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
import markdown as markdown_lib
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

import session_store
from hmac_util import sign, verify

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

AGENT_WEBHOOK_SECRET = os.environ["AGENT_WEBHOOK_SECRET"]
ODOO_URL = os.environ.get("ODOO_URL", "http://odoo:8069")
AGENT_MAX_TURNS = int(os.environ.get("AGENT_MAX_TURNS", "12"))
AGENT_MAX_BUDGET_USD = float(os.environ.get("AGENT_MAX_BUDGET_USD", "0.50"))

# Trial fallback: AEI's own key, used only when the tenant hasn't set their
# own (BYOK) yet and Odoo says the tenant is still within its trial budget
# (GET /ai_agent/llm_config -> trial_available). Lives only here, in this
# pod's own env (agent_secret_manifest() in manifests.py) — never written
# into any tenant's Odoo database, so the shared platform key can't leak
# through Settings/developer mode the way a per-tenant config_parameter
# could. Odoo only ever sees a boolean + a running cost total it tracks
# itself from what this pod reports back after each trial turn.
DEFAULT_LLM_PROVIDER = os.environ.get("DEFAULT_LLM_PROVIDER", "")
DEFAULT_LLM_API_KEY = os.environ.get("DEFAULT_LLM_API_KEY", "")
DEFAULT_LLM_BASE_URL = os.environ.get("DEFAULT_LLM_BASE_URL", "")
DEFAULT_LLM_MODEL = os.environ.get("DEFAULT_LLM_MODEL", "deepseek-chat")

# Discuss renders a message body as HTML, so the model's Markdown used to land
# verbatim in the chat: "**bold**" shown literally, tables collapsed into one
# unreadable run of pipes, and every newline lost (SUB00268, 2026-08-13).
# Converting here (rather than in Odoo) keeps the fix where we own the image —
# the Odoo side sanitizes whatever it receives before posting it.
MARKDOWN_EXTENSIONS = ["tables", "fenced_code", "nl2br", "sane_lists"]

# Appended to the SDK's default preset, not replacing it. The chat panel is a
# narrow column: wide tables are painful there even once they render properly.
FORMAT_INSTRUCTIONS = (
    "You are answering inside Odoo's Discuss chat panel, a narrow column. "
    "Write in Markdown (it is converted to HTML before display). Prefer short "
    "paragraphs and bullet lists; use a table only for genuinely tabular data "
    "and keep it to 3 columns or fewer. Be concise — a few sentences beats a "
    "long report. Always answer in the same language the user wrote in."
)


def _to_html(text: str) -> str:
    """Markdown -> HTML for the Discuss message body."""
    try:
        return markdown_lib.markdown(text, extensions=MARKDOWN_EXTENSIONS)
    except Exception:
        # Never lose the answer over a formatting problem.
        logger.exception("agent: markdown conversion failed, sending plain text")
        return text


WELCOME_PROMPT = (
    "This is the very first time this user has opened a chat with you — "
    "they haven't typed anything yet. Proactively introduce yourself in "
    "1-3 short sentences: who you are (AEI Assistant), that you can help "
    "them configure and use their Odoo instance, and — only if you are "
    "currently running on AEI's own trial key rather than the tenant's "
    "own — mention briefly that they can set up their own API key in "
    "Settings > AEI Assistant for unlimited use. Keep it short and warm, "
    "in the same language the rest of this Odoo instance appears to be "
    "in (default to Spanish if unsure). Do not call any tools for this "
    "message."
)

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
    message: str = ""
    user_id: int
    user_login: str
    mcp_key: str
    welcome: bool = False


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


async def _fetch_llm_config() -> dict:
    """BYOK: pull the tenant's own AI-provider credentials from Odoo on
    every turn instead of a static env var, so a key change in Settings
    takes effect on the next message with no redeploy. When the tenant
    hasn't configured their own key, Odoo doesn't hand back a key at all —
    just `trial_available` (still within the platform's trial budget) or
    not — see saas_ai_agent's _aei_assistant_resolve_llm_config()."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{ODOO_URL}/ai_agent/llm_config",
            headers={"Authorization": f"Bearer {AGENT_WEBHOOK_SECRET}"},
        )
        resp.raise_for_status()
        return resp.json()


def _resolve_effective_config(remote_config: dict) -> dict | None:
    """Combine Odoo's answer with this pod's own trial credentials.
    Returns None if there's simply nothing usable to run the turn with
    (no BYOK key, and either not in trial or this pod has no default key
    configured at all — e.g. a provider portal-stg didn't set up)."""
    if remote_config.get("configured"):
        cfg = dict(remote_config)
        cfg["trial"] = False
        return cfg
    if remote_config.get("trial_available") and DEFAULT_LLM_API_KEY:
        return {
            "trial": True,
            "provider": DEFAULT_LLM_PROVIDER or "deepseek",
            "api_key": DEFAULT_LLM_API_KEY,
            "base_url": DEFAULT_LLM_BASE_URL or None,
            "model": DEFAULT_LLM_MODEL,
        }
    return None


def _build_options(llm_config: dict, mcp_key: str, resume: str | None) -> ClaudeAgentOptions:
    if llm_config["base_url"]:
        # Non-Anthropic (or self-hosted) provider — all confirmed to expose
        # an Anthropic-compatible /v1/messages endpoint (see
        # saas_ai_agent/models/res_config_settings.py PROVIDER_BASE_URLS).
        env = {
            "ANTHROPIC_BASE_URL": llm_config["base_url"],
            "ANTHROPIC_AUTH_TOKEN": llm_config["api_key"],
        }
    else:
        env = {"ANTHROPIC_API_KEY": llm_config["api_key"]}
    return ClaudeAgentOptions(
        model=llm_config["model"],
        env=env,
        # Preset + append: keep the SDK's own system prompt and add how to write
        # for the Discuss panel (see FORMAT_INSTRUCTIONS).
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": FORMAT_INSTRUCTIONS,
        },
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


async def _post_reply(channel_id: int, text: str, is_error: bool, cost_usd: float = 0.0, trial: bool = False, code: str | None = None) -> None:
    body = {"channel_id": channel_id, "text": text, "is_error": is_error, "cost_usd": cost_usd, "trial": trial, "code": code}
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
        try:
            remote_config = await _fetch_llm_config()
        except httpx.HTTPError as exc:
            logger.error("agent(channel=%s): failed to fetch llm_config: %s", payload.channel_id, exc)
            remote_config = {}
        llm_config = _resolve_effective_config(remote_config)
        if llm_config is None:
            # Odoo's pre-check (_dispatch_to_agent) only knows the tenant
            # side: it messages the user when there's no BYOK key AND the
            # trial budget is exhausted. It can NOT know whether this pod
            # actually holds a DEFAULT_LLM_API_KEY, so when the platform
            # trial key is unconfigured the dispatch still happens and
            # staying quiet here meant dead air for the user (SUB00265,
            # 2026-08-12). Send a typed reply instead — the Odoo controller
            # translates code=not_configured into the proper message in the
            # user's language and posts it as the bot.
            logger.warning("agent(channel=%s): no usable llm config — replying not_configured", payload.channel_id)
            await _post_reply(payload.channel_id, "", is_error=True, code="not_configured")
            return

        prompt = WELCOME_PROMPT if payload.welcome else payload.message
        resume = await session_store.get(payload.channel_id)
        options = _build_options(llm_config, payload.mcp_key, resume)
        session_id: str | None = None
        final_text = ""
        is_error = False
        cost_usd = 0.0

        async def _run(opts):
            """One turn. Returns (session_id, final_text, is_error, cost)."""
            sid, text, err, cost = None, "", False, 0.0
            # can_use_tool (our guardrail handler) requires streaming mode —
            # the one-shot query() helper only accepts a plain string prompt
            # and rejects can_use_tool with "requires streaming mode".
            async with ClaudeSDKClient(options=opts) as client:
                await client.query(prompt)
                async for message in client.receive_response():
                    cls_name = type(message).__name__
                    if cls_name == "SystemMessage" and getattr(message, "subtype", None) == "init":
                        sid = message.data.get("session_id")
                    elif cls_name == "ResultMessage":
                        err = bool(getattr(message, "is_error", False))
                        cost = float(getattr(message, "total_cost_usd", 0.0) or 0.0)
                        text = getattr(message, "result", None) or (
                            "No pude completar la solicitud." if err else ""
                        )
            return sid, text, err, cost

        try:
            session_id, final_text, is_error, cost_usd = await _run(options)
        except Exception as exc:  # noqa: BLE001 — always report back to the user
            # The conversation history lives in the CLI's own storage inside this
            # pod, while the session id is persisted per channel. A pod restart
            # (redeploy, eviction, OOM) therefore leaves a stored id the CLI no
            # longer knows, and EVERY existing channel's next message died with
            # "No conversation found with session ID" (SUB00268, 2026-08-13).
            # Drop the stale id and retry once, fresh — the user loses the
            # thread's context, not the answer.
            if resume and "No conversation found" in str(exc):
                logger.warning(
                    "agent(channel=%s): stale session %s, retrying without resume",
                    payload.channel_id, resume,
                )
                await session_store.clear(payload.channel_id)
                try:
                    session_id, final_text, is_error, cost_usd = await _run(
                        _build_options(llm_config, payload.mcp_key, None)
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("agent(channel=%s): retry failed", payload.channel_id)
                    is_error = True
                    final_text = "Ocurrió un error procesando tu mensaje. Inténtalo de nuevo en un momento."
            else:
                logger.exception("agent(channel=%s): turn failed", payload.channel_id)
                is_error = True
                final_text = "Ocurrió un error procesando tu mensaje. Inténtalo de nuevo en un momento."

        if session_id:
            await session_store.set(payload.channel_id, session_id)
        if not final_text:
            final_text = "No tengo una respuesta para eso todavía."

        await _post_reply(payload.channel_id, _to_html(final_text), is_error, cost_usd=cost_usd, trial=llm_config.get("trial", False))


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
