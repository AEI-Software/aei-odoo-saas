"""Shared-secret request signing between the tenant Odoo pod and this agent pod.

Both directions (Odoo -> agent /hook, agent -> Odoo /ai_agent/reply) use the
same AGENT_WEBHOOK_SECRET and the same scheme: hex HMAC-SHA256 over the raw
request body, sent as the X-Agent-Signature header. Traffic is also fenced by
the tenant NetworkPolicy (only the odoo/agent pods in the same namespace can
reach each other), so this is defense in depth, not the only control.
"""
import hashlib
import hmac


def sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    expected = sign(secret, body)
    return hmac.compare_digest(expected, signature)
