#!/bin/bash
# =============================================================================
# 07-join-k3s-workers.sh — Une los nodos worker al clúster K3s HA existente
#
# Ejecutar desde tu máquina local (WSL/Linux).
#
# Uso:
#   ./07-join-k3s-workers.sh [ruta/al/entorno.env]
#   Sin argumento, usa infra/environments/cotas.env (comportamiento por defecto).
#
# El env file debe definir K3S_NODES, K3S_WORKER_NODES, SSH_KEY, SSH_USER
# (ver infra/environments/cotas.env). Si K3S_WORKER_NODES está vacío, el
# script termina sin hacer nada (entorno sin workers definidos).
#
# Pasos por nodo:
#   1. Preparar nodo (sysctl, swap-off; ceph-common/rbd solo si STORAGE_BACKEND=ceph)
#   2. Instalar K3s agent (conecta al VIP)
#   3. Etiquetar el nodo como worker en K8s
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

ENV_FILE="${1:-${REPO_ROOT}/infra/environments/cotas.env}"

if [ ! -f "${ENV_FILE}" ]; then
  echo "❌ Env file no encontrado: ${ENV_FILE}"
  exit 1
fi

echo "→ Cargando entorno desde ${ENV_FILE}..."
# shellcheck disable=SC1090
source "${ENV_FILE}"

if [ "${#K3S_WORKER_NODES[@]}" -eq 0 ]; then
  echo "  ⚠️  sin workers definidos para este entorno"
  exit 0
fi

SSH_OPTS="-i ${SSH_KEY} -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o ServerAliveInterval=30"

# CONTROL_SSH = ssh_ip del primer elemento de K3S_NODES
IFS=':' read -r _control_name CONTROL_SSH _control_internal <<< "${K3S_NODES[0]}"

K3S_VERSION="v1.34.6+k3s1"

# name:ssh_ip:internal_ip
WORKERS=("${K3S_WORKER_NODES[@]}")

# ─── Banner ───────────────────────────────────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║   K3s Workers Join — Hito 1                             ║"
echo "  ║   3 worker nodes · Cilium auto-provisioned · Ceph RBD   ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""

# ─── Verificar SSH key ────────────────────────────────────────────────────────
if [ ! -f "${SSH_KEY}" ]; then
  echo "❌ SSH key no encontrada: ${SSH_KEY}"
  exit 1
fi
chmod 600 "${SSH_KEY}"

# ─── Obtener K3S_TOKEN desde control-1 ───────────────────────────────────────
echo "→ Obteniendo K3S_TOKEN desde k3s-control-1..."
K3S_TOKEN=$(ssh ${SSH_OPTS} ${SSH_USER}@${CONTROL_SSH} \
  "sudo cat /var/lib/rancher/k3s/server/node-token")
echo "  ✓ Token obtenido (${#K3S_TOKEN} chars)"

# ─── Verificar VIP activo ─────────────────────────────────────────────────────
echo "→ Verificando VIP ${KUBE_VIP_IP}:6443..."
if ssh ${SSH_OPTS} ${SSH_USER}@${CONTROL_SSH} \
    "nc -z -w5 ${KUBE_VIP_IP} 6443" 2>/dev/null; then
  echo "  ✓ VIP activo"
else
  echo "  ❌ VIP ${KUBE_VIP_IP}:6443 no responde — verifica kube-vip"
  exit 1
fi

# ─── Verificar conectividad SSH a cada worker ─────────────────────────────────
echo ""
echo "→ Verificando SSH a workers..."
for worker in "${WORKERS[@]}"; do
  IFS=':' read -r name ssh_ip internal_ip <<< "${worker}"
  if ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} "echo OK" &>/dev/null; then
    echo "  ✓ ${name} (${ssh_ip})"
  else
    echo "  ❌ ${name} (${ssh_ip}) — sin acceso SSH"
    echo "     Verifica: ssh -i ${SSH_KEY} ${SSH_USER}@${ssh_ip}"
    exit 1
  fi
done

# ─── Función: preparar nodo ───────────────────────────────────────────────────
prepare_worker() {
  local name="$1"
  local ssh_ip="$2"

  echo ""
  echo "  ┌── prepare: ${name} (${ssh_ip})"

  ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} "sudo bash -s" << PREPARE
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "  → Actualizando paquetes..."
apt-get update -qq
apt-get install -y -qq \\
  curl wget ca-certificates \\
  net-tools iproute2 iputils-ping \\
  jq nfs-common open-iscsi \\
  netcat-openbsd

if [ "${STORAGE_BACKEND:-}" = "ceph" ]; then
  echo "  → Instalando ceph-common (requerido para montar PVs)..."
  apt-get install -y -qq ceph-common
  ceph --version 2>/dev/null || { echo "  ✗ ceph-common falló"; exit 1; }

  echo "  → Cargando módulo rbd..."
  modprobe rbd
  echo "rbd" | tee /etc/modules-load.d/rbd.conf > /dev/null
  lsmod | grep -q rbd && echo "  ✓ rbd cargado" || { echo "  ✗ rbd no disponible"; exit 1; }
else
  echo "  → STORAGE_BACKEND=${STORAGE_BACKEND:-<sin definir>} — se omite ceph-common/rbd"
fi

echo "  → Configurando parámetros kernel..."
cat > /etc/sysctl.d/99-k3s-cilium.conf << 'SYSCTL'
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.conf.all.arp_announce = 2
net.ipv4.conf.all.arp_ignore = 1
SYSCTL
sysctl --system -q
echo "  ✓ sysctl aplicado"

echo "  → Deshabilitando swap..."
swapoff -a
sed -i '/\bswap\b/d' /etc/fstab
echo "  ✓ swap deshabilitado"
PREPARE

  echo "  └── prepare OK"
}

# ─── Función: unir worker al clúster ─────────────────────────────────────────
join_worker() {
  local name="$1"
  local ssh_ip="$2"
  local internal_ip="$3"
  local token="$4"

  echo ""
  echo "  ┌── join: ${name} (${ssh_ip} / ${internal_ip})"

  # Idempotencia: saltar si k3s-agent ya está corriendo
  if ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} \
      "systemctl is-active --quiet k3s-agent 2>/dev/null" 2>/dev/null; then
    echo "  ✓ k3s-agent ya está activo en ${name} — saltando join"
    echo "  └── (ya unido)"
    return 0
  fi

  ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} "sudo bash -s" << JOINCMD
set -euo pipefail

echo "  → Instalando K3s agent ${K3S_VERSION}..."
curl -sfL https://get.k3s.io | \
  INSTALL_K3S_VERSION="${K3S_VERSION}" \
  INSTALL_K3S_EXEC="agent \
    --server=https://${KUBE_VIP_IP}:6443 \
    --token=${token} \
    --node-ip=${internal_ip} \
    --node-name=${name}" \
  sh -

echo "  → Verificando k3s-agent..."
sleep 5
systemctl is-active k3s-agent && echo "  ✓ k3s-agent activo" || { echo "  ✗ k3s-agent no arrancó"; journalctl -u k3s-agent --no-pager -n 20; exit 1; }
JOINCMD

  echo "  └── join OK"
}

# ─── Función: etiquetar nodo ──────────────────────────────────────────────────
label_worker() {
  local name="$1"

  echo "  → Esperando que ${name} aparezca en el clúster..."
  for i in $(seq 1 24); do
    if ssh ${SSH_OPTS} ${SSH_USER}@${CONTROL_SSH} \
        "KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get node ${name} --no-headers" &>/dev/null; then
      echo "  ✓ ${name} visible en el clúster (intento ${i}/24)"
      break
    fi
    sleep 10
  done

  ssh ${SSH_OPTS} ${SSH_USER}@${CONTROL_SSH} "sudo bash -s" << LABELCMD
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl label node ${name} node-role.kubernetes.io/worker=true --overwrite
kubectl label node ${name} workload=tenant --overwrite
echo "  ✓ ${name} etiquetado: worker + workload=tenant"
LABELCMD
}

# =============================================================================
# MAIN — procesar cada worker en secuencia
# =============================================================================
START=$(date +%s)

for worker in "${WORKERS[@]}"; do
  IFS=':' read -r name ssh_ip internal_ip <<< "${worker}"

  echo ""
  echo "══════════════════════════════════════════════════════════"
  echo "  Worker: ${name} | SSH: ${ssh_ip} | K8s: ${internal_ip}"
  echo "══════════════════════════════════════════════════════════"

  prepare_worker "${name}" "${ssh_ip}"
  join_worker    "${name}" "${ssh_ip}" "${internal_ip}" "${K3S_TOKEN}"
  label_worker   "${name}"
done

# ─── Estado final del clúster ─────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════"
echo "  Estado final del clúster"
echo "══════════════════════════════════════════════════════════"
ssh ${SSH_OPTS} ${SSH_USER}@${CONTROL_SSH} \
  "KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get nodes -o wide"

echo ""
echo "  Pods de sistema (Cilium en workers):"
ssh ${SSH_OPTS} ${SSH_USER}@${CONTROL_SSH} \
  "KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl -n kube-system get pods -l k8s-app=cilium -o wide"

END=$(date +%s)
ELAPSED=$(( END - START ))

echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║        ✅ WORKERS UNIDOS AL CLÚSTER K3s                 ║"
echo "  ╠══════════════════════════════════════════════════════════╣"
echo "  ║  Tiempo: $(printf '%02d:%02d' $(( ELAPSED/60 )) $(( ELAPSED%60 )) )                                         ║"
echo "  ║                                                          ║"
echo "  ║  Workers:                                                ║"
for worker in "${WORKERS[@]}"; do
  IFS=':' read -r name ssh_ip internal_ip <<< "${worker}"
  printf "  ║    %-45s ║\n" "${name}  ${internal_ip}"
done
echo "  ║                                                          ║"
echo "  ║  Label aplicado: workload=tenant                        ║"
echo "  ║                                                          ║"
echo "  ║  SIGUIENTE: Agregar nodeAffinity a tenant deployments   ║"
echo "  ║    infra/k3s-ha/08-patch-tenant-affinity.sh             ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""
