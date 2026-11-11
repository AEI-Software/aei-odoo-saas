# Sub-agent: odoo_k8s_saas_support

Follow the root [AGENTS.md](../../AGENTS.md) workflow (SDD question, TDD, quality gate).
This file adds the rules specific to this module.

## Owns
- Support-hour tracking per subscription: monthly allowance per instance and
  add-on hour packages.
- Helpdesk ticket extensions (`helpdesk_ticket`, `saas_support_log`) and the portal views for them.

## Does not own
- The helpdesk itself: it is the OCA `helpdesk_mgmt` in `external_addons/`. Never edit it.
  Extend it with `_inherit`.
- Subscription lifecycle: `odoo_k8s_saas_subscription`.

## Invariants
- Depends on `odoo_k8s_saas_subscription` and `helpdesk_mgmt`.
- Unused monthly hours expire each month (see the plan terms in
  `odoo_k8s_saas_subscription/data/subscription_templates.xml`). Never carry them over.
- A customer sees only the tickets and hours of their own subscription.

## TDD focus (write these tests first)
Current model (`models/sale_subscription.py`): total = plan allowance + support-pack
hours; consumed = hours logged in `saas.support.log` for the current month;
available = total − consumed.
- Total equals the plan allowance plus pack hours.
- Only logs from the current month count as consumed (no rollover).
- Available hours follow total − consumed.
- Over-allowance behavior is not defined yet: decide it with the user, then test it.
- Record rules: customer A cannot read customer B's tickets.

## Key files
- `models/helpdesk_ticket.py`, `models/saas_support_log.py`, `models/sale_subscription.py`
- `data/products.xml`, `views/portal_templates.xml`

## Structure (root `AGENTS.md`: size, models layout, comments, names)
No file is over the size limit today. Legacy that breaks the rules (frozen; fix when you touch it):
- Loose files directly in `models/`: `helpdesk_ticket.py`, `saas_support_log.py`,
  `product_template.py`, `sale_subscription.py`.

Target layout:
```
models/helpdesk/   helpdesk_ticket.py, saas_support_log.py
models/hours/      sale_subscription.py     monthly total, consumed, available
models/products/   product_template.py
```

## Memory (Engram)
Follow the root `AGENTS.md` memory rules. Topic key prefix: `support/odoo_k8s_saas_support-`.
Save: support-hours policy decisions (over-allowance, expiry), helpdesk integration gotchas.
