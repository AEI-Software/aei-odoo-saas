# AEI Odoo SaaS — Orchestrator

You are the **main orchestrator** for this repository. Every task starts here.
Architecture, branches, deploy commands and security patterns live in
[CLAUDE.md](CLAUDE.md): read it before touching infrastructure.

Each custom module has its own **sub-agent** in `addons/<module>/AGENTS.md`.
Antigravity loads it automatically when you work inside that folder. When a task
touches a module, read that file first and obey its boundaries.

## Module routing

| Task touches | Sub-agent |
|---|---|
| Tenant model, K8s sync, provisioning UI | `addons/odoo_k8s_saas/AGENTS.md` |
| Subscription lifecycle, checkout, customer portal | `addons/odoo_k8s_saas_subscription/AGENTS.md` |
| Support hours, helpdesk tickets | `addons/odoo_k8s_saas_support/AGENTS.md` |
| QR payment (Banco Mercantil) | `addons/payment_qr_mercantil/AGENTS.md` |
| QR payment (Banco Ganadero v1.17.4) | `addons/payment_qr_ganadero/AGENTS.md` |
| Cookie / auth hardening | `addons/saas_security_hardening/AGENTS.md` |
| Landing page, plans, public website | `addons/aei_website/AGENTS.md` |
| `portal/`, `k8s/`, `infra/`, CI | no sub-agent: orchestrator handles it |

A change spanning several modules is split per module. Respect dependency
direction: `aei_website` → `odoo_k8s_saas_subscription` → `odoo_k8s_saas`.
A lower module never imports from a higher one.

## Workflow for every non-trivial task

1. **Route.** Identify the module(s) and read their `AGENTS.md`.
2. **Ask once: SDD?** Before any non-trivial change, ask the user one question:
   "Spec first (SDD) or direct?" Skip for typos, docs and one-line fixes.
   If yes, write `docs/specs/<change>.md` first: goal, Given/When/Then scenarios,
   acceptance criteria, out of scope. The tests derive from the scenarios.
3. **TDD: Red → Green → Refactor.** On by default.
   - **Red:** write a failing test, run it, and confirm it fails for the right reason.
   - **Green:** write the minimum code that passes.
   - **Refactor:** clean up with the tests green. No behavior change.
   - If a change is genuinely untestable (pure styling), say so instead of skipping silently.
4. **Quality gate** before declaring done (see checklist below).
5. **Verify, don't assume.** Run the check and report the real result. Say
   explicitly what was not verified.
6. **Record** decisions and gotchas in Engram (project `aei-software`).

## Engineering principles

- **Clean Code:** intention-revealing names, small functions with one job, no
  dead code, no magic numbers, comments explain *why* not *what*.
- **SOLID, KISS, DRY, YAGNI.** Do not build for hypothetical needs.
- **Easy to use and maintain:** the next developer must understand a file without
  asking. Prefer boring and explicit over clever.
- **Odoo way:** extend with `_inherit`, never edit core. Business logic in models,
  not in controllers or QWeb. Config in `ir.config_parameter` or env vars, not constants.
- **Python style:** PEP 8. Flake8 and Bandit must pass (they gate CI).
- **Commits:** conventional commits. No AI attribution.

## Testing (Odoo 18)

- Use `TransactionCase` for models and `HttpCase` for controllers and website.
- Tag tests `@tagged('post_install', '-at_install')` when they need website or payment.
- **Never hit the network in tests.** Mock the K8s portal API and bank APIs with
  `unittest.mock.patch`.
- Run against a throwaway database, never against your working one. Use a separate
  `--http-port`: tests start their own HTTP server and `--no-http` makes Odoo fail with
  `Port 8069 is in use` while the dev server is running:

```bash
docker compose -f docker-compose.dev.yml exec odoo \
  odoo -d aei_test -i <module> --test-enable --test-tags /<module> \
  --http-port=8099 --stop-after-init
```

## Standards alignment

These are the practices we follow, mapped to the standard that motivates them.
Following them is not an ISO certification.

| Standard | What it means here |
|---|---|
| ISO/IEC 25010 (product quality) | Review checklist: maintainability (modularity, testability), security, reliability, usability. |
| ISO/IEC/IEEE 12207 (lifecycle) | Spec → implement → verify → maintain, with traceability spec → test → commit. |
| ISO/IEC/IEEE 29119 (testing) | Designed, repeatable, independent tests. A failing test comes before the fix. |
| ISO/IEC 27001:2022 A.8.25–A.8.29 | Secure development lifecycle, security requirements, secure coding, security testing. |
| ISO/IEC 27001:2022 A.8.31–A.8.32 | Dev/test/prod separation and controlled change (main = staging, 18.0 = production). |

OWASP Top 10 and NIST SSDF are enforced in `.github/workflows/ci-cd.yml`.

## Memory (Engram)

Every agent, the orchestrator and each module sub-agent, uses Engram project
`aei-software` through MCP.

- **Before working:** `mem_search` with the module name and the topic. Reuse what is
  already decided instead of rediscovering it.
- **Save only what matters:** a decision and its reason, a bug fix with its root cause,
  a gotcha or non-obvious behavior, a convention, a user preference.
- **Do not save:** routine edits, code that is already in git, anything that is easy to
  re-read from the repo. **Never save secrets**: passwords, API keys, tokens,
  `admin_passwd`, bank credentials.
- **Topic key:** `<area>/<module>-<topic>`, for example `payments/payment_qr_mercantil-webhook-idempotency`.
  The same topic updates the same note (upsert) instead of creating duplicates.
- **Content format:** What, Why, Where (relative paths), Learned.
- **When:** save before writing the final answer, never as the last step of a turn.

## Code structure rules (owner decision, 2026-11-05)

Order is part of quality here. These apply to every sub-agent and are checked by
`.github/scripts/structure_gate.py` (CI, `validate` job).

1. **File size.** Every `.py` and `.xml` file under `addons/` stays at **200 lines or fewer**;
   **250 is the hard maximum**. Blank lines and comments count. Split before you reach 250,
   not after.
2. **Models layout.** `models/` contains only `__init__.py` and **sub-folders**. Each
   sub-folder is named after the logic or requirement it implements (for example
   `models/provisioning/`, `models/billing/`) and holds small files plus its own `__init__.py`.
   No loose `.py` files directly in `models/`. One file, one responsibility. Never a
   500 to 600 line catch-all. Views follow the same idea: group by feature in
   sub-folders (`views/home/`, `views/portal/`) once a module has more than three view files.
3. **Comments.** Explain what each piece is for, not what the syntax does.
   - Python: a docstring on every class and every function or method in `models/` and
     `controllers/`, including small compute methods.
   - XML: a comment at the top of every file saying what it defines, and a comment before
     each template, record or view block whose purpose is not obvious.
4. **File names.** English, plain and descriptive: `provisioning_actions.py`,
   `instance_form_views.xml`. Never `utils.py`, `helpers.py`, `misc.py`, `common.py`,
   `tmp.py`, `new.py`, `test2.py`, or a file that mixes two topics (`faq_cta.xml`).
5. **Legacy.** Some existing files break these rules; each module's `AGENTS.md` lists them.
   They are recorded in `.github/scripts/structure_baseline.json` and may **not grow**. When a
   task touches one, split it as part of that task, with tests written first so the split
   changes no behavior. **New code complies from its first commit.** A violation that is not in
   the baseline fails CI.
6. **Splitting a model in Odoo.** Keep one `_name` and extend it from several files with
   `_inherit` (one class per file, grouped by responsibility), or move shared logic to a
   mixin. Import every file from the sub-folder's `__init__.py`.

## Hard rules

- Never put secrets in the repo. Secrets come from `.secrets.env` / K8s Secrets.
- Never repair tenants with `kubectl` directly. Use the portal API or the SaaS module actions.
- Never change production (`18.0`, `odoo-admin`) without explicit user confirmation.
- Never use `:latest` image tags.
- Do not run destructive commands (drop DB, delete volumes, force push) without asking.
- All Odoo browser POST forms include `csrf_token`. Never disable CSRF on browser-facing
  routes. The only exception is a server-to-server webhook (`csrf=False`), and only if it
  authenticates the caller another way (token or JWT) and is listed in its module's `AGENTS.md`.
- Ask at most one question at a time, then wait.

## Definition of Done

- [ ] Failing test existed first and now passes (or untestable stated explicitly).
- [ ] Module's other tests still pass.
- [ ] `flake8` critical rules and `bandit` clean.
- [ ] `python3 .github/scripts/structure_gate.py` passes: files within 250 lines (target 200), no loose `.py` in `models/`, descriptive names, docstrings and XML comments present.
- [ ] No secrets, no hardcoded environment values.
- [ ] Dependency direction respected.
- [ ] Manifest version bumped if the schema or data changed (add a migration if needed).
- [ ] Docs updated (`docs/wiki/` or the module's `AGENTS.md`).
- [ ] Anything not verified is stated in the final message.

