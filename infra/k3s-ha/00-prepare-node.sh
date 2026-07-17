#!/bin/bash
# =============================================================================
# 00-prepare-node.sh — Prepara cada nodo K3s (Ubuntu 24.04)
#
# Ejecutado por deploy-k3s-cluster.sh en todos los nodos via SSH.
# Instala prerequisitos comunes (open-iscsi para Longhorn incluido) y, solo si
# STORAGE_BACKEND=ceph, el cliente Ceph (ceph-common + módulo rbd).
#
# Variables recibidas via env:
#   NODE_NAME        — nombre del nodo
#   NODE_IP          — IP interna
#   STORAGE_BACKEND  — ceph | longhorn
#   CEPH_MON_HOSTS   — IPs de MONs a verificar (solo ceph, separadas por espacio)
#   PG_CHECK_IPS     — IPs de PG a verificar (warn-only, separadas por espacio)
# =============================================================================
set -euo pipefail

echo ""
echo "  ┌─────────────────────────────────────────────────────────"
echo "  │  00-prepare-node — ${NODE_NAME} (${NODE_IP})"
echo "  └─────────────────────────────────────────────────────────"

# ── Sistema base ──────────────────────────────────────────────────────────────
echo "→ Actualizando paquetes..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  curl wget gnupg2 ca-certificates \
  net-tools iproute2 iputils-ping \
  jq htop nfs-common open-iscsi \
  netcat-openbsd

# ── Ceph client — solo si el storage backend es Ceph RBD ─────────────────────
STORAGE_BACKEND="${STORAGE_BACKEND:-ceph}"
if [ "${STORAGE_BACKEND}" = "ceph" ]; then
  echo "→ Instalando ceph-common..."
  apt-get install -y -qq ceph-common
  ceph --version 2>/dev/null || { echo "  ✗ ceph-common no instalado correctamente"; exit 1; }
  echo "  ✓ ceph-common instalado"

  echo "→ Cargando módulo rbd..."
  modprobe rbd
  echo "rbd" | tee /etc/modules-load.d/rbd.conf > /dev/null
  lsmod | grep -q rbd && echo "  ✓ módulo rbd cargado" || { echo "  ✗ Error cargando rbd"; exit 1; }
else
  echo "→ STORAGE_BACKEND=${STORAGE_BACKEND} — se omite cliente Ceph (open-iscsi ya instalado para Longhorn)"
fi

# ── Ajustes kernel para K3s + Cilium (eBPF) ──────────────────────────────────
echo "→ Configurando parámetros kernel..."
cat > /etc/sysctl.d/99-k3s-cilium.conf << 'EOF'
# K3s
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
# Cilium / eBPF
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
# kube-vip ARP
net.ipv4.conf.all.arp_announce = 2
net.ipv4.conf.all.arp_ignore = 1
EOF
sysctl --system -q
echo "  ✓ parámetros kernel aplicados"

# ── Deshabilitar swap (requerido por K3s) ─────────────────────────────────────
echo "→ Deshabilitando swap..."
swapoff -a
sed -i '/\bswap\b/d' /etc/fstab
echo "  ✓ swap deshabilitado"

# ── Verificar conectividad con Ceph MONs (solo backend ceph) ──────────────────
if [ "${STORAGE_BACKEND}" = "ceph" ] && [ -n "${CEPH_MON_HOSTS:-}" ]; then
  echo "→ Verificando conectividad con Ceph MONs..."
  for mon in ${CEPH_MON_HOSTS}; do
    if nc -z -w3 "${mon}" 6789 2>/dev/null; then
      echo "  ✓ ${mon}:6789 alcanzable"
    else
      echo "  ✗ ${mon}:6789 NO alcanzable"
      echo "    Verifica que los nodos K3s tengan ruta a la red de Ceph"
      exit 1
    fi
  done
fi

# ── Verificar conectividad con PostgreSQL (warn-only) ─────────────────────────
echo "→ Verificando conectividad con PostgreSQL..."
for pg_ip in ${PG_CHECK_IPS:-}; do
  if nc -z -w3 "${pg_ip}" 5002 2>/dev/null; then
    echo "  ✓ ${pg_ip}:5002 (PgBouncer) OK"
  else
    echo "  ⚠ ${pg_ip}:5002 no responde — verificar después de instalar K3s"
  fi
done

echo ""
echo "  ✅ 00-prepare-node completado en ${NODE_NAME}"
