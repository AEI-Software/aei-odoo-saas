# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Odoo SaaS MVP — a multi-tenant SaaS platform for Odoo 18 on Kubernetes (K3s). Automates tenant provisioning, lifecycle management, subscription billing (OCA), and QR payment processing (Banco Mercantil, Bolivia). Production domain: `aeisoftware.com`.

## ⚠️ Estado de la infraestructura (2026-07-28)

**El entorno COTAS fue desmantelado.** El clúster K3s de producción/staging en `10.40.2.158`
(Ceph RBD, Patroni `192.168.0.x`, namespaces `odoo-admin` / `staging` / `aeisoftware`) ya no
existe. **No hay entorno productivo activo**; la migración a un nuevo proveedor está pendiente.

El **único entorno vivo es el testbed cruzoil**, y es solo laboratorio (no aloja nada productivo):

| Elemento | Valor |
|---|---|
| Host KVM | `10.9.13.2` (bare-metal Ubuntu 22.04) |
| K3s servers | `k3s-test-1..3` = `10.9.13.21-23` (Cilium + Longhorn) |
| VIP API server | `10.9.13.20` (kube-vip) |
| PostgreSQL | `pg-test-1` = `10.9.13.24` (Patroni single + PgBouncer + HAProxy + MinIO `https://10.9.13.24:9000`) |
| Inventario | `infra/environments/testbed.env` |
| Tunnel Cloudflare | propio, **in-cluster** (ns `cloudflare`, 2 réplicas) — tunnel `afc7a49a-166d-4505-92de-b9aad8fb1e32`, ruta comodín `*.aeisoftware.com` → `http://traefik.kube-system:80` |
| Dominios | los **mismos del ex-productivo**: `staging.` / `www.` / `portal.` / `<tenant>.aeisoftware.com` (`BASE_DOMAIN="aeisoftware.com"`). `test.aeisoftware.com` **descartado**: el Universal SSL no cubre dos niveles |

Detalle completo, invariantes del host y pendientes: `docs/wiki/Environment-Status.md`.
Las páginas del wiki que describen COTAS llevan un banner de desmantelamiento y se conservan
como referencia histórica.

## Branch Strategy

Con producción desmantelada, el modelo de dos ramas está **en pausa**: todo el trabajo va a
`main` (y a branches de feature como `feat/cloud-portability`). `18.0` sigue existiendo pero
no despliega en ningún lado hasta que haya nuevo entorno productivo.

Modelo original (histórico, a retomar tras la migración):

| Branch | Namespace | Domain | Role |
|--------|-----------|--------|------|
| `main` | odoo-stg (staging) | staging.aeisoftware.com | Staging/test |
| `18.0` | odoo-admin | admin.aeisoftware.com | Production |

## Architecture

Three layers work together:

1. **Portal API** (`portal/`) — FastAPI service that provisions/manages tenants via Kubernetes API. Runs as a Deployment (2 replicas) in namespace `aeisoftware`. Authenticated by `X-API-Key` header.

2. **Odoo Addons** — Custom modules installed in the admin Odoo instance:
   - `odoo_k8s_saas` — Core SaaS admin UI. Model `saas.instance` tracks tenants through states: draft → provisioning → ready → suspended → pending_delete → error → deleted. Cron syncs state from K8s every 2 min. Also owns the `ai_agent_enabled`/`ai_agent_state` toggle + `action_enable_ai_agent`/`action_disable_ai_agent`.
   - `odoo_k8s_saas_subscription` — Bridges OCA subscriptions to SaaS provisioning. Hooks on `stage_id`/`template_id` changes trigger provision/upgrade/suspend. Auto-install addon. Also bills the `aei_assistant` add-on via `_cron_update_aei_assistant_line`.
   - `payment_qr_mercantil` — QR payment via Banco Mercantil MC4 API. JWT-cached auth, webhook-driven confirmation, 2s polling on frontend.
   - `saas_ai_agent` — **Tenant-side** addon (not admin — installed inside each opted-in tenant's own DB) for the **AEI Assistant** AI agent feature: bot partner reachable via Discuss, BYOK settings screen, RBAC guardrails. Delivered to tenants via the dedicated `AEI-Software/aei-odoo-saas-agent` repo (git-clone, like any tenant addon), not baked into the tenant image. See [docs/wiki/AEI-Assistant.md](docs/wiki/AEI-Assistant.md).

3. **AI Agent workload** (`agent/`) — Per-tenant FastAPI + Claude Agent SDK container, one Deployment per opted-in tenant (not a sidecar, not a pooled multi-tenant service). Talks to the tenant's Odoo over MCP (via the vendored `muk_mcp` addon) scoped to whichever Odoo user is chatting — never a shared admin identity. See [docs/wiki/AEI-Assistant.md](docs/wiki/AEI-Assistant.md) for architecture, guardrails, and BYOK.

4. **Kubernetes Manifests** (`k8s/`) — Applied in lexical order (00-08). Each tenant gets its own namespace (`odoo-{tenant_id}`), PVC, secrets, deployment, service, ingress, and network policy.

**External dependency:** OCA contract/subscription modules included in `external_addons/` (rama 18.0). No longer cloned at deploy time.

## Plan Tiers (portal/k8s_utils/manifests.py)

Starter: 2 workers, 100m-500m CPU, 512Mi-1Gi RAM
Pro: 4 workers, 250m-1 CPU, 1Gi-2Gi RAM
Enterprise: 8 workers, 500m-2 CPU, 2Gi-4Gi RAM

## Cluster Access — testbed cruzoil (único entorno)

A diferencia de COTAS, aquí **kubectl corre local** contra el VIP; no hace falta salto SSH:

```bash
export KUBECONFIG=infra/k3s-ha/.kubeconfig.testbed   # server: https://10.9.13.20:6443
kubectl get nodes
```

| Parámetro | Valor |
|-----------|-------|
| Kubeconfig | `infra/k3s-ha/.kubeconfig.testbed` (gitignored) |
| API server | `https://10.9.13.20:6443` (kube-vip, alcanzable desde la workstation) |
| SSH a las VMs / host | usuario `ubuntu`, clave `/home/kali/it911/pentest_it911/hardening/keys/it911_admin_ed25519` |
| Secretos por entorno | `.secrets.env.testbed`, `infra/k3s-ha/.env.testbed`, `infra/postgres-ha/.env.testbed`, `infra/postgres-ha/.secrets.generated.testbed` (todos gitignored) |

> **kubectl:** el binario que vivía en `~/.local/bin/kubectl` ya no está — reinstalarlo antes
> de operar el testbed.

> **Invariantes del host cruzoil (`10.9.13.2`):** NO tocar `comodin-win7`, `pangolin_it911`,
> `pcd.qcow2`, la red `br0` ni los ~28 contenedores docker del host (Odoo 17 de clientes,
> cloudflared, traefik). Gateway de la red = `10.9.13.253`, no `.1`.

### Acceso histórico a COTAS (ya no funciona)

El nodo control `10.40.2.158` y la clave `.secrets/k3s_rsa` corresponden al clúster
desmantelado. Cualquier comando con `ssh ... ubuntu@10.40.2.158` en docs antiguos ya no aplica.

## Key Deployment Commands

> **IMPORTANTE — Solo existe el testbed.** Los comandos de `staging` / `odoo-admin` de COTAS
> ya no aplican (ver bloque histórico al final de esta sección). El testbed **no despliega el
> stack `odoo-admin`** — `06-odoo-admin.yaml`, `06b-odoo-admin-netpol.yaml`,
> `07-cloudflare-tunnel.yaml` y `05c-portal-servicemonitor.yaml` están excluidos en
> `testbed.env`.

> **Entorno por defecto:** desde 2026-07-28 los orquestadores usan `testbed.env` sin argumento
> (`deploy-k3s-cluster.sh:35`, `07-join-k3s-workers.sh:27`, `deploy-all.sh:39`,
> `apply-manifests.sh:27`). `cotas.env` queda como plantilla del entorno anterior. Aun así,
> pasar el entorno explícito es la forma más segura de operar.

> **IMPORTANTE — Addon deployment:** El pod de Odoo tiene un init container que clona el branch correspondiente de GitHub al arrancar. No hay imagen Docker que reconstruir para cambios de addons — solo hacer push y rollout restart.

> **IMPORTANTE — `--no-http`:** Siempre usar `--no-http` al actualizar módulos con `odoo -u` dentro del pod, porque el proceso principal ya ocupa el puerto 8069.

```bash
export KUBECONFIG=infra/k3s-ha/.kubeconfig.testbed   # kubectl local, sin salto SSH

# ── Levantar el entorno desde cero ──────────────────────────────────────────
./infra/k3s-ha/deploy-k3s-cluster.sh infra/environments/testbed.env
./infra/postgres-ha/deploy-all.sh    infra/environments/testbed.env
cp .secrets.env.example .secrets.env.testbed   # editar con valores reales
./infra/apply-manifests.sh --env infra/environments/testbed.env

# ── Local dev setup (WSL/Linux) ─────────────────────────────────────────────
DB_PASSWORD="..." API_KEY="..." ./dev-setup.sh

# ── Operación del testbed ───────────────────────────────────────────────────
kubectl get nodes
kubectl rollout restart deployment/portal -n aeisoftware
kubectl logs -n aeisoftware -l app=portal -f

# Actualizar el schema de un módulo en un tenant del testbed
POD=$(kubectl get pod -n odoo-<tenant> -l app=odoo --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n odoo-<tenant> $POD -- odoo -u <module_name> -d odoo_<tenant> --stop-after-init --no-http

# Portal: build and deploy
docker build -t ghcr.io/aei-software/aei-odoo-saas/portal:main portal/
kubectl rollout restart deployment/portal -n aeisoftware
```

<details>
<summary>Comandos históricos de COTAS (desmantelado 2026-07-28 — no funcionan)</summary>

```bash
SSH="ssh -i .secrets/k3s_rsa -o StrictHostKeyChecking=no ubuntu@10.40.2.158"

# STAGING (namespace: staging, branch: main)
$SSH "kubectl rollout restart deployment/odoo-stg -n staging && kubectl rollout status deployment/odoo-stg -n staging"
$SSH "POD=\$(kubectl get pod -n staging -l app=odoo-stg -o jsonpath='{.items[0].metadata.name}') && kubectl exec -n staging \$POD -- odoo -u <module_name> -d staging --stop-after-init --no-http"
$SSH "kubectl logs -n staging -l app=odoo-stg -f"
$SSH "kubectl rollout restart deployment/portal-stg -n staging"

# PRODUCCIÓN (namespace: odoo-admin, branch: 18.0)
$SSH "kubectl rollout restart deployment/odoo-admin -n odoo-admin && kubectl rollout status deployment/odoo-admin -n odoo-admin"
$SSH "POD=\$(kubectl get pod -n odoo-admin -l app=odoo-admin -o jsonpath='{.items[0].metadata.name}') && kubectl exec -n odoo-admin \$POD -- odoo -u <module_name> -d admin --stop-after-init --no-http"
```

</details>

## Portal API (portal/)

- **Entry:** `main.py` → FastAPI app, single router at `/api/v1/instances`
- **Router:** `routers/instances.py` — CRUD + stop/start/upgrade endpoints
- **K8s utils:** `k8s_utils/manifests.py` (manifest generators, PLAN_RESOURCES dict), `k8s_utils/client.py` (K8s SDK wrapper)
- **Dependencies:** `requirements.txt` — fastapi, kubernetes, psycopg2-binary, asyncpg, pydantic, httpx
- **Runs:** uvicorn, 4 workers, port 8000, non-root user `portal`
- **SQL safety:** All DDL uses `psycopg2.sql.Identifier()` — never f-strings for identifiers

## Odoo Addon Conventions

- All addons target Odoo 18.0 (`version: 18.0.x.y.z`)
- Security files at `security/ir.model.access.csv` (and optionally `ir_rules.xml`)
- Views in `views/` as XML, data in `data/` as XML
- Models extend Odoo base via `_inherit` pattern
- Subscription addon depends on `subscription_oca` (OCA module, not in this repo)

## CI/CD (.github/workflows/ci.yaml)

GitHub Actions builds portal Docker image on push to main/18.0. Tags: `:main`, `:18.0`, `:stable` (on 18.0 push), `:$SHA`. Pushes to GHCR. K8s deploy is manual (rollout restart).

## Testing

No automated test suite in the main repo. QA is manual per the test battery in README.md (admin + tenant perspective). OCA modules in `external_addons/` have their own Odoo test framework tests.

## CDN / Cloudflare

> _**Actualizado 2026-07-29:** los subdominios `staging.` / `www.` / `portal.` /
> `<tenant>.aeisoftware.com` vuelven a servir, ahora **desde el testbed**, vía un tunnel
> cloudflared propio desplegado **in-cluster** (`k8s/07-cloudflare-tunnel.yaml`, ns `cloudflare`)
> con una única ruta comodín `*.aeisoftware.com` → `http://traefik.kube-system:80`. Provisionar un
> tenant NO requiere llamadas a la API de Cloudflare. `admin.` sigue en 404 (stack `odoo-admin`
> excluido en el testbed)._
>
> _El tunnel del testbed es **distinto** del tunnel del host cruzoil (contenedor `6ad434184e13`,
> cargas de terceros): NO correr `setup_cloudflare_wildcard_tunnel.py` contra ese — su paso 2
> reemplaza todas las rutas. Verificar siempre `CF_TUNNEL_ID` antes de ejecutarlo._
>
> _Al diagnosticar con curl: las reglas WAF de zona que sobrevivieron a COTAS responden
> `403 cf-mitigated: challenge` al user-agent por defecto de curl. Con user-agent de navegador
> pasan. El comportamiento de caché descrito abajo sigue aplicando._

`aeisoftware.com` (y subdominios staging/admin/tenants) está detrás del proxy de Cloudflare. Al depurar
errores de frontend/assets, verificar `cf-cache-status` en los headers: el edge puede servir bundles
`/web/assets/*` viejos aunque el servidor esté sano (se sirven con `max-age=1año, immutable` y el hash de
la URL no cambia al recompilar). Tras purgar assets en el servidor o cambiar la imagen de Odoo, purgar
también Cloudflare. Runbook completo en `DEPLOY.md` § "Caché de assets frontend y Cloudflare".

## Reparación y provisioning de tenants

Nunca reparar (ni **crear**) tenants con `kubectl` directo (set image, edit deployment, apply manifests a
mano...): el `saas.instance` queda desincronizado — una instancia en `error` no vuelve sola a `ready`, y un
tenant creado por kubectl directo **no aparece ni es gestionable** desde los menús de Odoo (Ventas /
Suscripciones / SaaS), porque no existe el registro `saas.instance` correspondiente. Siempre usar el portal
API o las acciones del módulo SaaS (`action_provision`, `action_enable_ai_agent`, etc.) — confirmado en vivo
2026-08-07/08 al provisionar un tenant de prueba con kubectl directo y no poder encontrarlo luego en el
admin.

## Documentation Wiki

Full documentation (HLD, LLD, runbooks, API reference, QA battery) lives in **`docs/wiki/`** (start at
`docs/wiki/Home.md`) — migrated from the GitHub wiki on 2026-07-10 because private-repo wikis require a
paid GitHub plan to view in the browser (the `aei-odoo-saas.wiki.git` repo still exists but nobody could
read it from the UI). Keep documenting there as plain `.md` files, not on the GitHub wiki. Business
analysis reports live in `docs/` directly.

## Security Patterns

- Secrets via K8s Secrets from `.secrets.env` (never committed)
- Per-tenant NetworkPolicy isolation (default-deny + whitelist)
- Tenant ID validation: regex `^[a-z0-9][a-z0-9\-]{0,46}[a-z0-9]$`
- PodDisruptionBudgets on portal and odoo-admin
- Non-root containers (portal user, odoo UID 101)
- Image pinning (no `:latest` tags)

## Important Files

| Path | Purpose |
|------|---------|
| `infra/environments/testbed.env` | Inventario del único entorno vivo (cruzoil) — nodos, storage, S3, exclusiones |
| `docs/wiki/Environment-Status.md` | Qué entornos existen hoy y qué páginas del wiki son históricas |
| `docs/wiki/AEI-Assistant.md` | Arquitectura, guardrails, BYOK y billing del agente de IA por tenant |
| `infra/apply-manifests.sh` | Main deploy orchestrator (reads .secrets.env, creates namespaces/secrets, applies manifests) |
| `portal/routers/instances.py` | Tenant provisioning API (create, status, upgrade, delete, stop, start, agent/enable, agent/disable) |
| `portal/k8s_utils/manifests.py` | K8s manifest generators + PLAN_RESOURCES + agent_* generators + AGENT_PLAN_RESOURCES |
| `agent/main.py` | Tenant AI agent container — Claude Agent SDK, BYOK config fetch, guardrails |
| `saas_ai_agent/` | Tenant-side addon for the AI agent feature (Discuss bot, BYOK settings, RBAC) |
| `k8s/06-odoo-admin.yaml` | Production Odoo admin deployment (init containers, probes, volumes) — excluido en el testbed |
| `k8s/07-staging.yaml` | Staging environment manifest — sin entorno donde aplicarse hoy |
| `odoo_k8s_saas/models/saas_instance.py` | Core tenant model + K8s sync logic |
| `odoo_k8s_saas_subscription/models/sale_subscription.py` | Subscription → provisioning hooks |
| `payment_qr_mercantil/models/payment_transaction.py` | QR payment flow + webhook handler |
| `DEPLOY.md` | Production deployment procedures and diagnostics |
