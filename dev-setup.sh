#!/usr/bin/env bash
# =============================================================================
# dev-setup.sh — Bootstrap local K3s dev environment on WSL / Linux
#
# Usage:
#   chmod +x dev-setup.sh
#   ./dev-setup.sh
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$REPO_ROOT/k8s"
PORTAL_DIR="$REPO_ROOT/portal"
ADDONS_DIR="$REPO_ROOT/addons"

PORTAL_IMAGE="saas-portal:dev"
ODOO_IMAGE="${ODOO_IMAGE:-odoo:18}"

# Load non-placeholder values from .secrets.env if present
if [[ -f "$REPO_ROOT/.secrets.env" ]]; then
  while IFS='=' read -r key val; do
    [[ -z "$key" || "$key" =~ ^# ]] && continue
    val="${val%\"}"
    val="${val#\"}"
    if [[ -n "$val" && "$val" != "change_me" && -z "${!key:-}" ]]; then
      export "$key=$val"
    fi
  done < "$REPO_ROOT/.secrets.env"
fi

export DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -hex 16)}"
export API_KEY="${API_KEY:-$(openssl rand -hex 16)}"
export ADMIN_PASSWD="${ADMIN_PASSWD:-admin}"
export SAAS_WEBHOOK_KEY="${SAAS_WEBHOOK_KEY:-$(openssl rand -hex 16)}"

# ── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Pre-flight Checks ────────────────────────────────────────────────────────
info "Running pre-flight checks..."
if ! command -v docker &>/dev/null; then
  error "Docker is not installed. Please install Docker first: sudo apt install docker.io"
fi

if ! docker ps &>/dev/null; then
  error "Cannot access Docker daemon. Ensure you are in the docker group or run: sudo chmod 666 /var/run/docker.sock"
fi

# ── 0.5. Configure /etc/hosts for local dev (same domains as production) ─────
NODE_IP=$(hostname -I | awk '{print $1}')
DEV_HOSTS=("admin.aeisoftware.com" "www.aeisoftware.com" "portal.aeisoftware.com")
info "Ensuring /etc/hosts points to K3s node ($NODE_IP) for: ${DEV_HOSTS[*]}"
for h in "${DEV_HOSTS[@]}"; do
  sudo sed -i "/$h/d" /etc/hosts
  echo "$NODE_IP   $h" | sudo tee -a /etc/hosts > /dev/null
  info "  Set: $NODE_IP → $h"
done

# ── 1. Install K3s & configure kubeconfig ────────────────────────────────────
if ! command -v k3s &>/dev/null; then
  info "Installing K3s (without built-in Traefik) …"
  curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644 --disable traefik
  sleep 5
else
  info "K3s already installed: $(k3s --version | head -1)"
fi

# Copy kubeconfig to ~/.kube/config so Snap-confined kubectl can also read it
mkdir -p "$HOME/.kube"
sudo cp /etc/rancher/k3s/k3s.yaml "$HOME/.kube/config"
sudo chown "$(id -u):$(id -g)" "$HOME/.kube/config"
chmod 600 "$HOME/.kube/config"
export KUBECONFIG="$HOME/.kube/config"

info "Waiting for K3s node to be Ready …"
timeout 120 bash -c 'until k3s kubectl get nodes 2>/dev/null | grep -q " Ready"; do sleep 3; done'
kubectl get nodes

# ── 1.5. Ensure Traefik is installed via Helm ────────────────────────────────
if ! kubectl -n kube-system get deployment traefik &>/dev/null; then
  info "Installing Traefik via infra/install-traefik.sh …"
  bash "$REPO_ROOT/infra/install-traefik.sh"
else
  info "Traefik already deployed in kube-system."
fi

# ── 2. Build portal image and import into K3s ────────────────────────────────
info "Building portal image: $PORTAL_IMAGE …"
docker build -t "$PORTAL_IMAGE" "$PORTAL_DIR"

info "Importing portal image into K3s containerd …"
docker save "$PORTAL_IMAGE" | sudo k3s ctr images import -

# ── 3. Create namespaces ─────────────────────────────────────────────────────
info "Applying namespace manifest (aeisoftware and odoo-admin) …"
kubectl apply -f "$K8S_DIR/00-namespace.yaml"
kubectl create namespace odoo-admin --dry-run=client -o yaml | kubectl apply -f -

# ── 4. Apply dev secrets ─────────────────────────────────────────────────────
info "Applying dynamic dev secrets …"
cat <<EOF | kubectl apply -f -
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
---
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
  namespace: odoo-admin
type: Opaque
stringData:
  POSTGRES_PASSWORD: "${DB_PASSWORD}"
EOF

# ── 5. Apply Local Postgres 16 (ports 5000 & 5432, local-path storage) ───────
info "Applying local Postgres 16 ($K8S_DIR/dev/02-postgres-local.yaml) …"
kubectl apply -f "$K8S_DIR/dev/02-postgres-local.yaml"

# ── 6. Apply RBAC & Traefik Middlewares ──────────────────────────────────────
info "Applying RBAC …"
kubectl apply -f "$K8S_DIR/04-rbac.yaml"

info "Applying Traefik Middlewares (Odoo headers & security headers) …"
kubectl apply -f "$K8S_DIR/03-traefik-middleware.yaml"

# ── 7. Apply Portal (patched for local K3s) ──────────────────────────────────
info "Applying portal (local image, STORAGE_CLASS=local-path) …"
kubectl apply -f "$K8S_DIR/05-portal.yaml"
kubectl -n aeisoftware patch deployment portal \
  --type=json \
  -p='[
    {"op":"replace","path":"/spec/replicas","value":1},
    {"op":"replace","path":"/spec/template/spec/containers/0/image","value":"'"$PORTAL_IMAGE"'"},
    {"op":"replace","path":"/spec/template/spec/containers/0/imagePullPolicy","value":"Never"}
  ]'
kubectl -n aeisoftware set env deployment/portal \
  API_KEY="${API_KEY}" \
  STORAGE_CLASS="local-path" \
  ODOO_IMAGE="${ODOO_IMAGE}" \
  URL_SCHEME="http"

# ── 8. Apply Odoo admin (local-path PVC + local addons/ mount) ───────────────
info "Applying Odoo admin deployment (storageClassName=local-path, local addons) …"
sed 's/storageClassName: ceph-rbd/storageClassName: local-path/g' "$K8S_DIR/06-odoo-admin.yaml" | kubectl apply -f -

# Patch odoo-admin to copy addons directly from the local workspace and use public odoo:18 image
kubectl -n odoo-admin patch deployment odoo-admin --type=strategic -p "{
  \"spec\": {
    \"template\": {
      \"spec\": {
        \"volumes\": [
          {\"name\": \"host-repo\", \"hostPath\": {\"path\": \"${REPO_ROOT}\", \"type\": \"Directory\"}}
        ],
        \"initContainers\": [
          {
            \"name\": \"copy-addon\",
            \"image\": \"alpine:3.19\",
            \"imagePullPolicy\": \"IfNotPresent\",
            \"command\": [\"sh\", \"-c\", \"cp -r /mnt/host-repo/addons/* /mnt/extra-addons/ && cp -r /mnt/host-repo/external_addons/* /mnt/extra-addons/ && echo 'Local addons copied OK' && ls -la /mnt/extra-addons/\"],
            \"volumeMounts\": [
              {\"name\": \"odoo-addons\", \"mountPath\": \"/mnt/extra-addons\"},
              {\"name\": \"host-repo\", \"mountPath\": \"/mnt/host-repo\", \"readOnly\": true}
            ]
          },
          {
            \"name\": \"flush-asset-cache\",
            \"image\": \"${ODOO_IMAGE}\",
            \"imagePullPolicy\": \"IfNotPresent\"
          }
        ],
        \"containers\": [
          {
            \"name\": \"odoo\",
            \"image\": \"${ODOO_IMAGE}\",
            \"imagePullPolicy\": \"IfNotPresent\"
          }
        ]
      }
    }
  }
}"

kubectl -n odoo-admin rollout restart deployment odoo-admin

# ── 9. Expose services locally via LoadBalancer (dev only) ───────────────────
info "Exposing Odoo and Portal as LoadBalancer services …"

kubectl -n aeisoftware expose deployment portal \
  --name=portal-lb \
  --type=LoadBalancer \
  --port=8000 \
  --target-port=8000 \
  --dry-run=client -o yaml | \
  kubectl apply -f - 2>/dev/null || true

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: odoo-lb
  namespace: odoo-admin
spec:
  type: LoadBalancer
  ports:
    - name: http
      port: 8069
      targetPort: 8069
    - name: longpoll
      port: 8072
      targetPort: 8072
  selector:
    app: odoo-admin
EOF

# ── 10. Wait for pods ────────────────────────────────────────────────────────
info "Waiting for Postgres …"
kubectl -n aeisoftware rollout status statefulset/postgres --timeout=180s

info "Waiting for Portal …"
kubectl -n aeisoftware rollout status deployment/portal --timeout=180s

info "Waiting for Odoo admin …"
kubectl -n odoo-admin rollout status deployment/odoo-admin --timeout=300s

# ── 11. Print access info ────────────────────────────────────────────────────
WSL_IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Local K3s dev environment is ready!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Odoo Public Website: http://www.aeisoftware.com (or http://${WSL_IP}:8069)"
echo -e "  Odoo Admin Backend:  http://admin.aeisoftware.com"
echo -e "  Portal FastAPI Docs: http://portal.aeisoftware.com/docs (or http://${WSL_IP}:8000/docs)"
echo ""
echo -e "  API key:       ${API_KEY}"
echo -e "  DB password:   ${DB_PASSWORD}"
echo -e "  Admin passwd:  ${ADMIN_PASSWD}"
echo ""
echo -e "  Kubeconfig:    ~/.kube/config (already configured for kubectl)"
echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
