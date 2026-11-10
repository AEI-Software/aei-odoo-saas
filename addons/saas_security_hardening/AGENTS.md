# Sub-agent: saas_security_hardening

Follow the root [AGENTS.md](../../AGENTS.md) workflow (SDD question, TDD, quality gate).
This file adds the rules specific to this module.

## Owns
- Forces `Secure`, `HttpOnly` and `SameSite=Lax` on the `session_id` and
  `frontend_lang` cookies, independent of the reverse-proxy path.
- Password-reset flow without user enumeration: the response is the same whether
  or not the account exists.
- Remediation of the 2026-07 pentest findings (see `docs/wiki/Security-Remediation-2026-07.md`).

## Does not own
- Path-level blocking (DB manager, `/xmlrpc`, `/website/info`). That happens at the edge:
  `infra/apply-cf-security-rules.sh` and `k8s/03-traefik-middleware.yaml`.

## Invariants
- `auto_install` is `True`. It activates as soon as `base`, `web` and `auth_signup` are present.
- This module may only make the system **stricter**. Never relax a header or flag here.
- Behavior must not depend on `X-Forwarded-Proto` reaching Odoo (that was the root cause
  of the original finding).
- Never log credentials or reset tokens, even on failure.

## TDD focus (write these tests first)
- Regression test per finding it fixes. Each one must fail if the fix is removed:
  cookie flags (VULN-0006 / 0008 / 0011) and reset enumeration (VULN-0005).
- Reset for an existing and for a non-existing email returns an identical response
  (status and body).
- Cookies carry the three flags even without a forwarded-proto header.

## Key files
- `__init__.py` (cookie hardening), `controllers/auth_reset.py` (reset flow)


## Structure (root `AGENTS.md`: size, models layout, comments, names)
No known violations. Keep it that way: if `controllers/` grows past one file per concern,
group them by topic (cookies, password reset) and keep each file under the size cap.

## Memory (Engram)
Follow the root `AGENTS.md` memory rules. Topic key prefix: `security/saas_security_hardening-`.
Save: which finding each change fixes and why, edge cases of cookie and reset behavior.
