#!/bin/bash
# =============================================================================
# 07-join-k3s-workers.sh — Une 3 nodos worker al clúster K3s HA existente
#
# Ejecutar desde tu máquina local (WSL/Linux).
#
# Pasos por nodo:
#   1. Preparar nodo (ceph-common, rbd, sysctl, swap-off)
#   2. Instalar K3s agent (conecta al VIP 192.168.0.150:6443)
#   3. Etiquetar el nodo como worker en K8s
#
# Workers:
#   k3s-worker-1  IT911=10.40.2.200  internal=192.168.0.148
#   k3s-worker-2  IT911=10.40.2.190  internal=192.168.0.61
#   k3s-worker-3  IT911=10.40.2.171  internal=192.168.0.190
# =============================================================================
set -euo pipefail

SSH_KEY="/tmp/k3s_rsa"
SSH_USER="ubuntu"
SSH_OPTS="-i ${SSH_KEY} -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o ServerAliveInterval=30"

KUBE_VIP_IP="192.168.0.150"
CONTROL_SSH="10.40.2.158"    # k3s-control-1 — fuente del token

K3S_VERSION="v1.34.6+k3s1"

# name:ssh_ip(IT911):internal_ip
WORKERS=(
  "k3s-worker-1:10.40.2.200:192.168.0.148"
  "k3s-worker-2:10.40.2.190:192.168.0.61"
  "k3s-worker-3:10.40.2.171:192.168.0.190"
)

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

  ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} "sudo bash -s" << 'PREPARE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "  → Actualizando paquetes..."
apt-get update -qq
apt-get install -y -qq \
  curl wget ca-certificates \
  net-tools iproute2 iputils-ping \
  jq nfs-common open-iscsi \
  netcat-openbsd

echo "  → Instalando ceph-common (requerido para montar PVs)..."
apt-get install -y -qq ceph-common
ceph --version 2>/dev/null || { echo "  ✗ ceph-common falló"; exit 1; }

echo "  → Cargando módulo rbd..."
modprobe rbd
echo "rbd" | tee /etc/modules-load.d/rbd.conf > /dev/null
lsmod | grep -q rbd && echo "  ✓ rbd cargado" || { echo "  ✗ rbd no disponible"; exit 1; }

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
echo "  ║    k3s-worker-1  192.168.0.148                          ║"
echo "  ║    k3s-worker-2  192.168.0.61                            ║"
echo "  ║    k3s-worker-3  192.168.0.190                          ║"
echo "  ║                                                          ║"
echo "  ║  Label aplicado: workload=tenant                        ║"
echo "  ║                                                          ║"
echo "  ║  SIGUIENTE: Agregar nodeAffinity a tenant deployments   ║"
echo "  ║    infra/k3s-ha/08-patch-tenant-affinity.sh             ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""
