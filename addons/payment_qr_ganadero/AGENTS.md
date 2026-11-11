# Sub-agent: payment_qr_ganadero

Follow the root [AGENTS.md](../../AGENTS.md) workflow (SDD question, TDD, quality gate).
This file adds the rules specific to this module.

## Owns
- QR Empresarial v1.17.4 payment provider for Banco Ganadero (`code = 'qr_ganadero'`):
  - Outbound API consumption: Point 2 (`/qrcode/access`), Point 3 (`/qrcode/collections`),
    Point 4 (`/qrcode/transactions`), and Point 5 (`/qrcode/status`).
  - Inbound webhooks exposed to Banco Ganadero: Point 6 (`POST /payment/qr_ganadero/login`)
    and Point 7 (`POST /payment/qr_ganadero/payments`) with Point 8 response codes
    (`COD000`, `COD001`, `COD002`, `COD003`).
  - Test/Demo mode (`state == 'test'`) with SVG QR generation and payment simulation.
  - 3-second frontend status polling and 2-minute fallback cron (`_cron_qr_ganadero_poll_pending`).

## Invariants & Security Rules
- **Server-to-server CSRF exceptions (documented per root `AGENTS.md`):**
  - `POST /payment/qr_ganadero/login` (`controllers/bank_webhook.py`): uses `csrf=False` because
    Banco Ganadero is an external server. Authenticates caller with alphanumeric `userName` and
    `password` verified via `hmac.compare_digest` and issues an HS256-signed JWT with expiration.
  - `POST /payment/qr_ganadero/payments` (`controllers/bank_webhook.py`): uses `csrf=False`
    because Banco Ganadero posts JSON with `Authorization: Bearer <jwt>`. Verified via strict
    HS256 signature and `exp` check. Must be **idempotent** on `qrId` (repeated notification
    returns `COD000` without double confirmation).
- The simulate route (`/payment/qr_ganadero/simulate`) only works when `provider.state == 'test'`.
- Never log tokens, API keys, passwords, or JWT secrets.
- Every file under `addons/payment_qr_ganadero/` must stay under 200 lines (hard cap 250) and
  keep models inside logic sub-folders (`models/provider/`, `models/transaction/`,
  `models/payment_method/`).

## Memory (Engram)
Follow the root `AGENTS.md` memory rules. Topic key prefix: `payments/payment_qr_ganadero-`.

