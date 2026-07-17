#!/usr/bin/env bash
# =============================================================================
# infra/apply-manifests.sh
# Apply all K8s manifests in order, injecting secrets from .secrets.env.
#
# Usage (production/cotas — default environment):
#   ./infra/apply-manifests.sh
#
# Usage (other environment):
#   ./infra/apply-manifests.sh --env infra/environments/testbed.env
#
# Usage (dry-run — shows what would be applied, touches nothing):
#   ./infra/apply-manifests.sh --dry-run
#
# Environment inventory (non-secret: node IPs, STORAGE_CLASS, BASE_DOMAIN,
# MANIFEST_EXCLUDE, PG_ENDPOINT_IPS) comes from infra/environments/<env>.env.
# Secrets are read from .secrets.env (gitignored, never committed).
# Copy .secrets.env.example → .secrets.env and fill in real values first.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS_FILE="$REPO_ROOT/.secrets.env"
ENV_FILE="$REPO_ROOT/infra/environments/cotas.env"
DRY_RUN=false

# ── Argument parsing ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=true; shift ;;
    --env) ENV_FILE="$2"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# ── Load environment inventory ───────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: environment file not found: $ENV_FILE"
  exit 1
fi
# shellcheck source=/dev/null
source "$ENV_FILE"
echo "==> Environment: ${ENV_NAME} ($ENV_FILE)"

# Secrets por entorno: .secrets.env.<env> tiene prioridad; si no existe se usa
# .secrets.env (comportamiento histórico de cotas).
if [[ -f "$REPO_ROOT/.secrets.env.${ENV_NAME}" ]]; then
  SECRETS_FILE="$REPO_ROOT/.secrets.env.${ENV_NAME}"
fi

# Variables rendered into manifests. WHITELIST ONLY — the ConfigMap-embedded
# scripts in k8s/backup/ and k8s/07-staging.yaml contain many other ${VARS}
# that must reach the cluster untouched.
export STORAGE_CLASS BASE_DOMAIN PG_NETWORK_CIDR
RENDER_VARS='${STORAGE_CLASS} ${BASE_DOMAIN} ${PG_NETWORK_CIDR}'

KUBECTL_ARGS=""
if $DRY_RUN; then
  echo "==> DRY RUN mode — no changes will be made to the cluster"
  KUBECTL_ARGS="--dry-run=client"
fi

# ── Load secrets ─────────────────────────────────────────────────────────────
if [[ ! -f "$SECRETS_FILE" ]]; then
  echo ""
  echo "ERROR: $SECRETS_FILE not found."
  echo ""
  echo "  Create it from the example:"
  echo "    cp .secrets.env.example .secrets.env"
  echo "    # edit .secrets.env and fill in real passwords"
  echo ""
  exit 1
fi

# shellcheck source=/dev/null
set -o allexport
source "$SECRETS_FILE"
set +o allexport

# Validate required variables are set and not placeholders
missing=()
required_secrets=(DB_PASSWORD ADMIN_PASSWD API_KEY BACKUP_S3_ACCESS_KEY BACKUP_S3_SECRET_KEY BACKUP_PG_SUPERUSER_PASSWORD SAAS_WEBHOOK_KEY)
# El token del tunnel solo es necesario si el entorno despliega cloudflared in-cluster
if [[ " ${MANIFEST_EXCLUDE:-} " != *" 07-cloudflare-tunnel.yaml "* ]]; then
  required_secrets+=(CLOUDFLARE_TUNNEL_TOKEN)
fi
for var in "${required_secrets[@]}"; do
  val="${!var:-}"
  if [[ -z "$val" || "$val" == "change_me" ]]; then
    missing+=("$var")
  fi
done
if [[ ${#missing[@]} -gt 0 ]]; then
  echo ""
  echo "ERROR: The following secrets are missing or still set to 'change_me' in $SECRETS_FILE:"
  for v in "${missing[@]}"; do echo "  - $v"; done
  echo ""
  exit 1
fi

# ── Ensure namespaces exist before we try to create secrets in them ──────────
echo "==> Ensuring namespaces exist …"
kubectl create namespace aeisoftware   --dry-run=client -o yaml | kubectl apply $KUBECTL_ARGS -f - 2>/dev/null || true
kubectl create namespace odoo-admin    --dry-run=client -o yaml | kubectl apply $KUBECTL_ARGS -f - 2>/dev/null || true
kubectl create namespace backup-system --dry-run=client -o yaml | kubectl apply $KUBECTL_ARGS -f - 2>/dev/null || true

# ── Ensure odoo-admin PVC exists (kubectl apply silently drops PVCs on 06) ───
if [[ " ${MANIFEST_EXCLUDE:-} " != *" 06-odoo-admin.yaml "* ]]; then
echo "==> Ensuring odoo-admin-data PVC exists …"
kubectl get pvc odoo-admin-data -n odoo-admin &>/dev/null || \
  kubectl apply $KUBECTL_ARGS -f - <<PVCEOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: odoo-admin-data
  namespace: odoo-admin
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: ${STORAGE_CLASS}
  resources:
    requests:
      storage: 20Gi
PVCEOF
fi

# ── Apply secrets first (from env vars, never from git files) ────────────────
echo "==> Applying secrets from .secrets.env …"
cat <<EOF | kubectl apply $KUBECTL_ARGS --validate=false -f -
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
  namespace: aeisoftware
type: Opaque
stringData:
  POSTGRES_PASSWORD: "${DB_PASSWORD}"
---
apiVersion: v1
kind: Secret
metadata:
  name: portal-secret
  namespace: aeisoftware
type: Opaque
stringData:
  API_KEY: "${API_KEY}"
  SAAS_WEBHOOK_KEY: "${SAAS_WEBHOOK_KEY}"
---
apiVersion: v1
kind: Secret
metadata:
  name: portal-secret
  namespace: odoo-admin
type: Opaque
stringData:
  API_KEY: "${API_KEY}"
  SAAS_WEBHOOK_KEY: "${SAAS_WEBHOOK_KEY}"
---
apiVersion: v1
kind: Secret
metadata:
  name: odoo-admin-secret
  namespace: odoo-admin
type: Opaque
stringData:
  DB_PASSWORD: "${DB_PASSWORD}"
  ADMIN_PASSWD: "${ADMIN_PASSWD}"
EOF

# ── Backup system secrets (backup-system namespace) ──────────────────────────
echo "==> Aplicando backup secrets en namespace backup-system ..."
# BACKUP_S3_ENDPOINT viene del inventario del entorno (sin default: cada
# entorno debe declarar su object storage explícitamente).
if [[ -z "${BACKUP_S3_ENDPOINT:-}" ]]; then
  echo "ERROR: BACKUP_S3_ENDPOINT no definido en $ENV_FILE"
  exit 1
fi
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:-pg-backups}"
cat <<EOF | kubectl apply $KUBECTL_ARGS --validate=false -f -
apiVersion: v1
kind: Secret
metadata:
  name: backup-s3-secret
  namespace: backup-system
type: Opaque
stringData:
  AWS_ACCESS_KEY_ID: "${BACKUP_S3_ACCESS_KEY}"
  AWS_SECRET_ACCESS_KEY: "${BACKUP_S3_SECRET_KEY}"
  S3_ENDPOINT: "${BACKUP_S3_ENDPOINT}"
  S3_BUCKET: "${BACKUP_S3_BUCKET}"
---
apiVersion: v1
kind: Secret
metadata:
  name: postgres-superuser-secret
  namespace: backup-system
type: Opaque
stringData:
  POSTGRES_PASSWORD: "${BACKUP_PG_SUPERUSER_PASSWORD}"
EOF

# Cloudflare tunnel token — inyectar en namespace cloudflare (no en aeisoftware)
if [[ " ${MANIFEST_EXCLUDE:-} " != *" 07-cloudflare-tunnel.yaml "* ]]; then
  echo "==> Aplicando cloudflared-token en namespace cloudflare ..."
  kubectl create namespace cloudflare --dry-run=client -o yaml | kubectl apply $KUBECTL_ARGS -f - 2>/dev/null || true
  cat <<EOF | kubectl apply $KUBECTL_ARGS -f -
apiVersion: v1
kind: Secret
metadata:
  name: cloudflared-token
  namespace: cloudflare
type: Opaque
stringData:
  TUNNEL_TOKEN: "${CLOUDFLARE_TUNNEL_TOKEN}"
EOF
else
  echo "==> cloudflared in-cluster excluido en este entorno — se omite su secret"
fi

# ── Staging namespace + secrets (antes se creaban a mano, ver 07-staging.yaml) ─
if [[ " ${MANIFEST_EXCLUDE:-} " != *" 07-staging.yaml "* ]]; then
  echo "==> Aplicando secrets de staging ..."
  kubectl create namespace staging --dry-run=client -o yaml | kubectl apply $KUBECTL_ARGS -f - 2>/dev/null || true
  cat <<EOF | kubectl apply $KUBECTL_ARGS --validate=false -f -
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
  namespace: staging
type: Opaque
stringData:
  POSTGRES_PASSWORD: "${DB_PASSWORD}"
---
apiVersion: v1
kind: Secret
metadata:
  name: portal-secret
  namespace: staging
type: Opaque
stringData:
  API_KEY: "${API_KEY}"
  SAAS_WEBHOOK_KEY: "${SAAS_WEBHOOK_KEY}"
---
apiVersion: v1
kind: Secret
metadata:
  name: odoo-stg-secret
  namespace: staging
type: Opaque
stringData:
  DB_PASSWORD: "${DB_PASSWORD}"
  ADMIN_PASSWD: "${ADMIN_PASSWD}"
EOF
fi

# ── Endpoints de PostgreSQL externo (generados desde PG_ENDPOINT_IPS) ─────────
if [[ -z "${PG_ENDPOINT_IPS:-}" ]]; then
  echo "ERROR: PG_ENDPOINT_IPS no definido en $ENV_FILE"
  exit 1
fi
echo "==> Generando Endpoints postgres desde inventario (${PG_ENDPOINT_IPS}) ..."
{
  cat <<EOF
apiVersion: v1
kind: Endpoints
metadata:
  name: postgres
  namespace: aeisoftware
  labels:
    app: postgres
subsets:
  - addresses:
EOF
  for ip in ${PG_ENDPOINT_IPS}; do
    echo "      - ip: ${ip}"
  done
  cat <<'EOF'
    ports:
      - name: primary
        port: 5000
        protocol: TCP
      - name: replica
        port: 5001
        protocol: TCP
EOF
} | kubectl apply $KUBECTL_ARGS -f -

# ── Apply all other manifests (secrets files are deliberately skipped) ────────
echo "==> Applying manifests …"
# Apply backup/ subdirectory manifests (namespace, RBAC, NetworkPolicy, scripts, CronJobs)
for f in "$REPO_ROOT"/k8s/backup/*.yaml; do
  echo "  applying $f …"
  kubectl apply $KUBECTL_ARGS --validate=false -f "$f"
done

for f in "$REPO_ROOT"/k8s/0*.yaml; do
  filename=$(basename "$f")

  # Skip 01-secrets.yaml — it is now a placeholder-only file.
  # All secrets were already applied above from .secrets.env.
  if [[ "$filename" == "01-secrets.yaml" ]]; then
    echo "  skipping $filename (secrets applied from .secrets.env above)"
    continue
  fi

  # Skip manifests excluded by the environment inventory
  if [[ " ${MANIFEST_EXCLUDE:-} " == *" $filename "* ]]; then
    echo "  skipping $filename (MANIFEST_EXCLUDE en ${ENV_NAME})"
    continue
  fi

  # Cilium-specific policies only apply where the Cilium CRDs exist
  if [[ "$filename" == 00b-cilium-* ]] && \
     ! kubectl get crd ciliumnetworkpolicies.cilium.io &>/dev/null; then
    echo "  skipping $filename (CRD de Cilium no instalado)"
    continue
  fi

  # Skip files that contain no YAML objects (e.g. 08-backup-cronjob.yaml is
  # comment-only since Fase 2) — kubectl errors on "no objects passed to apply"
  if ! grep -qE '^[^#[:space:]]' "$f"; then
    echo "  skipping $filename (sin objetos YAML — archivo inactivo)"
    continue
  fi

  echo "  applying $f …"
  # Render whitelist-only: solo ${STORAGE_CLASS} y ${BASE_DOMAIN}; el resto de
  # ${VARS} (scripts embebidos en ConfigMaps) pasa intacto al clúster.
  envsubst "$RENDER_VARS" < "$f" | kubectl apply $KUBECTL_ARGS --validate=false -f -
done

# ── Verificar servicios ──────────────────────────────────────────────────────
if ! $DRY_RUN; then
  echo "==> Verificando endpoints de PostgreSQL HA..."
  kubectl -n aeisoftware get endpoints postgres || true

  echo ""
  echo "==> Todos los manifests aplicados correctamente."
  echo ""
  echo "    Portal:     https://portal.${BASE_DOMAIN}"
  echo "    Admin Odoo: https://admin.${BASE_DOMAIN}"
  echo "    VIP K3s:    ${KUBE_VIP_IP:-?}"
fi
