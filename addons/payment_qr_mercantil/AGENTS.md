# Sub-agent: payment_qr_mercantil

Follow the root [AGENTS.md](../../AGENTS.md) workflow (SDD question, TDD, quality gate).
This file adds the rules specific to this module.

## Owns
- QR payment provider for Banco Mercantil Santa Cruz (MC4 API): JWT-cached auth,
  QR generation, webhook-driven confirmation, a polling cron as fallback, and a
  2-second frontend poll while the customer pays.

## Reference for the next bank
- A Banco Ganadero provider (`payment_qr_ganadero`) is planned. Use this module's structure
  as the pattern and the spec in `docs/INTEGRACION_QR_BANCO_GANADERO.md`.
  Start with the SDD question: it is a new, security-sensitive feature.
- Do not copy-paste. If two providers share logic, extract it deliberately instead
  of duplicating (DRY), but only once the second one exists.

## Invariants
- The webhook endpoint is public and uses `csrf=False` because the bank is a server, not a
  browser. That is the allowed exception: it authenticates the caller with a per-transaction
  token in the callback URL, validates the payload and must be **idempotent**
  (a repeated notification must not confirm twice).
- The simulate route only works when the provider is in test mode. Keep it that way.
- Banco Ganadero authenticates differently (the bank logs in to our `login` and sends a JWT
  to `payments`), so there is no per-transaction URL token there. Do not assume this
  module's auth carries over.
- Never log tokens, API keys, passwords or full payloads.
- Credentials live on the provider record or in the environment, never in code.
- Amounts: use currency rounding. Compare the paid amount against the order amount.
- Confirmation is driven by the bank, not by the browser. The frontend poll only reads state.

## TDD focus (write these tests first)
- Webhook with a valid payment confirms the transaction exactly once.
- Replayed webhook is a no-op.
- Webhook with a wrong amount, unknown QR or bad credentials is rejected.
- Expired QR is handled.
- The cached JWT is reused and refreshed on expiry.
- Mock every bank HTTP call. Never hit the real API in tests.

## Key files
- `models/payment_provider.py`, `models/payment_transaction.py`
- `controllers/main.py`, `data/ir_cron_poll.xml`, `static/src/js/qr_mercantil_form.js`


## Structure (root `AGENTS.md`: size, models layout, comments, names)
Legacy that breaks the rules (frozen, may not grow; split when you touch it, tests first):
- `models/payment_provider.py` (378 lines), `controllers/main.py` (330 lines).
- `models/payment_transaction.py` is 245 lines: under the cap but close; do not add to it.
- Loose files directly in `models/`: `account_payment_method.py`, `payment_provider.py`,
  `payment_transaction.py`.

Target layout (also the template for `payment_qr_ganadero`, which must start compliant):
```
models/provider/      provider_fields.py     configuration fields
                      token_auth.py          get and refresh the cached JWT
                      qr_requests.py         generate QR, query status
models/transaction/   payment_transaction.py
models/payment_method/ account_payment_method.py
controllers/          display_qr.py, webhook.py, simulate_payment.py, status_polling.py
```

## Memory (Engram)
Follow the root `AGENTS.md` memory rules. Topic key prefix: `payments/payment_qr_mercantil-`.
Save: bank API quirks, webhook and idempotency decisions, answers from the bank.
Never save credentials, tokens or full payloads.
