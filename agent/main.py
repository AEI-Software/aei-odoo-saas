"""
Tenant AI agent — main entrypoint.

Provides:
  POST /hook      — Odoo posts a Discuss message here (postcommit hook from
                     the saas_ai_agent addon); returns 202 immediately and
                     processes the agent turn in the background.
  GET  /healthz    — liveness probe.

One process serves exactly one tenant (this is a per-tenant K8s Deployment,
not a pooled multi-tenant service — see /home/kali/.claude/plans/parsed-wobbling-dusk.md).
RBAC is enforced by Odoo itself: every MCP tool call runs as the specific
Odoo user who owns the muk_mcp key passed in on each /hook request, never a
shared admin identity (see the "RBAC design" section of the plan).
"""
import asyncio
import logging
import os

import httpx
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

import session_store
from hmac_util import sign, verify

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

AGENT_WEBHOOK_SECRET = os.environ["AGENT_WEBHOOK_SECRET"]
ODOO_URL = os.environ.get("ODOO_URL", "http://odoo:8069")
AGENT_MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5")
AGENT_MAX_TURNS = int(os.environ.get("AGENT_MAX_TURNS", "12"))
AGENT_MAX_BUDGET_USD = float(os.environ.get("AGENT_MAX_BUDGET_USD", "0.50"))

# Layer 2 guardrail (defense in depth — the authoritative block is the
# ORM-level override in saas_ai_agent/models/guardrails.py, gated on the
# mcp_name context key that muk_mcp stamps on every MCP request). This list
# rejects the tool call before it's even sent, so the LLM gets a clear
# denial message to relay instead of an opaque Odoo UserError.
DENYLISTED_MODELS = {
    "res.users",
    "res.groups",
    "ir.module.module",
    "ir.config_parameter",
    "muk_mcp.key",
    "ir.rule",
    "ir.model.access",
}

app = FastAPI(title="Tenant AI Agent")

# Serialize processing per Discuss channel so two messages in the same
# conversation never race each other's SDK session.
_channel_locks: dict[int, asyncio.Lock] = {}
_channel_locks_guard = asyncio.Lock()


async def _channel_lock(channel_id: int) -> asyncio.Lock:
    async with _channel_locks_guard:
        if channel_id not in _channel_locks:
            _channel_locks[channel_id] = asyncio.Lock()
        return _channel_locks[channel_id]


class HookPayload(BaseModel):
    channel_id: int
    message: str
    user_id: int
    user_login: str
    mcp_key: str


async def _pretooluse_guardrail(input_data: dict, _tool_use_id: str | None, _context) -> dict:
    """PreToolUse hook — NOT can_use_tool.

    can_use_tool looked like the natural fit but the SDK silently never
    calls it here: permission_mode="bypassPermissions" shadows it outright,
    and even without that, a whole-tool wildcard in allowed_tools (our
    "mcp__odoo__*") *also* shadows it (see claude_agent_sdk.types
    ._warn_if_can_use_tool_shadowed — verified against SDK 0.2.132 during
    the Phase 1 build, the SDK emits CanUseToolShadowedWarning for exactly
    this config). PreToolUse hooks are the mechanism the SDK itself
    recommends for gating every tool call regardless of permission_mode.
    """
    tool_input = input_data.get("tool_input", {})
    model = tool_input.get("model")
    if model in DENYLISTED_MODELS:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"No puedo operar sobre '{model}' — instalar apps, crear "
                    "usuarios y tocar permisos está fuera de mi alcance en "
                    "este plan. Explica la alternativa (upgrade de plan, "
                    "contactar soporte) en tu respuesta al usuario."
                ),
            }
        }
    return {}


def _build_options(mcp_key: str, resume: str | None) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=AGENT_MODEL,
        mcp_servers={
            "odoo": {
                "type": "http",
                "url": f"{ODOO_URL}/mcp",
                "headers": {"Authorization": f"Bearer {mcp_key}"},
            }
        },
        # tools=[] disables every *built-in* tool (Bash, Read, Task/Agent,
        # WebSearch, ...) outright. This is the exclusive gate — verified
        # during the Phase 1 build that allowed_tools alone does NOT do
        # this: it only auto-approves tools that are already available, so
        # with tools left at its default the model could (and, in testing,
        # did) reach for Bash/Task instead of the MCP tools. MCP tools are
        # unaffected by `tools` — they come from mcp_servers and are only
        # gated by allowed_tools.
        tools=[],
        allowed_tools=["mcp__odoo__*"],
        hooks={"PreToolUse": [HookMatcher(hooks=[_pretooluse_guardrail])]},
        setting_sources=[],
        permission_mode="bypassPermissions",
        max_turns=AGENT_MAX_TURNS,
        max_budget_usd=AGENT_MAX_BUDGET_USD,
        resume=resume,
    )


async def _post_reply(channel_id: int, text: str, is_error: bool) -> None:
    body = {"channel_id": channel_id, "text": text, "is_error": is_error}
    import json

    raw = json.dumps(body).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Agent-Signature": sign(AGENT_WEBHOOK_SECRET, raw),
    }
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(f"{ODOO_URL}/ai_agent/reply", content=raw, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("agent(channel=%s): failed to post reply back to Odoo: %s", channel_id, exc)


async def _run_turn(payload: HookPayload) -> None:
    lock = await _channel_lock(payload.channel_id)
    async with lock:
        resume = await session_store.get(payload.channel_id)
        options = _build_options(payload.mcp_key, resume)
        session_id: str | None = None
        final_text = ""
        is_error = False
        try:
            # can_use_tool (our guardrail handler) requires streaming mode —
            # the one-shot query() helper only accepts a plain string prompt
            # and rejects can_use_tool with "requires streaming mode".
            async with ClaudeSDKClient(options=options) as client:
                await client.query(payload.message)
                async for message in client.receive_response():
                    cls_name = type(message).__name__
                    if cls_name == "SystemMessage" and getattr(message, "subtype", None) == "init":
                        session_id = message.data.get("session_id")
                    elif cls_name == "ResultMessage":
                        is_error = bool(getattr(message, "is_error", False))
                        final_text = getattr(message, "result", None) or (
                            "No pude completar la solicitud." if is_error else ""
                        )
        except Exception as exc:  # noqa: BLE001 — always report back to the user
            logger.exception("agent(channel=%s): turn failed", payload.channel_id)
            is_error = True
            final_text = "Ocurrió un error procesando tu mensaje. Inténtalo de nuevo en un momento."

        if session_id:
            await session_store.set(payload.channel_id, session_id)
        if not final_text:
            final_text = "No tengo una respuesta para eso todavía."

        await _post_reply(payload.channel_id, final_text, is_error)


@app.post("/hook", status_code=202)
async def hook(request: Request, background_tasks: BackgroundTasks, x_agent_signature: str | None = Header(default=None)):
    raw = await request.body()
    if not verify(AGENT_WEBHOOK_SECRET, raw, x_agent_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = HookPayload.model_validate_json(raw)
    background_tasks.add_task(_run_turn, payload)
    return {"status": "accepted"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
