#!/bin/bash
# =============================================================================
# deploy-k3s-cluster.sh — Orquestador del clúster K3s HA
#
# Despliega el stack completo K3s HA en los nodos del entorno elegido.
# Ejecutar desde tu máquina local (no desde las VMs).
#
# Orden de despliegue:
#   1. Preparar los nodos
#   2. Instalar K3s server-1 (cluster-init)
#   3. Instalar kube-vip
#   4. Instalar Cilium CNI
#   5. Unir el resto de servers
#   6. Instalar Traefik
#   7. Instalar storage: Ceph CSI o Longhorn (según STORAGE_BACKEND)
#
# Prerequisito:
#   cp infra/k3s-ha/.env.example infra/k3s-ha/.env
#   nano infra/k3s-ha/.env   # completar K3S_TOKEN (+ CEPH_CSI_KEY/CEPH_ADMIN_KEY si ceph)
#
# Uso:
#   ./infra/k3s-ha/deploy-k3s-cluster.sh [infra/environments/<env>.env]
#   Sin argumento usa infra/environments/cotas.env (comportamiento histórico).
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ─── Cargar inventario del entorno ───────────────────────────────────────────
ENV_FILE="${1:-${REPO_ROOT}/infra/environments/cotas.env}"
if [ ! -f "${ENV_FILE}" ]; then
  echo "❌ Inventario de entorno no encontrado: ${ENV_FILE}"
  echo "   Disponibles: $(ls "${REPO_ROOT}/infra/environments/"*.env 2>/dev/null | xargs -n1 basename | tr '\n' ' ')"
  exit 1
fi
# shellcheck source=/dev/null
source "${ENV_FILE}"
echo "→ Entorno: ${ENV_NAME} (${ENV_FILE})"

echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║   K3s HA Cluster — Despliegue Automatizado              ║"
echo "  ║   Cilium · kube-vip · storage: ${STORAGE_BACKEND}"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""

# ─── SSH Config (SSH_KEY/SSH_USER vienen del inventario) ─────────────────────
SSH_OPTS="-i ${SSH_KEY} -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o ServerAliveInterval=30"

# ─── Nodos: name:ssh_ip:internal_ip (del inventario) ─────────────────────────
NODES=("${K3S_NODES[@]}")
NODE_COUNT="${#NODES[@]}"

# El primer nodo es el que inicializa el clúster
IFS=':' read -r FIRST_NAME FIRST_SSH FIRST_IP <<< "${NODES[0]}"

# ─── Cargar .env (variante por entorno para no mezclar credenciales) ──────────
DOTENV_FILE="${SCRIPT_DIR}/.env"
if [ "${ENV_NAME:-cotas}" != "cotas" ]; then
  DOTENV_FILE="${SCRIPT_DIR}/.env.${ENV_NAME}"
fi
if [ ! -f "${DOTENV_FILE}" ]; then
  echo "❌ Archivo ${DOTENV_FILE} no encontrado."
  echo "   Copia la plantilla y completa las credenciales:"
  echo "   cp ${SCRIPT_DIR}/.env.example ${DOTENV_FILE}"
  echo "   nano ${DOTENV_FILE}"
  exit 1
fi
set -a; source "${DOTENV_FILE}"; set +a
echo "→ Variables cargadas desde ${DOTENV_FILE}"

# ─── Generar K3S_TOKEN si no está definido ────────────────────────────────────
if [ -z "${K3S_TOKEN:-}" ] || [[ "${K3S_TOKEN}" == "change_me" ]]; then
  K3S_TOKEN="$(openssl rand -hex 32)"
  sed -i "s/^K3S_TOKEN=.*/K3S_TOKEN=${K3S_TOKEN}/" "${DOTENV_FILE}"
  echo "→ K3S_TOKEN generado y guardado en ${DOTENV_FILE}"
fi

# ─── Validar variables críticas ──────────────────────────────────────────────
echo "→ Validando configuración..."
REQUIRED=(KUBE_VIP_IP K3S_INTERFACE)
if [ "${STORAGE_BACKEND}" = "ceph" ]; then
  REQUIRED+=(CEPH_CLUSTER_ID CEPH_MON_1 CEPH_MON_2 CEPH_RBD_POOL CEPH_CSI_KEY CEPH_ADMIN_KEY)
fi
for var in "${REQUIRED[@]}"; do
  if [ -z "${!var:-}" ] || [[ "${!var}" == *"change_me"* ]]; then
    echo "  ✗ ${var} no configurado en .env"
    exit 1
  fi
  echo "  ✓ ${var}"
done

# ─── Helper: ejecutar script remotamente ─────────────────────────────────────
run_remote() {
  local name="$1"
  local ssh_ip="$2"
  local internal_ip="$3"
  local script="$4"

  echo ""
  echo "  ┌────────────────────────────────────────────"
  echo "  │ ${script} → ${name} (${ssh_ip})"
  echo "  └────────────────────────────────────────────"

  local env_exports
  env_exports="export NODE_NAME='${name}';"
  env_exports+="export NODE_IP='${internal_ip}';"
  env_exports+="export K3S_TOKEN='${K3S_TOKEN}';"
  env_exports+="export KUBE_VIP_IP='${KUBE_VIP_IP}';"
  env_exports+="export K3S_INTERFACE='${K3S_INTERFACE}';"
  env_exports+="export STORAGE_BACKEND='${STORAGE_BACKEND}';"
  env_exports+="export CEPH_MON_HOSTS='${CEPH_MON_HOSTS:-}';"
  env_exports+="export PG_CHECK_IPS='${PG_CHECK_IPS:-}';"
  env_exports+="export CEPH_CLUSTER_ID='${CEPH_CLUSTER_ID:-}';"
  env_exports+="export CEPH_MON_1='${CEPH_MON_1:-}';"
  env_exports+="export CEPH_MON_2='${CEPH_MON_2:-}';"
  env_exports+="export CEPH_RBD_POOL='${CEPH_RBD_POOL:-}';"
  env_exports+="export CEPH_CSI_KEY='${CEPH_CSI_KEY:-}';"
  env_exports+="export CEPH_ADMIN_KEY='${CEPH_ADMIN_KEY:-}';"

  # shellcheck disable=SC2029
  ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} \
    "sudo bash -c '${env_exports} bash -s'" < "${SCRIPT_DIR}/${script}"
}

# ─── Verificar conectividad SSH ───────────────────────────────────────────────
echo ""
echo "→ Verificando conectividad SSH..."
for node in "${NODES[@]}"; do
  IFS=':' read -r name ssh_ip internal_ip <<< "${node}"
  if ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} "echo OK" &>/dev/null; then
    echo "  ✓ ${name} (${ssh_ip})"
  else
    echo "  ✗ ${name} (${ssh_ip}) — No se puede conectar"
    echo "    Verifica: ssh -i ${SSH_KEY} ${SSH_USER}@${ssh_ip}"
    exit 1
  fi
done

START_TIME=$(date +%s)

# =============================================================================
# PASO 1: Preparar los 3 nodos (paralelo)
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PASO 1/7: Preparando nodos (ceph-common, rbd, sysctl)"
echo "═══════════════════════════════════════════════════════════"

for node in "${NODES[@]}"; do
  IFS=':' read -r name ssh_ip internal_ip <<< "${node}"
  run_remote "${name}" "${ssh_ip}" "${internal_ip}" "00-prepare-node.sh"
done

# =============================================================================
# PASO 2: Instalar K3s en el primer nodo (cluster-init)
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PASO 2/7: Instalando K3s server-1 (cluster-init)"
echo "  Nodo: ${FIRST_NAME} | IP: ${FIRST_IP}"
echo "═══════════════════════════════════════════════════════════"

run_remote "${FIRST_NAME}" "${FIRST_SSH}" "${FIRST_IP}" "01-install-k3s-server1.sh"

echo "→ Esperando 30s para que el API server estabilice..."
sleep 30

# =============================================================================
# PASO 3: Instalar kube-vip (VIP 192.168.0.150)
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PASO 3/7: Instalando kube-vip (VIP ${KUBE_VIP_IP})"
echo "═══════════════════════════════════════════════════════════"

run_remote "${FIRST_NAME}" "${FIRST_SSH}" "${FIRST_IP}" "02-install-kube-vip.sh"

echo "→ Esperando 15s para que el VIP se active..."
sleep 15

# =============================================================================
# PASO 4: Instalar Cilium CNI
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PASO 4/7: Instalando Cilium CNI (eBPF kube-proxy replacement)"
echo "═══════════════════════════════════════════════════════════"

run_remote "${FIRST_NAME}" "${FIRST_SSH}" "${FIRST_IP}" "04-install-cilium.sh"

echo "→ Esperando 20s para que Cilium propague el CNI..."
sleep 20

# =============================================================================
# PASO 5: Unir server-2 y server-3
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PASO 5/7: Uniendo el resto de servers al clúster"
echo "═══════════════════════════════════════════════════════════"

for (( i=1; i<NODE_COUNT; i++ )); do
  IFS=':' read -r name ssh_ip internal_ip <<< "${NODES[$i]}"
  run_remote "${name}" "${ssh_ip}" "${internal_ip}" "03-join-k3s-servers.sh"
  echo "→ Esperando 30s antes del siguiente nodo..."
  sleep 30
done

echo ""
echo "→ Verificando estado del clúster..."
ssh ${SSH_OPTS} ${SSH_USER}@${FIRST_SSH} \
  "sudo KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get nodes -o wide"

# =============================================================================
# PASO 6: Instalar Traefik
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PASO 6/7: Instalando Traefik v3"
echo "═══════════════════════════════════════════════════════════"

run_remote "${FIRST_NAME}" "${FIRST_SSH}" "${FIRST_IP}" "05-install-traefik.sh"

# =============================================================================
# PASO 7: Instalar storage (Ceph CSI RBD o Longhorn según STORAGE_BACKEND)
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PASO 7/7: Instalando storage (${STORAGE_BACKEND})"
echo "═══════════════════════════════════════════════════════════"

case "${STORAGE_BACKEND}" in
  ceph)     run_remote "${FIRST_NAME}" "${FIRST_SSH}" "${FIRST_IP}" "06-install-ceph-csi.sh" ;;
  longhorn) run_remote "${FIRST_NAME}" "${FIRST_SSH}" "${FIRST_IP}" "06b-install-longhorn.sh" ;;
  *) echo "❌ STORAGE_BACKEND desconocido: ${STORAGE_BACKEND} (esperado: ceph|longhorn)"; exit 1 ;;
esac

# =============================================================================
# RESUMEN FINAL
# =============================================================================
END_TIME=$(date +%s)
ELAPSED=$(( END_TIME - START_TIME ))

echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║              ✅ CLÚSTER K3s HA DESPLEGADO               ║"
echo "  ╠══════════════════════════════════════════════════════════╣"
echo "  ║                                                          ║"
echo "  ║  Tiempo total: $(printf '%02d:%02d:%02d' $((ELAPSED/3600)) $(((ELAPSED%3600)/60)) $((ELAPSED%60)))                              ║"
echo "  ║                                                          ║"
echo "  ║  Nodos:                                                  ║"
for node in "${NODES[@]}"; do
  IFS=':' read -r name ssh_ip internal_ip <<< "${node}"
  printf "  ║    %-14s %-15s                        ║\n" "${name}" "${internal_ip}"
done
echo "  ║                                                          ║"
echo "  ║  API Server VIP: https://${KUBE_VIP_IP}:6443             ║"
echo "  ║  Ingress:        http/https://${KUBE_VIP_IP}             ║"
echo "  ║  StorageClass:   ${STORAGE_CLASS}                        ║"
echo "  ║                                                          ║"
echo "  ║  Siguiente paso: Aplicar manifests K8s                  ║"
echo "  ║    cp infra/k3s-ha/.env.kubeconfig ~/.kube/k3s-ha.yaml  ║"
echo "  ║    ./infra/apply-manifests.sh                           ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Extraer kubeconfig apuntando al VIP ────────────────────────────────────
echo "→ Descargando kubeconfig (apunta al VIP ${KUBE_VIP_IP})..."
ssh ${SSH_OPTS} ${SSH_USER}@${FIRST_SSH} \
  "sudo cat /etc/rancher/k3s/k3s.yaml" | \
  sed "s/127.0.0.1/${KUBE_VIP_IP}/g" > "${SCRIPT_DIR}/.kubeconfig${ENV_NAME:+.${ENV_NAME}}"
chmod 600 "${SCRIPT_DIR}/.kubeconfig${ENV_NAME:+.${ENV_NAME}}"
echo "  ✅ Guardado en: ${SCRIPT_DIR}/.kubeconfig${ENV_NAME:+.${ENV_NAME}}"
echo "     Para usar: export KUBECONFIG=${SCRIPT_DIR}/.kubeconfig${ENV_NAME:+.${ENV_NAME}}"
