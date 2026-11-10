# Sub-agent: odoo_k8s_saas_subscription (bridge)

Follow the root [AGENTS.md](../../AGENTS.md) workflow (SDD question, TDD, quality gate).
This file adds the rules specific to this module.

## Owns
- The bridge between OCA subscriptions and tenant provisioning: stage and template
  changes trigger provision, upgrade and suspend.
- Checkout customizations (B2B address form, cart warning) and the customer portal
  (`/my/...` instance pages).
- Billing crons: dunning, renewal, closed-subscription grace period, user-count sync.
- Subscription templates for the three plans (starter, pro, enterprise).

## Does not own
- Tenant lifecycle and K8s calls: `odoo_k8s_saas`.
- Marketing pages and the landing page: `aei_website`.
- Payment providers: `payment_qr_*`.

## Invariants
- Depends on `odoo_k8s_saas`; never the other way around.
- `auto_install` is `True`: installing its dependencies installs it too. Keep that in mind
  before adding a dependency.
- Schema or data changes: bump the manifest version and add a script under `migrations/`.
- Webhook and portal controllers must authenticate the caller and check ownership:
  a customer sees only their own instances (`security/ir_rules.xml`).

## TDD focus (write these tests first)
- Stage change → correct provisioning action (mock the call into `odoo_k8s_saas`).
- Plan upgrade and downgrade map to the right plan resources.
- Record rules: customer A cannot read customer B's instance.
- Dunning levels fire on the right day and suspension on the right day.
- Extra-user billing line when users exceed `included_users`.

## Key files
- `models/sale_subscription.py`, `models/sale_order.py`, `models/saas_instance.py`
- `controllers/portal.py`, `controllers/webhook.py`, `controllers/website_sale_guard.py`
- `security/ir_rules.xml`, `data/subscription_templates.xml`, `migrations/`


## Structure (root `AGENTS.md`: size, models layout, comments, names)
Legacy that breaks the rules (frozen, may not grow; split when you touch it, tests first):
- `models/sale_subscription.py` (893 lines, the largest file in the repo).
- `views/subscription_portal_templates.xml` (681 lines).
- `controllers/portal.py` (363 lines).
- Loose files directly in `models/`: `sale_order.py`, `saas_instance.py`,
  `sale_subscription_template.py`, `sale_subscription.py`.

Target layout (proposed from the current method groups):
```
models/subscription/  subscription_fields.py   computed fields and portal URL
                      portal_actions.py        cancel, upgrade, reprovision
                      lifecycle_hooks.py       the write() hook: stage and template changes
                      dunning.py               reminder emails, suspend-overdue cron
                      closed_sync.py           closed-subscription grace-period cron
                      user_billing.py          user-count sync and extra-user line crons
models/order/         sale_order.py
models/instance/      saas_instance.py
models/template/      sale_subscription_template.py
views/portal/         one file per page: list, detail, plan change, backup
controllers/portal/   subscription_list.py, subscription_detail.py, plan_change.py, backup.py
```

## Memory (Engram)
Follow the root `AGENTS.md` memory rules. Topic key prefix: `billing/odoo_k8s_saas_subscription-`.
Save: lifecycle and dunning decisions, migration gotchas, checkout and portal behavior.
