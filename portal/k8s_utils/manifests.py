"""
k8s_utils/manifests.py

Generates Kubernetes manifest dicts for a tenant Odoo deployment.
Fase 3 — K3s HA con Ceph RBD storage y PostgreSQL HA externo:
  - PostgreSQL HA en 192.168.0.127/.186/.226 via HAProxy
  - :5000 HAProxy primary directo (all traffic)
  - LISTEN/NOTIFY nativo (longpolling sin bus_alt_connection)
  - ceph-rbd StorageClass (pool k3s-rbd)
  - Cilium NetworkPolicy con egress a 192.168.0.0/24
"""
from __future__ import annotations
import os
from typing import Any

BASE_DOMAIN = os.getenv("BASE_DOMAIN", "aeisoftware.com")
URL_SCHEME = os.getenv("URL_SCHEME", "http")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres.aeisoftware.svc.cluster.local")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5000"))          # HAProxy primary
POSTGRES_PORT_PRIMARY = int(os.getenv("POSTGRES_PORT_PRIMARY", "5000"))  # Same (legacy compat)
POSTGRES_USER = os.getenv("POSTGRES_USER", "odoo")
# ── Topología de base de datos ───────────────────────────────────────────────
# "external": clúster PG compartido FUERA de K8s (HAProxy/Patroni — modelo
#             original COTAS y el testbed cruzoil). El portal crea rol+DB por
#             psycopg2 contra POSTGRES_HOST.
# "cnpg":     una instancia PostgreSQL single POR TENANT dentro de su propio
#             namespace (CloudNativePG) — nueva arquitectura, ver
#             docs/CLOUD-STRATEGY-2026-08.md §3. El portal NO toca psycopg2:
#             el Cluster CR hace initdb con las credenciales que el portal
#             genera (secret pg-app-user), así el flujo de odoo-secret y
#             odoo.conf es idéntico en ambas topologías.
PG_TOPOLOGY = os.getenv("PG_TOPOLOGY", "external")
CNPG_IMAGE = os.getenv("CNPG_IMAGE", "ghcr.io/cloudnative-pg/postgresql:16")
CNPG_STORAGE_GI = int(os.getenv("CNPG_STORAGE_GI", "5"))
# Tamaño del PVC agent-workspace (agent_pvc_manifest) — usado para computar el
# techo de storage del namespace en resourcequota_manifest.
AGENT_WORKSPACE_GI = 1
ODOO_IMAGE = os.getenv("ODOO_IMAGE", "ghcr.io/aei-software/aei-odoo-saas/odoo:stable")
AGENT_IMAGE = os.getenv("AGENT_IMAGE", "ghcr.io/aei-software/aei-odoo-saas/agent:stable")
# Platform-owned trial key for the AI agent add-on — used only when a
# tenant hasn't set their own (BYOK) key yet, within a per-tenant budget
# Odoo itself tracks (see saas_ai_agent's aei_assistant_trial_cap_usd).
# Injected straight into each tenant's agent-secret; never written into
# any tenant's Odoo database. Empty by default — the trial fallback is
# simply unavailable until the platform operator sets these.
DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "deepseek")
DEFAULT_LLM_API_KEY = os.getenv("DEFAULT_LLM_API_KEY", "")
DEFAULT_LLM_BASE_URL = os.getenv("DEFAULT_LLM_BASE_URL", "https://api.deepseek.com/anthropic")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "deepseek-chat")
# local-path para dev local K3s, ceph-rbd para producción Cloud
STORAGE_CLASS = os.getenv("STORAGE_CLASS", "local-path")
# Red donde vive el clúster PostgreSQL externo (egress directo de tenants a HAProxy)
PG_NETWORK_CIDR = os.getenv("PG_NETWORK_CIDR", "192.168.0.0/24")
# Middleware namespace = namespace donde se despliegan los middlewares de Traefik
# Los middlewares (odoo-headers, odoo-compress) están en kube-system (ver 02-traefik-config.yaml)
ODOO_HEADERS_MIDDLEWARE = os.getenv("ODOO_HEADERS_MIDDLEWARE", "kube-system-odoo-headers@kubernetescrd")
# Security response headers (HSTS, X-Frame-Options, CSP, Referrer-Policy) — see k8s/03-traefik-middleware.yaml.
# Defaults to the aeisoftware-namespaced copy to match the ODOO_HEADERS_MIDDLEWARE override for tenants.
SECURITY_HEADERS_MIDDLEWARE = os.getenv(
    "SECURITY_HEADERS_MIDDLEWARE", "aeisoftware-security-headers@kubernetescrd"
)
# GitHub PAT for cloning private tenant addon repos (optional — public repos work without it)
GIT_TOKEN = os.getenv("GIT_TOKEN", "")
# Default language installed + set as default on every new tenant (Bolivia market).
TENANT_DEFAULT_LANG = os.getenv("TENANT_DEFAULT_LANG", "es_BO")
# Per-instance support user (created at first boot by odoo-init). The password is
# generated per tenant by the portal (like app_admin_password), stored in the tenant
# odoo-secret (SUPPORT_PASSWORD) and returned in the create response so the SaaS
# admin addon can log it in the saas.instance chatter. If empty, the support user
# is simply not created — provisioning still succeeds.
SUPPORT_USER_LOGIN = os.getenv("SUPPORT_USER_LOGIN", "soporte@aeisoftware.com")

# ── Per-plan compute resources ───────────────────────────────────────────────
# Each plan tier gets different Odoo workers, CPU, and RAM limits.
# These values are injected into the ConfigMap (odoo.conf) and Deployment.
PLAN_RESOURCES = {
    "starter": {
        "workers": 2, "cron_threads": 1,
        "cpu_req": "100m", "cpu_lim": "500m",
        "mem_req": "512Mi", "mem_lim": "1Gi",
    },
    "pro": {
        "workers": 4, "cron_threads": 1,
        "cpu_req": "250m", "cpu_lim": "1",
        "mem_req": "1Gi", "mem_lim": "2Gi",
    },
    "enterprise": {
        "workers": 8, "cron_threads": 1,
        "cpu_req": "500m", "cpu_lim": "2",
        "mem_req": "2Gi", "mem_lim": "4Gi",
    },
}

# ── AI agent add-on resources per plan ───────────────────────────────────────
# Deliberately not scaled with plan size the way PLAN_RESOURCES is — the
# agent's footprint is dominated by the SDK/CLI subprocess (~256Mi-1Gi
# regardless of tenant size, see agent/Dockerfile), not the tenant's own
# workload. Enterprise gets minReplicas effectively always-on (no
# scale-to-zero yet — that's Phase 5); starter/pro are meant to be toggled
# on demand by the customer.
AGENT_PLAN_RESOURCES = {
    "starter": {"cpu_req": "128m", "cpu_lim": "1", "mem_req": "256Mi", "mem_lim": "1Gi"},
    "pro": {"cpu_req": "256m", "cpu_lim": "1", "mem_req": "512Mi", "mem_lim": "2Gi"},
    "enterprise": {"cpu_req": "256m", "cpu_lim": "1", "mem_req": "512Mi", "mem_lim": "2Gi"},
}


def namespace_manifest(tenant_id: str) -> dict[str, Any]:
    """Namespace for one tenant: odoo-<tenant_id>"""
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": _ns(tenant_id),
            "labels": {
                "managed-by": "saas-portal",
                "tenant": tenant_id,
            },
        },
    }


def pvc_manifest(tenant_id: str, storage_gi: int = 10) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {
            "name": "odoo-data",
            "namespace": _ns(tenant_id),
        },
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "storageClassName": STORAGE_CLASS,
            "resources": {"requests": {"storage": f"{storage_gi}Gi"}},
        },
    }


def secret_manifest(tenant_id: str, db_password: str, admin_password: str, app_admin_password: str, support_password: str = "") -> dict[str, Any]:
    """Per-tenant secret with DB password and Odoo admin password."""
    import base64
    def b64(s: str) -> str:
        return base64.b64encode(s.encode()).decode()

    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": "odoo-secret",
            "namespace": _ns(tenant_id),
        },
        "type": "Opaque",
        "data": {
            "DB_PASSWORD": b64(db_password),
            "ADMIN_PASSWD": b64(admin_password),
            "APP_ADMIN_PASSWORD": b64(app_admin_password),
            # Per-tenant support-user password (may be empty — odoo-init skips
            # creating the support user when blank).
            "SUPPORT_PASSWORD": b64(support_password),
        },
    }


def git_secret_manifest(tenant_id: str, git_token: str) -> dict[str, Any]:
    """Per-tenant secret with GitHub PAT for cloning private addon repos."""
    import base64
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": "git-credentials",
            "namespace": _ns(tenant_id),
        },
        "type": "Opaque",
        "data": {
            "GIT_TOKEN": base64.b64encode(git_token.encode()).decode(),
        },
    }


def pg_credentials_secret_manifest(tenant_id: str, db_password: str) -> dict[str, Any]:
    """Credenciales del owner de la BD del tenant, consumidas por CNPG initdb.

    El portal sigue siendo la fuente de verdad del password (igual que en la
    topología external) — CNPG NO genera su propio secret pg-app cuando
    bootstrap.initdb.secret está presente, usa este. Así odoo-secret,
    odoo.conf y todo el flujo aguas abajo no cambian entre topologías.
    """
    import base64
    def b64(s: str) -> str:
        return base64.b64encode(s.encode()).decode()
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": "pg-app-user",
            "namespace": _ns(tenant_id),
        },
        "type": "kubernetes.io/basic-auth",
        "data": {
            "username": b64(f"odoo-{tenant_id}"),
            "password": b64(db_password),
        },
    }


def pg_cluster_manifest(tenant_id: str) -> dict[str, Any]:
    """Instancia PostgreSQL single del tenant (CloudNativePG, PG_TOPOLOGY=cnpg).

    1 instancia, sin standby — decisión de arquitectura (Patroni HA descartado;
    el RTO es el re-schedule del pod sobre su réplica Longhorn). Sizing por
    tenant según docs/CLOUD-STRATEGY-2026-08.md §3: 250m/512Mi req=lim
    (QoS Guaranteed, regla CNPG shared_buffers 128MB ⇒ 512Mi de contenedor).
    Servicios que crea el operador: pg-rw / pg-ro / pg-r en el namespace.
    """
    return {
        "apiVersion": "postgresql.cnpg.io/v1",
        "kind": "Cluster",
        "metadata": {
            "name": "pg",
            "namespace": _ns(tenant_id),
            "labels": {"app": "pg", "tenant": tenant_id},
        },
        "spec": {
            "instances": 1,
            "imageName": CNPG_IMAGE,
            "bootstrap": {
                "initdb": {
                    "database": _dbname(tenant_id),
                    "owner": f"odoo-{tenant_id}",
                    "secret": {"name": "pg-app-user"},
                }
            },
            "storage": {
                "size": f"{CNPG_STORAGE_GI}Gi",
                "storageClass": STORAGE_CLASS,
            },
            "resources": {
                "requests": {"cpu": "250m", "memory": "512Mi"},
                "limits": {"cpu": "250m", "memory": "512Mi"},
            },
            "enableSuperuserAccess": False,
        },
    }


def pg_cilium_apiserver_policy_manifest(tenant_id: str) -> dict[str, Any]:
    """Egress al API server para los pods CNPG del tenant (solo PG_TOPOLOGY=cnpg).

    El instance-manager de CNPG necesita leer su Cluster CR del API server al
    arrancar. Con Cilium, el ipBlock 0.0.0.0/0:443 de la NetworkPolicy NO cubre
    la ClusterIP del API server (identidad de clúster, DNAT a nodo:6443 antes
    de evaluar la política) — mismo motivo por el que existe
    k8s/00b-cilium-apiserver-egress.yaml para el portal. Confirmado en vivo en
    cotas-staging: sin esto, el job initdb muere con "dial tcp 10.43.0.1:443:
    i/o timeout". Scoped SOLO a los pods del Cluster pg — los pods Odoo del
    tenant siguen sin poder hablar con el API server.
    """
    return {
        "apiVersion": "cilium.io/v2",
        "kind": "CiliumNetworkPolicy",
        "metadata": {
            "name": "pg-egress-kube-apiserver",
            "namespace": _ns(tenant_id),
        },
        "spec": {
            "endpointSelector": {"matchLabels": {"cnpg.io/cluster": "pg"}},
            "egress": [{"toEntities": ["kube-apiserver"]}],
        },
    }


def configmap_manifest(tenant_id: str, db_password: str, admin_password: str, addons_repos: list = None, plan: str = "starter") -> dict[str, Any]:
    """Odoo config file per tenant — passwords are embedded at provision time."""
    db_name = _dbname(tenant_id)
    addons_repos = addons_repos or []
    import json
    addons_json_str = json.dumps(addons_repos)

    res = PLAN_RESOURCES.get(plan, PLAN_RESOURCES["starter"])
    db_host, db_port = _db_endpoint(tenant_id)

    # /mnt/extra-addons is always included: the clone-addons init container
    # (see deployment_manifest) guarantees it's never an empty/invalid addons
    # dir — it drops a placeholder module (installable: False) when no repos
    # are configured. This must stay unconditional so that addon repos added
    # LATER via the "Sync Addons to Instance" button (PATCH /config, which
    # only ever touches addons.json, never re-renders odoo.conf) actually
    # take effect — otherwise Odoo never sees the cloned modules at all
    # regardless of "Update Apps List". See DEPLOY.md incident 2026-07-10.
    #
    # limit_time_*: sin esto Odoo usa el default limit_time_real=120s, y con
    # workers>0 el master MATA al worker HTTP a los 120s. Instalar varias apps
    # a la vez (11 apps + dependencias > 120s) hace que el worker muera a media
    # carga del grafo y los módulos que no alcanzaron a commitear quedan en
    # estado "to install" — genera tickets de soporte innecesarios. Confirmado
    # en vivo (tenant SUB00259, 2026-08-10: "WorkerHTTP timeout after 120s").
    # 1200s real deja terminar instalaciones batch grandes; el commit del
    # install ocurre server-side aunque el browser corte antes (Cloudflare ~100s).
    conf = f"""[options]
db_host = {db_host}
db_port = {db_port}
db_user = odoo-{tenant_id}
db_password = {db_password}
admin_passwd = {admin_password}
db_name = {db_name}
dbfilter = ^{db_name}$
list_db = False
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons
data_dir = /var/lib/odoo
workers = {res["workers"]}
max_cron_threads = {res["cron_threads"]}
gevent_port = 8072
proxy_mode = True
without_demo = True
limit_time_cpu = 600
limit_time_real = 1200
limit_time_real_cron = 1800
"""
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": "odoo-conf",
            "namespace": _ns(tenant_id),
        },
        "data": {
            "odoo.conf": conf,
            "addons.json": addons_json_str
        },
    }



def deployment_manifest(tenant_id: str, odoo_version: str = "18.0", custom_image: str | None = None, plan: str = "starter", install_modules: str = "") -> dict[str, Any]:
    pg_user = f"odoo-{tenant_id}"
    db_name = _dbname(tenant_id)
    db_host, db_port = _db_endpoint(tenant_id)
    active_image = custom_image if custom_image else f"odoo:{odoo_version}"
    res = PLAN_RESOURCES.get(plan, PLAN_RESOURCES["starter"])
    init_modules = f"base,{install_modules}" if install_modules else "base"
    # Shared volume mounts and env used by both init and main containers
    _vol_mounts = [
        {"name": "odoo-conf", "mountPath": "/etc/odoo"},
        {"name": "odoo-data", "mountPath": "/var/lib/odoo"},
        {"name": "odoo-extra-addons", "mountPath": "/mnt/extra-addons"},
    ]
    _env = [
        {"name": "DB_PASSWORD", "valueFrom": {"secretKeyRef": {"name": "odoo-secret", "key": "DB_PASSWORD"}}},
        {"name": "APP_ADMIN_PASSWORD", "valueFrom": {"secretKeyRef": {"name": "odoo-secret", "key": "APP_ADMIN_PASSWORD"}}},
        {"name": "HOST",     "value": db_host},
        {"name": "PORT",     "value": str(db_port)},
        {"name": "USER",     "value": pg_user},
        {"name": "PASSWORD", "valueFrom": {"secretKeyRef": {"name": "odoo-secret", "key": "DB_PASSWORD"}}},
        # TCP keepalives — prevent HAProxy from dropping idle connections (default 30min timeout).
        # psycopg2/libpq reads PGKEEPALIVES* automatically without any Odoo config changes.
        {"name": "PGKEEPALIVES",          "value": "1"},
        {"name": "PGKEEPALIVES_IDLE",     "value": "60"},   # send keepalive after 60s idle
        {"name": "PGKEEPALIVES_INTERVAL", "value": "10"},   # retry every 10s
        {"name": "PGKEEPALIVES_COUNT",    "value": "5"},    # fail after 5 missed keepalives
    ]
    # Init env — same port since PgBouncer was removed
    _init_env = [
        {"name": "DB_PASSWORD", "valueFrom": {"secretKeyRef": {"name": "odoo-secret", "key": "DB_PASSWORD"}}},
        {"name": "APP_ADMIN_PASSWORD", "valueFrom": {"secretKeyRef": {"name": "odoo-secret", "key": "APP_ADMIN_PASSWORD"}}},
        {"name": "HOST",     "value": db_host},
        {"name": "PORT",     "value": str(db_port)},
        {"name": "USER",     "value": pg_user},
        {"name": "PASSWORD", "valueFrom": {"secretKeyRef": {"name": "odoo-secret", "key": "DB_PASSWORD"}}},
        # First-boot bootstrap (see first_boot.py heredoc in odoo-init below)
        {"name": "TENANT_LANG",   "value": TENANT_DEFAULT_LANG},
        {"name": "TENANT_BASE_URL", "value": f"{URL_SCHEME}://{tenant_id}.{BASE_DOMAIN}"},
        {"name": "SUPPORT_LOGIN", "value": SUPPORT_USER_LOGIN},
        {"name": "SUPPORT_PASSWORD", "valueFrom": {"secretKeyRef": {"name": "odoo-secret", "key": "SUPPORT_PASSWORD"}}},
    ]
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "odoo",
            "namespace": _ns(tenant_id),
            "labels": {"app": "odoo", "tenant": tenant_id},
        },
        "spec": {
            "replicas": 1,
            "strategy": {"type": "Recreate"},
            "selector": {"matchLabels": {"app": "odoo"}},
            "template": {
                "metadata": {"labels": {"app": "odoo", "tenant": tenant_id}},
                "spec": {
                    "initContainers": [
                        # 1. Clone custom addons from git repos listed in addons.json
                        {
                            "name": "clone-addons",
                            "image": "python:3.10-alpine",
                            "command": ["/bin/sh", "-c"],
                            "args": [
                                "apk add --no-cache git && python3 -c '\n"
                                "import json, os, subprocess\n"
                                "git_token = os.environ.get(\"GIT_TOKEN\", \"\")\n"
                                "try:\n"
                                "    with open(\"/etc/odoo/addons.json\") as f:\n"
                                "        addons = json.load(f)\n"
                                "except Exception:\n"
                                "    addons = []\n"
                                "os.makedirs(\"/mnt/extra-addons/.repos\", exist_ok=True)\n"
                                "os.makedirs(\"/mnt/extra-addons\", exist_ok=True)\n"
                                "for repo in addons:\n"
                                "    url = repo.get(\"url\")\n"
                                "    branch = repo.get(\"branch\", \"\")\n"
                                "    if not url: continue\n"
                                "    if git_token and url.startswith(\"https://github.com/\"):\n"
                                "        url = url.replace(\"https://\", f\"https://{git_token}@\", 1)\n"
                                "    repo_name = url.rstrip(\"/\").rsplit(\"/\", 1)[-1]\n"
                                "    if repo_name.endswith(\".git\"): repo_name = repo_name[:-4]\n"
                                "    temp_dest = f\"/mnt/extra-addons/.repos/{repo_name}\"\n"
                                "    cmd = [\"git\", \"clone\", \"--depth=1\"]\n"
                                "    if branch:\n"
                                "        cmd.extend([\"-b\", branch])\n"
                                "    cmd.extend([url, temp_dest])\n"
                                "    print(f\"Cloning {url} into {temp_dest}...\")\n"
                                "    if not os.path.exists(temp_dest):\n"
                                "        subprocess.run(cmd, check=True)\n"
                                "    is_single = False\n"
                                "    for filename in [\"__manifest__.py\", \"__openerp__.py\"]:\n"
                                "        if os.path.exists(os.path.join(temp_dest, filename)):\n"
                                "            is_single = True\n"
                                "            break\n"
                                "    if is_single:\n"
                                "        dest = f\"/mnt/extra-addons/{repo_name}\"\n"
                                "        if not os.path.exists(dest):\n"
                                "            os.symlink(temp_dest, dest)\n"
                                "    else:\n"
                                "        for item in os.listdir(temp_dest):\n"
                                "            item_path = os.path.join(temp_dest, item)\n"
                                "            if os.path.isdir(item_path):\n"
                                "                is_sub = False\n"
                                "                for filename in [\"__manifest__.py\", \"__openerp__.py\"]:\n"
                                "                    if os.path.exists(os.path.join(item_path, filename)):\n"
                                "                        is_sub = True\n"
                                "                        break\n"
                                "                if is_sub:\n"
                                "                    dest = f\"/mnt/extra-addons/{item}\"\n"
                                "                    if not os.path.exists(dest):\n"
                                "                        os.symlink(item_path, dest)\n"
                                "' && "
                                "if [ -z \"$(ls -A /mnt/extra-addons 2>/dev/null)\" ]; then "
                                "  mkdir -p /mnt/extra-addons/_placeholder && "
                                "  touch /mnt/extra-addons/_placeholder/__init__.py && "
                                "  printf \"{'name': 'Extra Addons Placeholder', 'version': '1.0', 'installable': False}\\n\" "
                                "    > /mnt/extra-addons/_placeholder/__manifest__.py; "
                                "fi && "
                                "chown -R 101:101 /mnt/extra-addons"
                            ],
                            "env": [
                                {
                                    "name": "GIT_TOKEN",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": "git-credentials",
                                            "key": "GIT_TOKEN",
                                            "optional": True,
                                        }
                                    },
                                }
                            ],
                            "volumeMounts": _vol_mounts,
                            "securityContext": {
                                "runAsUser": 0,
                                "runAsNonRoot": False,
                            },
                        },
                        # 2. Wait for PostgreSQL HA to be reachable before attempting DB init.
                        #    Prevents CrashLoopBackOff caused by DNS timeout on early pod startup.
                        {
                            "name": "wait-for-postgres",
                            "image": "busybox:1.36",
                            "command": ["/bin/sh", "-c"],
                            "args": [
                                f"echo 'Waiting for PostgreSQL at {db_host}:{db_port}...'; "
                                f"until nc -z {db_host} {db_port}; do "
                                "  echo 'PostgreSQL not ready, retrying in 3s...'; sleep 3; "
                                "done; "
                                "echo 'PostgreSQL is ready.'"
                            ],
                        },
                        # 3. Bootstrap DB schema on first start; skip if DB already exists
                        #    (idempotent — safe on CrashLoopBackOff restarts, avoids 45-120s
                        #    re-init overhead that was causing 58-60 restart cycles).
                        {
                            "name": "odoo-init",
                            "image": active_image,
                            "imagePullPolicy": "Always",
                            "command": ["/bin/sh", "-c"],
                            "args": [
                                # Product images (aei-custom-odoo-images 19.0+) bake the AEI
                                # localization at /opt/aei-addons and inject it into the addons
                                # path via their ENTRYPOINT (/entrypoint-custom.sh) — which only
                                # the MAIN container goes through. This init container invokes
                                # `odoo` directly, so it must build the same addons path itself;
                                # otherwise --init/update_list can't see the baked modules
                                # (SUB00262 2026-08-12: l10n_bo_core absent from ir_module_module).
                                # Runtime detection keeps plain odoo:XX.0 images working.
                                "AEI_ADDONS_PATH='/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons'; "
                                "if [ -d /opt/aei-addons ]; then "
                                "  AEI_ADDONS_PATH=\"/opt/aei-addons,$AEI_ADDONS_PATH\"; "
                                "fi; "
                                "echo \"odoo-init: addons_path=$AEI_ADDONS_PATH\"; "
                                # Check if Odoo schema exists (not just the DB) by looking for
                                # ir_module_module. A freshly created empty DB would pass the
                                # old "SELECT FROM pg_database" check but still need --init=base.
                                f"DB_INIT=$(PGPASSWORD=$DB_PASSWORD psql "
                                f"-h {db_host} -p {db_port} "
                                f"-U {pg_user} -d {db_name} -tAc "
                                "\"SELECT 1 FROM information_schema.tables "
                                "WHERE table_schema='public' AND table_name='ir_module_module'\" "
                                f"2>/dev/null || true); "
                                "if [ \"$DB_INIT\" = \"1\" ]; then "
                                f"  echo 'DB {db_name} already has Odoo schema, skipping --init={init_modules}'; "
                                "else "
                                # Product images from 19.0 on ship a pre-seeded master DB at
                                # /opt/aei-master (see aei-custom-odoo-images 19.0/build-master-db.sh).
                                # Restoring it is both faster (~30s vs ~5min) and the only way to get
                                # the Bolivian chart of accounts: Odoo 19 picks the chart in
                                # account/models/ir_module.py::write(), and on a company with no
                                # country the `or tname == 'generic_coa'` branch always wins — which
                                # also pins account_fiscal_country_id to base.us and the currency to
                                # USD (SUB00263/264, 2026-08-12). The master DB was seeded with the
                                # country set BEFORE `account` was installed, so it carries chart
                                # 'bo' / BOB. Images without the dump keep the --init path.
                                "  if [ -f /opt/aei-master/master.sql.gz ]; then "
                                f"    echo 'Seeding DB {db_name} from baked master template...'; "
                                f"    gunzip -c /opt/aei-master/master.sql.gz | PGPASSWORD=$DB_PASSWORD psql -q "
                                f"      -h {db_host} -p {db_port} -U {pg_user} -d {db_name} "
                                "      -v ON_ERROR_STOP=1 > /dev/null "
                                "    && echo 'master-restore: schema+data done' "
                                "    || echo 'master-restore: FAILED — tenant DB may be incomplete'; "
                                # The master filestore is small (~1 MB) but not optional: a fresh
                                # Odoo DB already references ~530 files from ir_attachment (payment
                                # method icons, menu icons, avatars, language flags). Skipping it
                                # leaves those images broken in the tenant.
                                "    if [ -f /opt/aei-master/filestore.tar.gz ]; then "
                                f"      mkdir -p /var/lib/odoo/filestore/{db_name} "
                                f"      && tar xzf /opt/aei-master/filestore.tar.gz -C /var/lib/odoo/filestore/{db_name} "
                                "      && echo 'master-restore: filestore done' "
                                "      || echo 'master-restore: filestore FAILED — broken images in tenant'; "
                                "    fi; "
                                # The baked modules are frozen at image build time, but the addons in
                                # /mnt/extra-addons are git-cloned at provision time and can be newer.
                                # Upgrade only those whose on-disk version differs — a full -u all
                                # would cost minutes and touch modules that never changed.
                                "    cat > /tmp/sync_addons.py <<'PYEOF'\n"
                                "import os\n"
                                "from odoo.modules.module import Manifest\n"
                                "stale = []\n"
                                "for mod in env['ir.module.module'].sudo().search([('state', '=', 'installed')]):\n"
                                "    try:\n"
                                "        manifest = Manifest.for_addon(mod.name, display_warning=False)\n"
                                "    except Exception:\n"
                                "        manifest = None\n"
                                "    on_disk = manifest and manifest.get('version')\n"
                                "    if on_disk and mod.latest_version and on_disk != mod.latest_version:\n"
                                "        stale.append(mod.name)\n"
                                "print('sync-addons: stale=%s' % (','.join(stale) or 'none'))\n"
                                "PYEOF\n"
                                "    STALE=$(odoo shell --config=/etc/odoo/odoo.conf "
                                "      --addons-path=\"$AEI_ADDONS_PATH\" --no-http < /tmp/sync_addons.py 2>/dev/null "
                                "      | sed -n 's/^sync-addons: stale=//p' | tail -1); "
                                "    if [ -n \"$STALE\" ] && [ \"$STALE\" != 'none' ]; then "
                                "      echo \"odoo-init: upgrading drifted addons: $STALE\"; "
                                "      odoo --config=/etc/odoo/odoo.conf --update=\"$STALE\" "
                                "        --addons-path=\"$AEI_ADDONS_PATH\" --stop-after-init "
                                "      || echo 'sync-addons: FAILED — drifted addons kept their DB version'; "
                                "    fi; "
                                # Modules the product asks for that the template doesn't carry.
                                f"    MISSING=$(PGPASSWORD=$DB_PASSWORD psql -h {db_host} -p {db_port} "
                                f"      -U {pg_user} -d {db_name} -tAc \""
                                f"SELECT string_agg(m, ',') FROM unnest(string_to_array('{init_modules}', ',')) AS m "
                                "WHERE m NOT IN (SELECT name FROM ir_module_module WHERE state='installed')\" "
                                "      2>/dev/null || true); "
                                "    if [ -n \"$MISSING\" ]; then "
                                "      echo \"odoo-init: installing modules missing from template: $MISSING\"; "
                                "      odoo --config=/etc/odoo/odoo.conf --init=\"$MISSING\" "
                                "        --addons-path=\"$AEI_ADDONS_PATH\" "
                                f"        --load-language={TENANT_DEFAULT_LANG} --stop-after-init "
                                "      || echo 'odoo-init: WARNING extra --init exited non-zero'; "
                                "    fi; "
                                "  else "
                                "    echo 'Initializing Odoo schema for the first time...'; "
                                f"    odoo --config=/etc/odoo/odoo.conf --init={init_modules} "
                                "      --addons-path=\"$AEI_ADDONS_PATH\" "
                                f"      --load-language={TENANT_DEFAULT_LANG} --stop-after-init "
                                "    || echo 'odoo-init: WARNING --init exited non-zero; attempting first-boot anyway'; "
                                "  fi; "
                                # First-boot bootstrap: set admin password, default language
                                # (TENANT_LANG for existing + future users/partners) and create
                                # the per-instance support user (skipped if SUPPORT_PASSWORD is
                                # empty). Heredoc is quoted ('PYEOF') so the shell does NOT
                                # expand anything — the script reads env vars via os.environ,
                                # which is also safe for passwords with special characters.
                                #
                                # ⚠️ odoo shell exec()s piped stdin as ONE block: any exception
                                # aborts the WHOLE script, including earlier writes and the final
                                # commit (SUB00262/263 2026-08-12: Odoo 19 renamed res.users
                                # groups_id -> group_ids; the ValueError on the support-user
                                # create rolled back the admin password too, so the credentials
                                # email carried a password that was never applied while the
                                # tenant kept admin/admin). Hence the version-agnostic
                                # groups_field lookup and the loud '|| echo FAILED' below —
                                # never let this step fail silently again.
                                "  cat > /tmp/first_boot.py <<'PYEOF'\n"
                                "import os, secrets, uuid\n"
                                # De-cloning FIRST, before anything touches res.users: when the DB
                                # comes from the baked master template every tenant would otherwise
                                # share database.uuid (instance identity) and database.secret (the
                                # key sessions and access tokens are signed with). The master dump
                                # ships without them, and Odoo does NOT lazily recreate database.secret
                                # — creating a user with it missing dies in tools.misc.hmac with
                                # "TypeError: secret must be a str or bytes" (avatar access token).
                                # Harmless on the --init path: they were just generated, we replace them.
                                "ICP = env['ir.config_parameter'].sudo()\n"
                                "ICP.set_param('database.uuid', str(uuid.uuid4()))\n"
                                "ICP.set_param('database.secret', secrets.token_hex(32))\n"
                                "env.cr.commit()\n"
                                "lang = os.environ.get('TENANT_LANG') or 'es_BO'\n"
                                "env['res.lang']._activate_lang(lang)\n"
                                "env['res.users'].with_context(active_test=False).search([]).write({'lang': lang})\n"
                                "env['res.partner'].with_context(active_test=False).search([]).write({'lang': lang})\n"
                                "env['ir.default'].set('res.partner', 'lang', lang)\n"
                                "env.ref('base.user_admin').write({'password': os.environ['APP_ADMIN_PASSWORD']})\n"
                                "support_pwd = os.environ.get('SUPPORT_PASSWORD')\n"
                                "support_login = os.environ.get('SUPPORT_LOGIN') or 'soporte@aeisoftware.com'\n"
                                "Users = env['res.users'].with_context(active_test=False)\n"
                                "if support_pwd and not Users.search([('login', '=', support_login)]):\n"
                                "    groups_field = 'group_ids' if 'group_ids' in Users._fields else 'groups_id'\n"
                                "    Users.create({\n"
                                "        'name': 'Soporte AEI',\n"
                                "        'login': support_login,\n"
                                "        'email': support_login,\n"
                                "        'password': support_pwd,\n"
                                "        'lang': lang,\n"
                                "        groups_field: [(6, 0, [env.ref('base.group_user').id, env.ref('base.group_system').id])],\n"
                                "    })\n"
                                "    print('first-boot: support user created')\n"
                                # Without web.base.url Odoo derives links from whatever host the
                                # first request carried, which is how password-reset mails ended up
                                # pointing at internal hosts. Freeze it to the tenant's own URL.
                                "base_url = os.environ.get('TENANT_BASE_URL')\n"
                                "if base_url:\n"
                                "    ICP.set_param('web.base.url', base_url)\n"
                                "    ICP.set_param('web.base.url.freeze', 'True')\n"
                                "    print('first-boot: web.base.url=%s' % base_url)\n"
                                "env.cr.commit()\n"
                                "print('first-boot: lang=%s applied' % lang)\n"
                                "PYEOF\n"
                                "  odoo shell --config=/etc/odoo/odoo.conf --addons-path=\"$AEI_ADDONS_PATH\" --no-http < /tmp/first_boot.py "
                                "  || echo 'first-boot: FAILED — tenant credentials NOT applied'; "
                                "fi; "
                                # Flush cached asset bundles on every start (not just first boot).
                                # With imagePullPolicy=Always the running Odoo build can legitimately
                                # change between restarts; stale ir.attachment rows compiled by a
                                # different build can register core Owl templates (e.g. mail.Thread)
                                # with mismatched content and break "loadBundle" bundles like
                                # portal.assets_chatter (Missing template errors). Assets recompile
                                # automatically on next request, so this is always safe.
                                f"PGPASSWORD=$DB_PASSWORD psql -h {db_host} -p {db_port} "
                                f"-U {pg_user} -d {db_name} "
                                "-c \"DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'\" "
                                "2>/dev/null || echo 'flush-asset-cache: skipped (DB not ready yet)'; "
                                # Refresh the addon module list on every start (not just first
                                # boot). Needed for "Sync Addons to Instance" (routers/instances.py
                                # patch_instance_config): repos get cloned into /mnt/extra-addons
                                # and the pod restarts, but Odoo never auto-discovers new module
                                # folders on disk — normally someone has to enable developer mode
                                # and click "Update Apps List" by hand. update_list() only
                                # registers/refreshes ir.module.module rows; it does NOT install
                                # anything (a repo can carry many modules — installing the right
                                # one is a deliberate follow-up action, not automatic). See
                                # DEPLOY.md incident 2026-07-10.
                                "echo \"env['ir.module.module'].update_list(); env.cr.commit()\" "
                                "| odoo shell --config=/etc/odoo/odoo.conf --addons-path=\"$AEI_ADDONS_PATH\" --no-http "
                                "|| echo 'update-apps-list: skipped (DB not ready yet)'"
                            ],
                            "env": _init_env,
                            "volumeMounts": _vol_mounts,
                        },
                    ],
                    "affinity": {
                        "nodeAffinity": {
                            # Prefer worker nodes (labelled workload=tenant by 07-join-k3s-workers.sh).
                            # Soft preference — falls back to control-plane if workers are full.
                            "preferredDuringSchedulingIgnoredDuringExecution": [
                                {
                                    "weight": 100,
                                    "preference": {
                                        "matchExpressions": [
                                            {
                                                "key": "workload",
                                                "operator": "In",
                                                "values": ["tenant"],
                                            }
                                        ]
                                    },
                                }
                            ]
                        }
                    },
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 101,
                        "fsGroup": 101,
                    },
                    "containers": [
                        {
                            "name": "odoo",
                            "image": active_image,
                            "imagePullPolicy": "Always",
                            "args": ["--config=/etc/odoo/odoo.conf"],
                            "ports": [
                                {"containerPort": 8069},
                                {"containerPort": 8072},
                            ],
                            "env": _env,
                            "volumeMounts": _vol_mounts,
                            # startupProbe gives Odoo up to 10 min for the first boot
                            # (module loading + ORM init can take 2-5 min).
                            # Once it passes, livenessProbe takes over with strict timing.
                            "startupProbe": {
                                "httpGet": {"path": "/web/health", "port": 8069},
                                "failureThreshold": 30,
                                "periodSeconds": 20,
                            },
                            "livenessProbe": {
                                "httpGet": {"path": "/web/health", "port": 8069},
                                "periodSeconds": 30,
                                "failureThreshold": 3,
                            },
                            "readinessProbe": {
                                "httpGet": {"path": "/web/health", "port": 8069},
                                "periodSeconds": 15,
                                "failureThreshold": 40,
                            },
                            "resources": {
                                "requests": {"cpu": res["cpu_req"], "memory": res["mem_req"]},
                                "limits":   {"cpu": res["cpu_lim"], "memory": res["mem_lim"]},
                            },
                        }
                    ],
                    "volumes": [
                        {"name": "odoo-conf", "configMap": {"name": "odoo-conf"}},
                        {"name": "odoo-data", "persistentVolumeClaim": {"claimName": "odoo-data"}},
                        {"name": "odoo-extra-addons", "emptyDir": {}},
                    ],
                },
            },
        },
    }


def network_policy_manifest(tenant_id: str) -> dict[str, Any]:
    """Isolate tenant namespace: deny all, allow Traefik for 8069/8072 and Postgres for 5432."""
    ns = _ns(tenant_id)
    ingress = [
        {   # Allow Ingress Controller (Traefik)
            "from": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}}}],
            "ports": [{"protocol": "TCP", "port": 8069}, {"protocol": "TCP", "port": 8072}]
        },
        {   # Allow Portal FastAPI → backup endpoint (prod: aeisoftware, staging: staging)
            "from": [
                {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "aeisoftware"}}},
                {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "staging"}}},
            ],
            "ports": [{"protocol": "TCP", "port": 8069}]
        }
    ]
    egress = [
        {   # DNS
            "to": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "kube-system"}}, "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}}}],
            "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}]
        },
        {   # GitHub addons HTTPS
            "to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}],
            "ports": [{"protocol": "TCP", "port": 443}]
        }
    ]
    if PG_TOPOLOGY == "cnpg":
        # Postgres vive DENTRO del namespace (pods del Cluster CNPG "pg"):
        ingress += [
            {   # odoo (y cualquier pod del tenant) → pg :5432, intra-namespace
                "from": [{"podSelector": {}}],
                "ports": [{"protocol": "TCP", "port": 5432}]
            },
            {   # Operador CNPG (status/instance-manager :8000 + mantenimiento :5432)
                "from": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "cnpg-system"}}}],
                "ports": [{"protocol": "TCP", "port": 8000}, {"protocol": "TCP", "port": 5432}]
            },
            {   # Portal → pg :5432 (sync de user-count, health checks)
                "from": [
                    {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "aeisoftware"}}},
                    {"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "staging"}}},
                ],
                "ports": [{"protocol": "TCP", "port": 5432}]
            },
        ]
        egress += [
            {   # odoo → pg intra-namespace
                "to": [{"podSelector": {}}],
                "ports": [{"protocol": "TCP", "port": 5432}]
            },
        ]
    else:
        egress += [
            {   # Service postgres en aeisoftware (ClusterIP → Endpoints → HAProxy)
                "to": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "aeisoftware"}}}],
                "ports": [
                    {"protocol": "TCP", "port": POSTGRES_PORT},
                ]
            },
            {   # Egress directo a la red del clúster PG externo
                "to": [{"ipBlock": {"cidr": PG_NETWORK_CIDR}}],
                "ports": [
                    {"protocol": "TCP", "port": POSTGRES_PORT},
                ]
            },
        ]
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": "tenant-isolation", "namespace": ns},
        "spec": {
            "podSelector": {},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": ingress,
            "egress": egress,
        }
    }


def service_manifest(tenant_id: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": "odoo", "namespace": _ns(tenant_id)},
        "spec": {
            "selector": {"app": "odoo"},
            "ports": [
                {"name": "http", "port": 8069, "targetPort": 8069},
                {"name": "longpoll", "port": 8072, "targetPort": 8072},
            ],
        },
    }


def ingress_manifest(tenant_id: str) -> dict[str, Any]:
    """Standard K8s Ingress for Traefik."""
    subdomain = tenant_id  # e.g. demo → demo.aeisoftware.com
    annotations = {
        "traefik.ingress.kubernetes.io/router.entrypoints": "web,websecure",
        "traefik.ingress.kubernetes.io/router.middlewares": f"{ODOO_HEADERS_MIDDLEWARE},{SECURITY_HEADERS_MIDDLEWARE}",
    }

    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {
            "name": "odoo-ingress",
            "namespace": _ns(tenant_id),
            "annotations": annotations,
        },
        "spec": {
            "ingressClassName": "traefik",
            "rules": [
                {
                    "host": f"{subdomain}.{BASE_DOMAIN}",
                    "http": {
                        "paths": [
                            {
                                "path": "/websocket",
                                "pathType": "Prefix",
                                "backend": {"service": {"name": "odoo", "port": {"number": 8072}}},
                            },
                            {
                                "path": "/",
                                "pathType": "Prefix",
                                "backend": {"service": {"name": "odoo", "port": {"number": 8069}}},
                            },
                        ]
                    },
                }
            ],
        },
    }


def limitrange_manifest(tenant_id: str) -> dict[str, Any]:
    """Default resource limits for containers that don't declare them explicitly.

    Primarily protects against runaway init containers (clone-addons, wait-for-postgres,
    odoo-init) which have no explicit resources in the Deployment spec.
    The main odoo container has explicit limits and is not affected by these defaults.
    """
    return {
        "apiVersion": "v1",
        "kind": "LimitRange",
        "metadata": {
            "name": "tenant-limits",
            "namespace": _ns(tenant_id),
        },
        "spec": {
            "limits": [
                {
                    "type": "Container",
                    "default": {
                        "cpu": "500m",
                        "memory": "512Mi",
                    },
                    "defaultRequest": {
                        "cpu": "50m",
                        "memory": "128Mi",
                    },
                }
            ]
        },
    }


def resourcequota_manifest(tenant_id: str, plan: str = "starter", storage_gi: int = 10) -> dict[str, Any]:
    """Namespace-level ceiling per plan tier — EL TECHO VENDIBLE del tenant.

    Nueva arquitectura (docs/CLOUD-STRATEGY-2026-08.md §2): el namespace es el
    producto, y esta quota es su techo contractual. Cubre TODO lo que corre en
    el namespace del tenant: el pod Odoo, el pod del AI agent (default en todos
    los tenants) y — con PG_TOPOLOGY=cnpg — su instancia Postgres propia.

    - `requests.storage` suma los tamaños SOLICITADOS de todos los PVC del
      namespace (odoo-data + agent-workspace + PVC de pg). Con Longhorn
      thin-provisioned nada de esto se reserva por adelantado: el techo existe,
      el uso real es el que ocupa disco. Caveat honesto: la quota limita lo
      solicitado, no el uso vivo dentro de un PVC ya creado.
    - `limits.cpu/memory` es el techo de cómputo del namespace completo —
      dimensionado para odoo+agent+pg más el overlap transitorio de un rollout
      y los init containers (que toman defaults del LimitRange).
    """
    _quotas = {
        "starter":    {"cpu": "4",  "memory": "6Gi"},
        "pro":        {"cpu": "6",  "memory": "10Gi"},
        "enterprise": {"cpu": "8",  "memory": "16Gi"},
    }
    q = _quotas.get(plan, _quotas["starter"])
    storage_ceiling = storage_gi + AGENT_WORKSPACE_GI
    if PG_TOPOLOGY == "cnpg":
        storage_ceiling += CNPG_STORAGE_GI
    return {
        "apiVersion": "v1",
        "kind": "ResourceQuota",
        "metadata": {
            "name": "tenant-quota",
            "namespace": _ns(tenant_id),
        },
        "spec": {
            "hard": {
                "limits.cpu":    q["cpu"],
                "limits.memory": q["memory"],
                # Techo de storage del namespace = suma de todos sus PVCs.
                "requests.storage": f"{storage_ceiling}Gi",
                # odoo-data + agent-workspace + pg + 1 margen para PVCs en
                # Terminating durante ciclos disable/enable del agente.
                "persistentvolumeclaims": "4",
                # odoo (x2 en rollout) + agent (x2) + pg + job initdb de CNPG
                "pods": "8",
                "services": "8",   # odoo + agent + pg-r/-ro/-rw
                "secrets": "15",   # odoo/git/agent + pg-app-user + los TLS de CNPG
                "configmaps": "8",
            }
        },
    }


def pdb_manifest(tenant_id: str) -> dict[str, Any]:
    """PodDisruptionBudget for the tenant Odoo pod.

    minAvailable: 1 means kubectl drain cannot voluntarily evict this pod
    unless a replacement is already running. With replicas=1, this results in
    ALLOWED DISRUPTIONS=0 — the pod is protected from accidental eviction
    during node maintenance. The admin must explicitly scale=0 or delete the
    PDB before draining a node that hosts this tenant.
    """
    return {
        "apiVersion": "policy/v1",
        "kind": "PodDisruptionBudget",
        "metadata": {
            "name": "odoo-pdb",
            "namespace": _ns(tenant_id),
        },
        "spec": {
            "minAvailable": 1,
            "selector": {
                "matchLabels": {"app": "odoo"},
            },
        },
    }


def agent_secret_manifest(tenant_id: str, webhook_secret: str) -> dict[str, Any]:
    """Platform-internal shared secret for the odoo<->agent HMAC channel.

    NOT the tenant's AI-provider API key — that's BYOK, entered by the
    tenant in Settings > AEI Assistant (saas_ai_agent addon) and fetched
    by the agent pod per-turn from GET /ai_agent/llm_config. This Secret
    only carries AGENT_WEBHOOK_SECRET, mirroring k8s/dev/agent-*.yaml.
    """
    import base64
    def b64(s: str) -> str:
        return base64.b64encode(s.encode()).decode()

    data = {"AGENT_WEBHOOK_SECRET": b64(webhook_secret)}
    if DEFAULT_LLM_API_KEY:
        data.update({
            "DEFAULT_LLM_PROVIDER": b64(DEFAULT_LLM_PROVIDER),
            "DEFAULT_LLM_API_KEY": b64(DEFAULT_LLM_API_KEY),
            "DEFAULT_LLM_BASE_URL": b64(DEFAULT_LLM_BASE_URL),
            "DEFAULT_LLM_MODEL": b64(DEFAULT_LLM_MODEL),
        })
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "agent-secret", "namespace": _ns(tenant_id)},
        "type": "Opaque",
        "data": data,
    }


def agent_pvc_manifest(tenant_id: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {"name": "agent-workspace", "namespace": _ns(tenant_id)},
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "storageClassName": STORAGE_CLASS,
            "resources": {"requests": {"storage": "1Gi"}},
        },
    }


def agent_deployment_manifest(tenant_id: str, plan: str = "starter") -> dict[str, Any]:
    res = AGENT_PLAN_RESOURCES.get(plan, AGENT_PLAN_RESOURCES["starter"])
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "agent",
            "namespace": _ns(tenant_id),
            "labels": {"app": "agent", "tenant": tenant_id},
        },
        "spec": {
            "replicas": 1,
            "strategy": {"type": "Recreate"},
            "selector": {"matchLabels": {"app": "agent"}},
            "template": {
                "metadata": {"labels": {"app": "agent", "tenant": tenant_id}},
                "spec": {
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 1000,
                        # Without fsGroup, the mounted PVC lands owned by
                        # root:root and the non-root `agent` user (uid 1000,
                        # baked into the image by Dockerfile's adduser)
                        # can't write to /data — verified live during the
                        # Phase 1 build as a real PermissionError.
                        "fsGroup": 1000,
                    },
                    "containers": [
                        {
                            "name": "agent",
                            "image": AGENT_IMAGE,
                            "imagePullPolicy": "Always",
                            "ports": [{"containerPort": 8000}],
                            "env": [
                                {"name": "ODOO_URL", "value": "http://odoo:8069"},
                                {"name": "AGENT_MAX_TURNS", "value": "12"},
                                {"name": "AGENT_MAX_BUDGET_USD", "value": "0.50"},
                                {"name": "SESSION_STORE_PATH", "value": "/data/sessions.json"},
                                {
                                    "name": "AGENT_WEBHOOK_SECRET",
                                    "valueFrom": {"secretKeyRef": {"name": "agent-secret", "key": "AGENT_WEBHOOK_SECRET"}},
                                },
                                # Optional: absent whenever DEFAULT_LLM_API_KEY isn't
                                # set platform-wide (agent_secret_manifest skips
                                # writing these keys entirely in that case) — the
                                # trial fallback is then simply unavailable, tenants
                                # go straight to "configure your own key".
                                {
                                    "name": "DEFAULT_LLM_PROVIDER",
                                    "valueFrom": {"secretKeyRef": {"name": "agent-secret", "key": "DEFAULT_LLM_PROVIDER", "optional": True}},
                                },
                                {
                                    "name": "DEFAULT_LLM_API_KEY",
                                    "valueFrom": {"secretKeyRef": {"name": "agent-secret", "key": "DEFAULT_LLM_API_KEY", "optional": True}},
                                },
                                {
                                    "name": "DEFAULT_LLM_BASE_URL",
                                    "valueFrom": {"secretKeyRef": {"name": "agent-secret", "key": "DEFAULT_LLM_BASE_URL", "optional": True}},
                                },
                                {
                                    "name": "DEFAULT_LLM_MODEL",
                                    "valueFrom": {"secretKeyRef": {"name": "agent-secret", "key": "DEFAULT_LLM_MODEL", "optional": True}},
                                },
                            ],
                            "volumeMounts": [{"name": "agent-workspace", "mountPath": "/data"}],
                            "resources": {
                                "requests": {"cpu": res["cpu_req"], "memory": res["mem_req"]},
                                "limits": {"cpu": res["cpu_lim"], "memory": res["mem_lim"]},
                            },
                            "readinessProbe": {
                                "httpGet": {"path": "/healthz", "port": 8000},
                                "initialDelaySeconds": 3, "periodSeconds": 10,
                            },
                            "livenessProbe": {
                                "httpGet": {"path": "/healthz", "port": 8000},
                                "initialDelaySeconds": 5, "periodSeconds": 20,
                            },
                        }
                    ],
                    "volumes": [
                        {"name": "agent-workspace", "persistentVolumeClaim": {"claimName": "agent-workspace"}},
                    ],
                },
            },
        },
    }


def agent_service_manifest(tenant_id: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": "agent", "namespace": _ns(tenant_id)},
        "spec": {
            "selector": {"app": "agent"},
            "ports": [{"name": "http", "port": 8000, "targetPort": 8000}],
        },
    }


def agent_network_policy_manifest(tenant_id: str) -> dict[str, Any]:
    """Supplementary to `network_policy_manifest` (K8s NetworkPolicies are
    additive across objects selecting the same pods) — adds the
    intra-namespace odoo<->agent traffic that the base tenant-isolation
    policy doesn't grant (it only allows ingress from other namespaces).
    Applied only when the AI agent add-on is enabled; deleted alongside
    the other agent resources on disable.
    """
    ns = _ns(tenant_id)
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": "agent-isolation", "namespace": ns},
        "spec": {
            "podSelector": {},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [
                {"from": [{"podSelector": {"matchLabels": {"app": "odoo"}}}], "ports": [{"protocol": "TCP", "port": 8000}]},
                {"from": [{"podSelector": {"matchLabels": {"app": "agent"}}}], "ports": [{"protocol": "TCP", "port": 8069}]},
            ],
            "egress": [
                {"to": [{"podSelector": {"matchLabels": {"app": "agent"}}}], "ports": [{"protocol": "TCP", "port": 8000}]},
                {"to": [{"podSelector": {"matchLabels": {"app": "odoo"}}}], "ports": [{"protocol": "TCP", "port": 8069}]},
            ],
        },
    }


def agent_manifests(tenant_id: str, webhook_secret: str, plan: str = "starter") -> list[dict[str, Any]]:
    """All K8s objects needed to enable the AI agent add-on for one tenant."""
    return [
        agent_secret_manifest(tenant_id, webhook_secret),
        agent_pvc_manifest(tenant_id),
        agent_deployment_manifest(tenant_id, plan),
        agent_service_manifest(tenant_id),
        agent_network_policy_manifest(tenant_id),
    ]


def all_manifests(
    tenant_id: str,
    db_password: str,
    admin_password: str,
    app_admin_password: str,
    storage_gi: int = 10,
    addons_repos: list | None = None,
    odoo_version: str = "18.0",
    custom_image: str | None = None,
    plan: str = "starter",
    git_token: str = "",
    install_modules: str = "",
    support_password: str = "",
) -> list[dict]:
    """Return all manifests in apply-order."""
    manifests = [
        namespace_manifest(tenant_id),
        limitrange_manifest(tenant_id),
        resourcequota_manifest(tenant_id, plan=plan, storage_gi=storage_gi),
        network_policy_manifest(tenant_id),
        pvc_manifest(tenant_id, storage_gi),
        secret_manifest(tenant_id, db_password, admin_password, app_admin_password, support_password),
        configmap_manifest(tenant_id, db_password, admin_password, addons_repos, plan=plan),
    ]
    if PG_TOPOLOGY == "cnpg":
        # La instancia PG del tenant va ANTES del Deployment: el init container
        # wait-for-postgres del pod Odoo espera a pg-rw:5432 hasta que el
        # Cluster CNPG esté listo, igual que esperaba al HAProxy externo.
        manifests += [
            pg_credentials_secret_manifest(tenant_id, db_password),
            pg_cilium_apiserver_policy_manifest(tenant_id),
            pg_cluster_manifest(tenant_id),
        ]
    if git_token:
        manifests.append(git_secret_manifest(tenant_id, git_token))
    manifests += [
        deployment_manifest(tenant_id, odoo_version, custom_image, plan=plan, install_modules=install_modules),
        service_manifest(tenant_id),
        ingress_manifest(tenant_id),
        pdb_manifest(tenant_id),
    ]
    return manifests



# ── helpers ──────────────────────────────────────────────────────────────────
def _ns(tenant_id: str) -> str:
    return f"odoo-{tenant_id}"


def _db_endpoint(tenant_id: str) -> tuple[str, int]:
    """(host, port) del Postgres del tenant según PG_TOPOLOGY."""
    if PG_TOPOLOGY == "cnpg":
        return (f"pg-rw.{_ns(tenant_id)}.svc.cluster.local", 5432)
    return (POSTGRES_HOST, POSTGRES_PORT)


def _dbname(tenant_id: str) -> str:
    return f"odoo_{tenant_id}"
