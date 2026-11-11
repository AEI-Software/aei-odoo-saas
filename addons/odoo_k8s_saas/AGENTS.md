# Sub-agent: odoo_k8s_saas (core)

Follow the root [AGENTS.md](../../AGENTS.md) workflow (SDD question, TDD, quality gate).
This file adds the rules specific to this module.

## Owns
- `saas.instance`: tenant record and its state machine
  `draft → provisioning → ready → suspended → pending_delete → error → deleted`.
- Sync with Kubernetes through the portal API (`PORTAL_URL`, `PORTAL_KEY` env vars).
- Product fields that drive provisioning (`odoo_version`, `custom_image`,
  `install_modules`, `addons_repos_json`) and the `Odoo-SaaS` product category.

## Does not own
- Billing, subscriptions, checkout: `odoo_k8s_saas_subscription`.
- Anything public-facing: `aei_website`.

## Invariants
- This is the **lowest** layer. It must never import or depend on the subscription,
  support or website modules.
- State changes go through the state machine, never by writing `state` ad hoc.
- Never repair a tenant with `kubectl`. The record would desync from the cluster.
- Never hardcode the portal URL or key. Keep reading them from the environment.

## TDD focus (write these tests first)
- Valid and invalid state transitions.
- Provisioning call builds the right payload for each plan (mock the portal HTTP call).
- The reconcile cron handles an unreachable portal without raising. Locally it logs a
  DNS warning because there is no portal; that is expected, not a bug.

## Key files
- `models/saas_instance.py`, `models/product.py`, `models/saas_sale.py`
- `data/product_category.xml`, `data/ir_cron.xml`


## Structure (root `AGENTS.md`: size, models layout, comments, names)
Legacy that breaks the rules (frozen, may not grow; split when you touch it, tests first):
- `models/saas_instance.py` (644 lines), `models/saas_sale.py` (272 lines).
- `data/mail_template_branding_override.xml` (349 lines).
- Loose files directly in `models/`: `saas_instance.py`, `product.py`, `saas_sale.py`.

Target layout (proposed from the current method groups):
```
models/instance/   instance_fields.py       fields and constraints
                   provisioning_actions.py  provision, upgrade, stop, resume
                   deletion_actions.py      request delete, delete, pending-delete cron
                   config_actions.py        fetch/save config, logs, patch addons
                   status_sync.py           check status, reconcile cron, orphan DB cleanup
models/product/    product_template.py
models/billing/    invoice_provisioning.py  payment state, provision when paid
                   tenant_naming.py         category check and tenant id generation
data/mail/         one file per mail template
```

## Memory (Engram)
Follow the root `AGENTS.md` memory rules. Topic key prefix: `saas-core/odoo_k8s_saas-`.
Save: state-machine decisions, provisioning payload gotchas, portal API behavior.
