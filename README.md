# Odoo SaaS MVP

Multi-node Kubernetes SaaS provisioning for Odoo 18, running on **K3s + Ceph RBD + PostgreSQL HA + Cloudflare tunnels**.

> 📖 Full documentation: [**docs/wiki/Home.md**](docs/wiki/Home.md)

---

## Architecture

```
Internet → Cloudflare Tunnel → Traefik (K3s ingress)
                                    ├── admin.aeisoftware.com  → odoo-admin pod (namespace: odoo-admin)
                                    ├── portal.aeisoftware.com → portal FastAPI  (namespace: aeisoftware)
                                    └── <tenant>.aeisoftware.com → per-tenant Odoo pod (namespace: odoo-<tenant>)
                                              ↓
                                    PostgreSQL HA (HAProxy:5000 — primary directo)
```

> **Nota:** PgBouncer fue eliminado de la arquitectura. Todo el tráfico (workers, admin, DDL)
> va directamente a través de HAProxy en el puerto **5000**. Esto permite LISTEN/NOTIFY nativo
> (longpolling sin `bus_alt_connection`) y evita problemas de compatibilidad con transacciones.

**Init container flow (every pod restart):**
1. `copy-addon` (alpine/git) — clona el repo `main` con `--depth=1` y copia los addons a `/mnt/extra-addons` (incluye `subscription_oca` desde un fork OCA externo)
2. `render-config` (alpine) — usa `sed` para reemplazar placeholders `REPLACE_*` con valores de secretos en `odoo.conf`
3. `odoo:18` inicia leyendo `/etc/odoo/odoo.conf` y `/mnt/extra-addons`

---

## Addons incluidos

Todos los módulos propios viven bajo [`addons/`](addons/) (cada uno con su propio subagente `AGENTS.md`) y los de terceros bajo [`external_addons/`](external_addons/):

| Módulo | Ruta | Descripción |
|---|---|---|
| `aei_website` | `addons/aei_website` | Sitio web público y Landing Page de AEI Software (CSS puro sin Bootstrap, planes SaaS y catálogo de módulos) |
| `odoo_k8s_saas` | `addons/odoo_k8s_saas` | UI admin de instancias SaaS (kanban, estados, acciones K8s) |
| `odoo_k8s_saas_subscription` | `addons/odoo_k8s_saas_subscription` | Bridge de suscripciones OCA ↔ instancias SaaS, checkout y portal de clientes |
| `odoo_k8s_saas_support` | `addons/odoo_k8s_saas_support` | Bolsa de horas de soporte mensual e integración con tickets Helpdesk |
| `payment_qr_mercantil` | `addons/payment_qr_mercantil` | Pasarela de pago por QR — Banco Mercantil Santa Cruz (mc4.com.bo) |
| `saas_security_hardening` | `addons/saas_security_hardening` | Endurecimiento de cookies de sesión (`Secure`, `HttpOnly`, `SameSite=Lax`) y protección anti-enumeración en `/web/reset_password` |
| `subscription_oca` | `external_addons/subscription_oca` | Contratos de suscripción recurrentes — vendored desde [OCA/contract](https://github.com/OCA/contract) (branch `18.0`); sincronizar con `scripts/sync-oca-contract.sh` |

---

## Security & DevSecOps Features

| Feature | Implementation |
|:--------|:-------------|
| SQL Injection Protection | DDL queries use `psycopg2.sql.Identifier()` — no f-strings |
| Session & Auth Hardening | `saas_security_hardening` enforces `Secure/HttpOnly/SameSite=Lax` cookies & generic password-reset responses |
| CSRF & Safe DOM | Mandatory `csrf_token` on all browser POST forms; zero `innerHTML`/`eval` in frontend JS |
| NetworkPolicy | Default-deny + whitelist for `odoo-admin`; per-tenant isolation |
| PodDisruptionBudgets | `minAvailable: 1` for portal and odoo-admin |
| Liveness Probes | All services: portal (`/healthz`), odoo-admin (`/web/health`), tenants |
| Tenant ID Validation | `@api.constrains` regex + min 2 chars + SQL `UNIQUE` |
| Secrets Management | K8s Secrets + ConfigMap (passwords embedded at provision time); Gitleaks blocks secrets in Git |
| Image & Action Pinning | `cloudflared:2026.3.0`, no `:latest`; GitHub Actions pinned to 40-char commit SHAs |
| Data Protection on Close | Subscription "Closed" → `action_stop()` suspends pods, preserves PVC+DB |
| Automated DevSecOps Gates | 6 CI gates in [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml): Gitleaks, Bandit + Semgrep (OWASP Top 10), `pip-audit` + Trivy FS, Trivy K8s Config, `structure_gate.py` + `security_gate.sh` + `flake8`, and Trivy Container Image scan |

---

## Branch Strategy & Namespace Topology

| Branch | Ambiente | Namespace K8s | Pod / Deploy | Dominio |
|:-------|:---------|:-------------|:------------|:--------|
| `main` | **Staging** | `staging` | `odoo-stg` | `staging.aeisoftware.com` |
| `18.0` | **Producción** | `odoo-admin` | `odoo-admin` | `admin.aeisoftware.com` / `www.aeisoftware.com` |

> **Regla:** Todos los cambios van a `main` primero, se prueban en Staging, y luego se promueven a `18.0`.

> [!CAUTION]
> **Para reiniciar Staging** usar siempre:
> ```bash
> kubectl rollout restart deployment/odoo-stg -n staging
> ```
> **Para reiniciar Producción** (solo en ventanas de mantenimiento):
> ```bash
> kubectl rollout restart deployment/odoo-admin -n odoo-admin
> ```
> ⚠️ `odoo-admin` es **PRODUCCIÓN**. `odoo-stg` es **STAGING**.

---

## Day 0 — Instalación desde cero

Existen dos modos de instalación sobre **K3s**:
- **Opción A — Desarrollo Local con K3s (WSL / Linux en una sola máquina):** usa [`./dev-setup.sh`](dev-setup.sh), almacenamiento nativo `local-path` de K3s, PostgreSQL 16 interno ([`k8s/dev/02-postgres-local.yaml`](k8s/dev/02-postgres-local.yaml)) y monta directamente tu carpeta local `addons/`. No requiere Ceph, Cloudflare Tunnel ni S3 externo.
- **Opción B — Servidor Cloud de Producción (Multi-nodo + Ceph RBD + PostgreSQL HA externo):** usa [`infra/apply-manifests.sh`](infra/apply-manifests.sh).

---

### Opción A — Desarrollo Local en K3s (WSL / Linux)

```bash
chmod +x dev-setup.sh
./dev-setup.sh
```

**Qué hace automáticamente `./dev-setup.sh`:**
1. Configura `/etc/hosts` local para `www.aeisoftware.com`, `admin.aeisoftware.com` y `portal.aeisoftware.com`.
2. Instala K3s (si no está instalado), copia el kubeconfig a `~/.kube/config` (compatible con `kubectl` de Snap) y despliega Traefik vía Helm.
3. Construye la imagen local `saas-portal:dev` y la importa en el `containerd` de K3s.
4. Despliega PostgreSQL 16 local en K3s (`k8s/dev/02-postgres-local.yaml`, puertos `5000` y `5432`, `storageClassName: local-path`).
5. Despliega `portal` y `odoo-admin` usando almacenamiento `local-path` y copiando directamente tus carpetas locales `addons/` y `external_addons/`.
6. Expone Odoo en `http://www.aeisoftware.com` (`:8069`) y el Portal FastAPI en `http://portal.aeisoftware.com/docs` (`:8000/docs`).

Una vez que `./dev-setup.sh` termina, inicializá por primera vez los módulos en la base `admin` de K3s (ver **Paso 7** más abajo).

---

### Opción B — Servidor Cloud de Producción (Day 0)

> **Prerequisites (Producción):**
> - Ubuntu 22.04 / Debian 12 VM con `root` o `sudo`, almacenamiento Ceph RBD (`ceph-rbd`) y clúster PostgreSQL HA externo (`192.168.0.x:5000`)
> - Dominio DNS apuntando al servidor y Cloudflare Tunnel token
> - GHCR token con acceso read a `ghcr.io/aei-software/aei-odoo-saas/*`
> - Credenciales MC4 del Banco Mercantil (si usas `payment_qr_mercantil` en producción)

---

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/AEI-Software/aei-odoo-saas.git
cd aei-odoo-saas
```

---

### Paso 2 — Crear el archivo de secretos

```bash
cp .secrets.env.example .secrets.env
nano .secrets.env          # completar TODOS los valores — nunca hacer commit de este archivo
```

**Variables requeridas en `.secrets.env` por `infra/apply-manifests.sh`:**

| Variable | Requerida | Descripción | Ejemplo |
|---|---|---|---|
| `DB_PASSWORD` | ✅ sí | Contraseña del usuario `odoo` en PostgreSQL | `S3cre7DB!` |
| `ADMIN_PASSWD` | ✅ sí | Master password de Odoo (para gestión de bases de datos) | `MasterP4ss!` |
| `API_KEY` | ✅ sí | Clave secreta del portal FastAPI (`X-API-Key` / Bearer) | `uuid4-largo` |
| `CLOUDFLARE_TUNNEL_TOKEN` | ✅ sí | Token del tunnel en Cloudflare Zero Trust Dashboard | `eyJ...` |
| `BACKUP_S3_ACCESS_KEY` | ✅ sí | Access Key de RadosGW / S3 para CronJobs de backup | `AKIA...` |
| `BACKUP_S3_SECRET_KEY` | ✅ sí | Secret Key de RadosGW / S3 para CronJobs de backup | `s3cr3t...` |
| `BACKUP_PG_SUPERUSER_PASSWORD` | ✅ sí | Contraseña del rol superusuario `postgres` (para `pg_dump`) | `PgSup3r!` |
| `SAAS_WEBHOOK_KEY` | ✅ sí | Secreto compartido entre el portal FastAPI y el webhook de Odoo | `openssl rand -hex 32` |

> **`.secrets.env` está en `.gitignore` — nunca se commitea.**
> El script `apply-manifests.sh` valida que ninguna de las 8 variables tenga el placeholder `change_me` y las inyecta como Kubernetes Secrets.

---

### Paso 3 — Instalar K3s (sin Traefik integrado)

```bash
bash infra/install-k3s.sh
```

Instala K3s con `--disable=traefik` y espera a que el nodo quede `Ready`.
*(Si en tu sistema tenés `/snap/bin/kubectl`, copiá antes o después `/etc/rancher/k3s/k3s.yaml` a `~/.kube/config`).*

---

### Paso 4 — Instalar Traefik via Helm

```bash
bash infra/install-traefik.sh
```

Instala Traefik con Helm en el namespace `kube-system` como controlador de ingress.

---

### Paso 5 — Aplicar todos los manifests (Producción)

```bash
KUBECONFIG=/etc/rancher/k3s/k3s.yaml bash infra/apply-manifests.sh
```

El script:
1. Lee `.secrets.env` y valida que las 8 variables requeridas no tengan placeholders `change_me`
2. Crea namespaces `aeisoftware`, `odoo-admin`, `backup-system` y `cloudflare` si no existen
3. Crea el PVC `odoo-admin-data` (20Gi, `ceph-rbd`) si no existe
4. Crea Kubernetes Secrets a partir de las variables env (nunca desde archivos git)
5. Aplica los manifests `k8s/backup/*.yaml` y `k8s/0*.yaml` en orden (saltando `01-secrets.yaml`)
6. Verifica los endpoints de PostgreSQL HA (`192.168.0.x:5000`)

> **Dry-run:** `KUBECONFIG=/etc/rancher/k3s/k3s.yaml bash infra/apply-manifests.sh --dry-run` muestra qué se aplicaría sin tocar el cluster.
> **Nota para WSL / Laptop local:** Si estás en tu máquina de desarrollo sin Ceph ni PostgreSQL HA externo, en lugar del Paso 5 ejecutá `./dev-setup.sh` (ver **Opción A** arriba).

---

### Paso 6 — Configurar el proveedor de pago QR Mercantil

Una vez que el pod `odoo-admin` esté `Running`:

1. Ir a **Contabilidad → Configuración → Diarios de pago** (o **Contabilidad → Configuración → Proveedores de pago**)
2. Buscar **"QR Mercantil"** y abrirlo
3. En la pestaña **Credenciales** completar:

| Campo Odoo | Header MC4 API | Descripción |
|---|---|---|
| **API Key (Login)** | `apikey` | Clave para el endpoint de autenticación (`/autenticacion/v1/generarToken`) |
| **API Key Servicio** | `apikeyServicio` | Clave para los endpoints de QR (`/api/v1/generaQr`, `/api/v1/estadoTransaccion`) |
| **Usuario API** | `username` en body | Usuario para obtener el JWT |
| **Contraseña API** | `password` en body | Contraseña para obtener el JWT |
| **URL Base API** | — | Default: `https://sip.mc4.com.bo:8443` |
| **Webhook URL** | `callback` en generaQr | Ej: `https://admin.aeisoftware.com/payment/qr_mercantil/webhook` |

4. En la pestaña **Configuración**:
   - **Estado** → `Producción` (para llamadas reales al banco) o `Prueba` (modo demo, sin llamadas reales)

> **Modo Prueba (`state=test`):** genera QRs SVG ficticios, nunca llama al banco.
> El botón "Simular Pago" en el checkout confirma la transacción directamente.
> Ideal para flujos de testing de SaaS provisioning sin credenciales reales.

---

### Paso 7 — Instalar / actualizar módulos Odoo

La **primera vez** en una base `admin` recién creada, usar `-i` (para instalar); en actualizaciones posteriores de esquema, usar `-u`:

```bash
POD=$(kubectl get pod -n odoo-admin -l app=odoo-admin -o jsonpath='{.items[0].metadata.name}')

# Primera vez (instalar todos los módulos del repo en la base 'admin'):
kubectl exec -n odoo-admin $POD -- \
  odoo -i payment_qr_mercantil,odoo_k8s_saas,odoo_k8s_saas_subscription,odoo_k8s_saas_support,saas_security_hardening,aei_website,subscription_oca \
  -d admin --stop-after-init --http-port=8099

# Actualizaciones posteriores (cuando los módulos ya están instalados):
kubectl exec -n odoo-admin $POD -- \
  odoo -u payment_qr_mercantil,odoo_k8s_saas,odoo_k8s_saas_subscription,odoo_k8s_saas_support,saas_security_hardening,aei_website,subscription_oca \
  -d admin --stop-after-init --http-port=8099

# Luego restart limpio
kubectl rollout restart deployment/odoo-admin -n odoo-admin
kubectl rollout status deployment/odoo-admin -n odoo-admin
```

> **Nota:** ningún módulo se auto-actualiza en restart. El container Odoo inicia sin flag `-u`.
> Para actualizar módulos tras cambios de esquema, ejecutar el comando `odoo -u <módulo>` manualmente.
> Ver la sección "Cuando hay cambios de esquema" en [DEPLOY.md](DEPLOY.md) para el procedimiento detallado.

---

## Flujo de despliegue estándar (Day N)

```bash
# 1. Commit y push del código
git add <archivos>
git commit -m "tipo(módulo): descripción"
git push origin main

# 2. Rollout restart — el initContainer clona el repo actualizado
kubectl rollout restart deployment/odoo-admin -n odoo-admin

# 3. Esperar Ready
kubectl rollout status deployment/odoo-admin -n odoo-admin

# 4. Verificar logs
POD=$(kubectl get pod -n odoo-admin -l app=odoo-admin -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n odoo-admin $POD -f
```

> En `push` o `pull_request` a `main` / `18.0`, el pipeline DevSecOps ([`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml)) ejecuta automáticamente las 6 puertas de seguridad y calidad y, en `push` a `main`, despliega a Staging. El workflow [`.github/workflows/ci.yaml`](.github/workflows/ci.yaml) construye y publica la imagen del portal en GHCR. El despliegue a Producción (`odoo-admin`, rama `18.0`) siempre requiere confirmación manual del operador.

---

## Provisionamiento de un Tenant (Day 1)

```bash
# Crear instancia
curl -X POST https://portal.aeisoftware.com/api/v1/instances \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "demo", "plan": "starter", "storage_gi": 10}'

# Verificar estado (poll hasta "ready")
curl -H "X-API-Key: $API_KEY" https://portal.aeisoftware.com/api/v1/instances/demo
```

La instancia queda disponible en `https://demo.aeisoftware.com`.

Each tenant gets:
- Dedicated K8s namespace (`odoo-<tenant_id>`)
- Dedicated PostgreSQL database + role
- PVC with `local-path` (dev) or `ceph-rbd` (prod) StorageClass
- NetworkPolicy (tenant isolation)
- Liveness probe (`/web/health`)
- Ingress via Traefik → Cloudflare tunnel
- **Plan-specific resources** (workers, CPU, RAM) — see table below

---

## Plan de Recursos por Tier

Cada plan SaaS provisiona instancias con recursos de cómputo diferenciados:

| Plan | Workers Odoo | CPU Request | CPU Limit | RAM Request | RAM Limit | Almacenamiento |
|:-----|:------------:|:-----------:|:---------:|:-----------:|:---------:|:--------------:|
| **Starter** | 2 | 100m | 500m | 512Mi | 1Gi | 10 GB |
| **Pro** | 4 | 250m | 1 core | 1Gi | 2Gi | 50 GB |
| **Enterprise** | 8 | 500m | 2 cores | 2Gi | 4Gi | 100 GB |

Definidos en `portal/k8s_utils/manifests.py` → `PLAN_RESOURCES`.

### Upgrade de Plan (sin pérdida de datos)

```bash
# Cambiar un tenant existente de starter a pro (en vivo, sin borrar datos)
curl -X PATCH https://portal.aeisoftware.com/api/v1/instances/demo/upgrade \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"plan": "pro", "storage_gi": 50}'
```

El endpoint:
1. Actualiza el `ConfigMap` odoo.conf (`workers`, `max_cron_threads`)
2. Parchea el `Deployment` con nuevos limits de CPU/RAM
3. Reinicia el pod para que tome los cambios (rolling restart)

> **Regla operativa:** Los upgrades de plan se hacen **editando la plantilla (template) en la suscripción OCA**,
> no creando una nueva suscripción. Crear una nueva suscripción generará una instancia nueva en blanco.

---

## Ciclo de vida de Suscripciones y Instancias

| Evento | Acción en Odoo | Resultado en K8s |
|:-------|:--------------|:----------------|
| Confirmar venta + Activar suscripción | Stage → *In Progress* | Pod aprovisionado, DB creada |
| Cambiar plantilla (Upgrade/Downgrade) | Template → Pro/Enterprise | ConfigMap actualizado, Deployment re-aplicado |
| Suscripción vence (cron) | `_cron_suspend_overdue` | Pod escalado a 0 réplicas (datos preservados) |
| Cerrar suscripción | Stage → *Closed* | Pod suspendido (`action_stop()`) — **datos preservados** |
| Borrado manual por Sysadmin | `action_request_delete()` desde `saas.instance` | Namespace + DB eliminados definitivamente |

> ⚠️ **IMPORTANTE:** Cerrar una suscripción **suspende** la instancia, no la borra.
> El borrado definitivo debe ser ejecutado manualmente por el administrador del sistema
> desde la vista **SaaS → Instancias** usando el botón **"Eliminar instancia"**.

## Estructura del repositorio

```
aei-odoo-saas/
├── AGENTS.md                         # Orquestador principal (SDD, TDD, Clean Code, reglas de estructura)
├── CLAUDE.md                         # Guía de arquitectura, ramas, K8s y patrones de seguridad
├── addons/                           # Módulos propios de Odoo 18 (cada uno con su propio AGENTS.md)
│   ├── aei_website/                  # Sitio web público y Landing Page (CSS puro sin Bootstrap)
│   │   ├── AGENTS.md                 # Subagente del módulo web
│   │   ├── models/                   # Subcarpetas por lógica: plans/, catalog/, pages/
│   │   ├── views/                    # layout.xml, homepage.xml y subcarpeta views/home/
│   │   ├── data/                     # saas_plans.xml y catalog/modules.json
│   │   ├── static/src/               # CSS en dos capas (foundation/ + refinements/), JS y fuentes locales
│   │   ├── migrations/               # Migraciones de datos post-migrate (18.0.1.1.0)
│   │   └── tests/                    # Suite TDD (HttpCase, TransactionCase y reglas estáticas)
│   ├── odoo_k8s_saas/                # UI admin de instancias SaaS y sincronización con K8s
│   │   ├── AGENTS.md
│   │   ├── models/                   # saas.instance: aprovisionamiento, upgrade, stop/resume
│   │   ├── views/                    # Kanban, formulario, lista y acciones
│   │   ├── data/                     # Categoría SaaS, plantillas de correo y cron de estado
│   │   └── security/ir.model.access.csv
│   ├── odoo_k8s_saas_subscription/   # Bridge de suscripciones OCA ↔ instancias K8s y portal
│   │   ├── AGENTS.md
│   │   ├── controllers/              # Portal de cliente, guardas de checkout y webhook SaaS
│   │   ├── models/                   # Hooks de suscripción, orden de venta y plantillas
│   │   ├── views/                    # Vistas de suscripción, checkout y portal
│   │   ├── data/                     # Plantillas de suscripción, productos y crons
│   │   └── security/                 # ir.model.access.csv + ir_rules.xml
│   ├── odoo_k8s_saas_support/        # Bolsa de horas de soporte mensual y tickets Helpdesk
│   │   ├── AGENTS.md
│   │   ├── models/                   # Consumo de horas en helpdesk.ticket y sale.subscription
│   │   ├── views/                    # Vistas de tickets, suscripciones y portal
│   │   └── security/ir.model.access.csv
│   ├── payment_qr_mercantil/         # Pasarela de pago por QR Banco Mercantil (SIP MC4)
│   │   ├── AGENTS.md
│   │   ├── controllers/main.py       # /payment/qr_mercantil/webhook, /status, /simulate
│   │   ├── models/                   # payment.provider y payment.transaction
│   │   ├── static/src/js/            # Polling de estado, simulación y protección doble-click
│   │   └── views/                    # Configuración del proveedor y plantilla QR
│   └── saas_security_hardening/      # Endurecimiento de cookies de sesión y auth_reset
│       ├── AGENTS.md
│       └── controllers/auth_reset.py
├── external_addons/                  # Addons de terceros vendored (subscription_oca, helpdesk_mgmt, etc.)
├── docs/
│   ├── specs/                        # Especificaciones SDD (ej. aei-website-landing.md)
│   └── wiki/                         # Documentación extendida de arquitectura y operaciones
├── k8s/                              # Manifiestos de Kubernetes
│   ├── 00-namespace.yaml             # Namespaces (aeisoftware, odoo-admin)
│   ├── 00-network-policy.yaml        # Base network policies
│   ├── 01-secrets.yaml               # Placeholder — secretos se aplican vía .secrets.env
│   ├── 01-traefik.yaml               # Traefik CRDs / IngressRoutes
│   ├── 02-postgres.yaml              # PostgreSQL service
│   ├── 02-postgres-external.yaml     # PostgreSQL HA external endpoints
│   ├── 02-postgres-config.yaml       # PostgreSQL config
│   ├── 02-cloudflare-tunnel.yaml     # Cloudflare tunnel (pinned v2026.3.0)
│   ├── 03-cloudflared.yaml           # cloudflared DaemonSet (pinned v2026.3.0)
│   ├── 03-traefik-middleware.yaml    # Traefik middlewares
│   ├── 04-rbac.yaml                  # ServiceAccount + ClusterRole + Binding (aeisoftware + staging)
│   ├── 05-portal.yaml                # Portal FastAPI (4 workers, liveness probe)
│   ├── 05b-pdb.yaml                  # PodDisruptionBudgets (portal + odoo-admin)
│   ├── 06-odoo-admin.yaml            # Odoo admin (clona y copia addons/* + external_addons/*)
│   ├── 06b-odoo-admin-netpol.yaml    # NetworkPolicy for odoo-admin (default-deny + whitelist)
│   ├── 07-staging.yaml               # Entorno completo de Staging
│   ├── 08-backup-cronjob.yaml        # Backup CronJob
│   ├── dev/00-dev-secrets.yaml       # Secretos para entorno local de desarrollo
│   └── prod/06-odoo-admin-cloud.yaml # Deployment de producción odoo-admin
├── portal/                           # FastAPI portal API (orquestador de clúster K8s)
│   ├── main.py
│   ├── routers/instances.py          # Lifecycle API: POST create, PATCH upgrade, DELETE, stop/start
│   ├── k8s_utils/
│   │   ├── manifests.py              # PLAN_RESOURCES + generadores de manifiestos por tenant
│   │   └── client.py                 # Wrapper del SDK de K8s (apply, patch, scale, restart)
│   ├── Dockerfile                    # uvicorn --workers 4
│   └── requirements.txt
├── scripts/
│   ├── reset_transactional_data.sql  # SQL para limpiar datos transaccionales
│   └── backup-odoo-admin.sh          # Full backup (DB + filestore)
├── infra/
│   ├── install-k3s.sh                # Instala K3s sin Traefik integrado
│   ├── install-traefik.sh            # Instala Traefik via Helm
│   ├── apply-manifests.sh            # Aplica todos los manifests (lee .secrets.env)
│   └── create-cf-route.sh            # Helper para rutas Cloudflare
├── dev-setup.sh                      # Bootstrap automático K3s local (WSL / Linux)
├── bandit.yaml                       # Configuración de análisis SAST Python (Bandit)
├── .gitleaks.toml                    # Reglas de detección de secretos (Gitleaks)
├── .secrets.env.example              # Plantilla — copiar a .secrets.env y completar
└── .github/
    ├── scripts/
    │   ├── structure_gate.py         # Gate de estructura: <=250 líneas, subcarpetas en models/, docstrings
    │   ├── structure_baseline.json   # Baseline congelado de archivos legados
    │   └── security_gate.sh          # Gate OWASP: cero secretos, CSRF, .sudo() auditados, cero :latest
    └── workflows/
        ├── ci-cd.yml                 # Pipeline DevSecOps de 6 puertas + deploy a Staging
        └── ci.yaml                   # Build + push de imagen del portal FastAPI a GHCR
```

> **Nota:** `subscription_oca` está vendored en `external_addons/` (fuente:
> [OCA/contract](https://github.com/OCA/contract) branch `18.0`, sha en
> `external_addons/OCA_CONTRACT_SHA`). Refrescar con `scripts/sync-oca-contract.sh`.

---

## Cloudflare Tunnel

Regla wildcard configurada en Zero Trust Dashboard:
```
*.aeisoftware.com → http://traefik.kube-system.svc.cluster.local:80
```

No se requieren cambios DNS por tenant.  
El `IngressRoute` de Traefik por tenant enruta por header `Host:`.

---

## CI/CD y Pipeline DevSecOps (GitHub Actions)

El repositorio cuenta con dos workflows automatizados en [`.github/workflows/`](.github/workflows/):

### 1. Pipeline Principal de Calidad, DevSecOps y Staging ([`ci-cd.yml`](.github/workflows/ci-cd.yml))
Se ejecuta en cada `push` y `pull_request` hacia `main` y `18.0` (con todas las acciones fijadas por hash SHA de 40 caracteres y permisos mínimos):

1. **`secrets` (Gitleaks):** escanea el historial y el árbol de trabajo con [`.gitleaks.toml`](.gitleaks.toml) para bloquear cualquier credencial, token o clave privada.
2. **`sast` (Bandit + Semgrep OWASP Top 10):** analiza vulnerabilidades estáticas en Python (`addons/` y `portal/`) usando [`bandit.yaml`](bandit.yaml) y reglas `p/owasp-top-ten`.
3. **`sca` (`pip-audit` + Trivy FS):** audita dependencias de Python y el sistema de archivos en busca de CVEs críticos o altos.
4. **`k8s-security` (Trivy Config):** valida los manifiestos de [`k8s/`](k8s/) y prohíbe el uso de imágenes con tag `:latest`.
5. **`validate` (Lint + Structure Gate + Security Gate):**
   - Verifica compilación Python y reglas críticas de `flake8`.
   - Ejecuta [`python3 .github/scripts/structure_gate.py`](.github/scripts/structure_gate.py): exige que todo archivo `.py` y `.xml` nuevo bajo `addons/` tenga **<= 200 líneas (máximo duro 250)**, subcarpetas por lógica dentro de `models/`, docstrings en clases/métodos y comentarios en vistas XML.
   - Ejecuta [`bash .github/scripts/security_gate.sh`](.github/scripts/security_gate.sh): verifica ausencia de secretos hardcodeados, `csrf=False` no autorizados, `shell=True`, `verify=False`, `:latest` y audita el uso de `.sudo()`.
6. **`build-and-scan` + `deploy-staging`:** construye la imagen Docker, la escanea con Trivy Image (`CRITICAL,HIGH`) y, en `push` a `main`, despliega automáticamente al entorno de Staging.

### 2. Build de Imagen del Portal FastAPI ([`ci.yaml`](.github/workflows/ci.yaml))
En cada push a `main`:
1. Construye la imagen Docker de `portal/` con Docker Buildx + layer cache.
2. Publica en `ghcr.io/aei-software/aei-odoo-saas/portal` con el SHA del commit.
3. Para aplicar en producción (`aeisoftware`), el operador ejecuta `kubectl -n aeisoftware rollout restart deployment/portal`.

---

## Módulos de terceros

> **Nota:** El módulo `subscription_oca` ha sido incorporado al repositorio en `external_addons/` para simplificar el despliegue. Anteriormente se clonaba de un repositorio externo.

---

## Diagnóstico rápido

```bash
# Ver todos los pods en namespaces relevantes
kubectl get pods -n aeisoftware
kubectl get pods -n odoo-admin
kubectl get pods -n staging

# Logs del pod Odoo admin
POD=$(kubectl get pod -n odoo-admin -l app=odoo -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n odoo-admin $POD -f --tail=100

# Logs del portal
kubectl logs -n aeisoftware deployment/portal -f --tail=100

# NetworkPolicies
kubectl get netpol -A

# PDBs
kubectl get pdb -A

# Liveness probes status
kubectl get deploy -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,PROBE:.spec.template.spec.containers[0].livenessProbe.httpGet.path'
```

### Reset completo (Eliminar SaaS + Tenant DBs + PVCs)

```bash
# Borra las bases de datos en Postgres
## Nota: el cluster PG corre en 3 VMs externas (no en K8s). Para eliminar DBs/roles de tenants manualmente, ver [[PostgreSQL Cluster Operations]] en la wiki.

# Borra la instancia en K8s (deployments, servicios, PVCs y secretos)
python3 infra/delete-instance.py demo-company
```

---

## Multi-Version y Custom Images

La plataforma soporta la creación de instancias con versiones específicas de Odoo (17.0, 18.0, 19.0) y el uso de **imágenes de Docker personalizadas** por cliente (ej: `ghcr.io/aei-software/aei-custom-odoo-images:19.0`).
- La configuración de versión se define en el **Producto SaaS** (Pestaña "SaaS Configuration").
- Cuando se vende una suscripción con una imagen personalizada, Kubernetes forzará un `imagePullPolicy: Always` para asegurar que el tenant siempre utilice la última versión de su imagen custom sin depender del caché del nodo.
- Los módulos integrados en la imagen personalizada deben ubicarse en `/opt/custom-addons` para evitar ser sobrescritos por los volúmenes efímeros de Kubernetes.

---

## Batería de Pruebas Sugeridas (QA)

### Pruebas desde la perspectiva del Administrador (Admin Odoo-SaaS-MVP)
1. **Creación de Producto:** Crear un nuevo producto SaaS, ir a la pestaña "SaaS Configuration", asignar `Odoo Version = Custom Image`, e introducir el tag de una imagen alojada en Github en el campo `Custom Odoo Image`.
2. **Venta Automática:** Crear un presupuesto para un cliente con el producto SaaS y confirmarlo. Verificar que el estado de la venta avance y la suscripción pase a "In Progress".
3. **Provisionamiento:** Navegar a "SaaS -> Instancias" en el backend administrativo. Verificar que el ORM haya creado la instancia automáticamente heredando la versión y ruta de imagen del producto hijo.
4. **Verificación de Logs:** Acceder a la vista formulario de la instancia SaaS y confirmar a través de los botones nativos "Odoo Logs" e "Init Logs" que la instancia booteó sin errores y descargó las credenciales de la API FastAPI.
5. **Gestión de Ciclo de Vida:** Ejecutar la acción "Suspend" para escalar el pod a 0 (reducción de consumo) y "Resume" para escalar a 1. Comprobar en Kubernetes que los pods bajen o suban efectivamente.

### Pruebas desde la perspectiva del Cliente Final (Tenant SaaS)
1. **Recepción de Credenciales:** Tras confirmarse el pago u orden, verificar la recepción del correo electrónico automatizado enviado por el Cron Job, conteniendo la URL única, usuario (`admin`) y la contraseña generada aleatoriamente.
2. **Acceso al Sistema:** Navegar a la URL autogenerada para el Tenant (vía Traefik ingress) e ingresar con las credenciales exactas del email.
3. **Verificación de Módulos Base:** Confirmar que el Wizard de inicialización cargó el Odoo básico en blanco sin romper dependencias de Python.
4. **Verificación de Addons Custom (Si aplica):** Comprobar que los addons inyectados a nivel de la imagen Docker en `/opt/custom-addons` aparecen correctamente en la lista de Aplicaciones listas para instalar sin arrojar exclusiones de `FileNotFoundError` en logs.
5. **Persistencia Volumétrica:** Crear un registro transaccional cualquiera (ej. un Cliente). Solicitar al Admin simular una Suspensión temporal y posterior Reactivación de la instancia. Retornar al sistema y validar que la base de datos Postgres y el volumen Ceph RBD conservaron la integridad del registro intacta.

---

## Teardown

### Solo los workloads Odoo/portal (mantiene K3s)

```bash
kubectl delete namespace odoo-admin aeisoftware --ignore-not-found
kubectl get ns -o name | grep '^namespace/odoo-' | xargs -r kubectl delete
```

### Teardown completo (elimina K3s y todos los datos)

```bash
/usr/local/bin/k3s-uninstall.sh
```

> ⚠️ **Destructivo.** Todos los PVCs, bases de datos y estado del cluster se pierden permanentemente.

---

## Admin Odoo

Acceso en `https://admin.aeisoftware.com`

Los addons proveen:
- **App SaaS** en el menú principal (kanban de instancias)
- Estados: `draft → provisioning → ready → suspended → pending_delete → deleted`
- Validación de `tenant_id`: mínimo 2 chars, regex `[a-z0-9\-]`, SQL `UNIQUE`
- Edición On-The-Fly de `odoo.conf` y Repositorios Extra (vía K8s ConfigMap)
- Extracción de **Logs** del pod directamente desde la UI de Odoo
- Botones Suspender / Reanudar con scale-down/up en K8s a 0 o 1 réplicas
- Hook automático: Upgrade de plantilla de suscripción → actualiza workers/CPU/RAM en K8s
- Cron jobs: sync de estado e inquilinos cada 2 min, suspensión de instancias vencidas diariamente
- Per-tenant NetworkPolicy: aislamiento automático de cada namespace
- Cron de facturación OCA con `try/except` por subscripción — un registro corrupto no detiene el proceso
