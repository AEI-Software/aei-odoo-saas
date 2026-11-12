# Sub-agent: aei_website

Follow the root [AGENTS.md](../../AGENTS.md) workflow (SDD question, TDD, quality gate).
This file adds the rules specific to this module.

## Owns
- The public landing page (homepage override), pricing section, plan products, module explorer and plan dialogs.
- Custom public auth templates (`/web/login`, `/web/signup`, `/web/reset_password`, and `/account` redirect) wired to Odoo's native authentication engine.
- Custom Contact Us pages (`/contactus`, `/contactus-thank-you`, and CSRF-protected `POST /contactus/submit`).
- Static assets for the public site (`static/src/css/foundation`, `static/src/css/refinements`, `static/src/js/landing.js` including bidirectional scroll reveal/exit animations).
- Everything is versioned in code. Do not design pages in the browser editor: that
  content lives only in the database and is lost.

## Does not own
- Checkout, subscriptions, portal: `odoo_k8s_saas_subscription`.
- Payments: `payment_qr_*`.
- No business logic here. This module presents data and links to the native cart.

## Invariants
- Depends on `odoo_k8s_saas_subscription`; nothing depends on this module.
- Every POST form includes `csrf_token`. Never disable CSRF.
- JS never uses `innerHTML`, `outerHTML` or `document.write`. Use `textContent` and
  `createElement`.
- Never load remote scripts or CDN assets without a pinned version and SRI hash.
- Public copy is Spanish (Bolivia market). Code, identifiers and comments are English.
- Plan products carry the category `odoo_k8s_saas.product_category_odoo_saas` and a
  subscription template. That is what triggers provisioning after payment.

## Style rules (owner decision, 2026-11-05)
- Plain CSS only. No Bootstrap class, component or dependency in this module. Odoo Website
  ships Bootstrap in its own bundle and that cannot be removed; this module just does not use it.
- Every class is prefixed `aei-`. The only exceptions are `fa`/`fa-*` (icon font shipped by
  Odoo) and `oe_structure`. `tests/test_static_rules.py` enforces it.
- CSS is split by responsibility under `static/src/css/`: `tokens.css` (variables), `base.css`
  (scoped reset), `layout/`, `components/`, `sections/`, `effects/`. New colors go in
  `tokens.css`. No rule on `html`, `body` or a bare tag.
- Load order is declared in `__manifest__.py`; keep it in sync when adding a file.
- Pages use their own header and footer (`views/layout.xml`) and hide Odoo's through
  `website.page`. The shop, portal and backend keep Odoo's.

## Known debt (fix these, do not copy them)
- Plan marketing copy (headline, highlights, report counts) lives in `views/home/plans.xml`.
  Numbers (price, users, storage, support) come from records. If the copy must become
  editable by non-developers, move it to fields on the product.
- Top plan size is open (spec D1): the card shows the subscription template value (50 users
  today) while the design says 25. One data change fixes it once the owner decides.
- Not ported yet: standalone `/pricing` route. Header links point to anchors on `/` until
  `/pricing` exists.
- The homepage override uses `xpath` on `//div[@id='wrap']`. Confirm it against
  `website.homepage` in Odoo 18 whenever the website module is upgraded.
- `website.homepage_page` and `/contactus` chrome flags are set by `<function>` calls in
  `views/homepage.xml` and `views/contact/contactus.xml`, because those records are `noupdate`.
  Do not replace them with `<record>`.

## Testing
`tests/test_landing.py`, `tests/test_landing_offers.py`, `tests/test_landing_dialogs.py`,
`tests/test_plan_pricing.py`, `tests/test_account_and_contact.py` (HTTP, records, auth/contact
flows, scroll motion) and `tests/test_static_rules.py` (no Bootstrap, prefixes, no unsafe DOM).
Run with the command in the root `AGENTS.md` (in multi-DB environments pass `--db-filter=^aei_test$`
and `--workers=0 --max-cron-threads=0 --http-interface=127.0.0.1 --http-port=8099`).

## Key files
- `controllers/public_pages.py` (`/account` redirect and `/contactus/submit`)
- `models/plans/`, `models/catalog/`, `models/contact/website_contact.py`, `models/pages/website_page.py`
- `views/layout.xml`, `views/home/*.xml`, `views/homepage.xml`, `views/account/*.xml`, `views/contact/contactus.xml`
- `static/src/css/{foundation,refinements}/**`, `static/src/js/landing.js`, `migrations/`

## Structure (root `AGENTS.md`: size, models layout, comments, names)
This module is the reference for the rules and must stay clean with no baseline entries:
```
controllers/      public_pages.py            /account redirect and /contactus/submit
models/catalog/   module_catalog.py          interactive module explorer data
models/contact/   website_contact.py         sanitized contact form -> mail.mail
models/pages/     website_page.py            own chrome flags and b2c signup config
models/plans/     product_template.py, ...   plan lookup and billing pricing
views/layout.xml  header, footer, badge      shared page chrome
views/home/       one file per home section: hero, clients, processes, profiles, plans, ...
views/account/    login_layout.xml, login_forms.xml
views/contact/    contactus.xml              /contactus and /contactus-thank-you
views/homepage.xml                           assembles the home sections
static/src/css/   foundation/ then refinements/ (tokens, base, layout/, components/, sections/, effects/)
```
Add new pages as a sub-folder under `views/` (for example `views/pricing/`), one file per section.

## Memory (Engram)
Follow the root `AGENTS.md` memory rules. Topic key prefix: `frontend/aei_website-`.
Save: page and pricing decisions, QWeb or xpath gotchas, final copy and plan decisions.
