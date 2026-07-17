#!/usr/bin/env bash
# =============================================================================
# infra/testbed/create-testbed-vms.sh
#
# Crea las 4 VMs KVM del testbed de portabilidad (simula una "nube genérica"
# sin Ceph/RadosGW) en el host libvirt "cruzoil". Se ejecuta EN ese host,
# como root o con sudo.
#
# VMs creadas (bridge br0, IPs estáticas):
#   k3s-test-1   4 vCPU  12288M RAM   80G disco   10.9.13.21/24
#   k3s-test-2   4 vCPU  12288M RAM   80G disco   10.9.13.22/24
#   k3s-test-3   4 vCPU  12288M RAM   80G disco   10.9.13.23/24
#   pg-test-1    4 vCPU   8192M RAM   60G disco   10.9.13.24/24
#
# Idempotente: si una VM ya existe (virsh dominfo <nombre> resuelve), se
# omite con un mensaje. No hace autostart de las VMs.
#
# Uso:
#   sudo SSH_PUBKEY_FILE=/home/ubuntu/.ssh/id_ed25519.pub \
#     bash infra/testbed/create-testbed-vms.sh
#
# Variables:
#   SSH_PUBKEY_FILE   (obligatoria) ruta a la clave pública SSH a inyectar
#                     en el usuario 'ubuntu' de cada VM.
#   GATEWAY           (opcional) gateway de la red br0. Default: 10.9.13.1
#   BRIDGE            (opcional) bridge de libvirt/host a usar. Default: br0
# =============================================================================
set -euo pipefail

# ── Configuración ─────────────────────────────────────────────────────────────
GATEWAY="${GATEWAY:-10.9.13.1}"
BRIDGE="${BRIDGE:-br0}"

IMAGES_DIR="/var/lib/libvirt/images"
BASE_IMG_DIR="${IMAGES_DIR}/base"
BASE_IMG="${BASE_IMG_DIR}/jammy-server-cloudimg-amd64.img"
BASE_IMG_URL="https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOUD_INIT_DIR="${SCRIPT_DIR}/cloud-init"
USER_DATA_TMPL="${CLOUD_INIT_DIR}/user-data.tmpl"
NETWORK_CFG_TMPL="${CLOUD_INIT_DIR}/network-config.tmpl"

WORK_DIR="$(mktemp -d /tmp/testbed-cloudinit.XXXXXX)"
trap 'rm -rf "${WORK_DIR}"' EXIT

# name:vcpu:ram_mb:disk_gb:ip
VMS=(
  "k3s-test-1:4:12288:80:10.9.13.21"
  "k3s-test-2:4:12288:80:10.9.13.22"
  "k3s-test-3:4:12288:80:10.9.13.23"
  "pg-test-1:4:8192:60:10.9.13.24"
)

# ── Chequeos previos ──────────────────────────────────────────────────────────
if [[ "$(id -u)" -ne 0 ]]; then
  echo "✗ Este script debe ejecutarse como root (sudo)."
  exit 1
fi

if [[ -z "${SSH_PUBKEY_FILE:-}" ]]; then
  echo "✗ Falta SSH_PUBKEY_FILE — ruta a la clave pública SSH a inyectar."
  echo "  Uso: sudo SSH_PUBKEY_FILE=/ruta/a/id_ed25519.pub bash $0"
  exit 1
fi

if [[ ! -f "${SSH_PUBKEY_FILE}" ]]; then
  echo "✗ SSH_PUBKEY_FILE (${SSH_PUBKEY_FILE}) no existe."
  exit 1
fi

SSH_PUBKEY="$(cat "${SSH_PUBKEY_FILE}")"
if [[ -z "${SSH_PUBKEY}" ]]; then
  echo "✗ ${SSH_PUBKEY_FILE} está vacío."
  exit 1
fi
echo "✓ Clave pública SSH cargada desde ${SSH_PUBKEY_FILE}"

for f in "${USER_DATA_TMPL}" "${NETWORK_CFG_TMPL}"; do
  if [[ ! -f "${f}" ]]; then
    echo "✗ Falta template requerido: ${f}"
    exit 1
  fi
done

for cmd in virsh qemu-img; do
  if ! command -v "${cmd}" &>/dev/null; then
    echo "✗ Falta el comando '${cmd}'. Instala qemu-kvm/libvirt antes de continuar."
    exit 1
  fi
done

# ── Instalar dependencias faltantes ───────────────────────────────────────────
echo "→ Verificando dependencias (cloud-image-utils, virtinst)..."
NEED_INSTALL=()
command -v cloud-localds &>/dev/null || NEED_INSTALL+=("cloud-image-utils")
command -v virt-install &>/dev/null || NEED_INSTALL+=("virtinst")

if [[ ${#NEED_INSTALL[@]} -gt 0 ]]; then
  echo "→ Instalando: ${NEED_INSTALL[*]}"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq "${NEED_INSTALL[@]}"
  echo "✓ Dependencias instaladas"
else
  echo "✓ cloud-localds y virt-install ya disponibles"
fi

# ── Descargar imagen base (una sola vez) ──────────────────────────────────────
mkdir -p "${BASE_IMG_DIR}"
if [[ -f "${BASE_IMG}" ]]; then
  echo "✓ Imagen base ya presente: ${BASE_IMG}"
else
  echo "→ Descargando imagen base Ubuntu 22.04 (jammy) cloud image..."
  curl -fL --retry 3 -o "${BASE_IMG}.tmp" "${BASE_IMG_URL}"
  mv "${BASE_IMG}.tmp" "${BASE_IMG}"
  echo "✓ Imagen base descargada: ${BASE_IMG}"
fi

# ── Verificar que las IPs estén libres ────────────────────────────────────────
echo "→ Verificando que las IPs objetivo estén libres..."
for entry in "${VMS[@]}"; do
  IFS=":" read -r vm_name vm_vcpu vm_ram vm_disk vm_ip <<< "${entry}"
  if ping -c1 -W1 "${vm_ip}" &>/dev/null; then
    echo "✗ ${vm_ip} (${vm_name}) responde a ping — ya está en uso. Abortando."
    exit 1
  fi
  echo "  ✓ ${vm_ip} libre"
done

# ── Crear cada VM ──────────────────────────────────────────────────────────────
for entry in "${VMS[@]}"; do
  IFS=":" read -r vm_name vm_vcpu vm_ram vm_disk vm_ip <<< "${entry}"

  echo ""
  echo "  ┌─────────────────────────────────────────────────────────"
  echo "  │  ${vm_name}  (${vm_vcpu} vCPU, ${vm_ram}M RAM, ${vm_disk}G, ${vm_ip})"
  echo "  └─────────────────────────────────────────────────────────"

  if virsh dominfo "${vm_name}" &>/dev/null; then
    echo "→ ${vm_name} ya existe — se omite."
    continue
  fi

  disk_path="${IMAGES_DIR}/${vm_name}.qcow2"
  seed_path="${IMAGES_DIR}/${vm_name}-seed.iso"

  echo "→ Creando disco qcow2 (${vm_disk}G, backing en imagen base)..."
  qemu-img create -f qcow2 -F qcow2 -b "${BASE_IMG}" "${disk_path}" "${vm_disk}G"
  echo "  ✓ ${disk_path}"

  echo "→ Renderizando cloud-init (user-data + network-config)..."
  vm_user_data="${WORK_DIR}/${vm_name}-user-data"
  vm_network_cfg="${WORK_DIR}/${vm_name}-network-config"

  VM_NAME="${vm_name}" SSH_PUBKEY="${SSH_PUBKEY}" \
    envsubst '${VM_NAME} ${SSH_PUBKEY}' < "${USER_DATA_TMPL}" > "${vm_user_data}"

  VM_IP="${vm_ip}" GATEWAY="${GATEWAY}" \
    envsubst '${VM_IP} ${GATEWAY}' < "${NETWORK_CFG_TMPL}" > "${vm_network_cfg}"

  echo "  ✓ user-data y network-config renderizados"

  echo "→ Generando seed ISO (cloud-localds)..."
  cloud-localds -N "${vm_network_cfg}" "${seed_path}" "${vm_user_data}"
  echo "  ✓ ${seed_path}"

  echo "→ Lanzando virt-install..."
  virt-install \
    --import \
    --name "${vm_name}" \
    --memory "${vm_ram}" \
    --vcpus "${vm_vcpu}" \
    --disk "${disk_path}",format=qcow2,bus=virtio \
    --disk "${seed_path}",device=cdrom \
    --network "bridge=${BRIDGE}",model=virtio \
    --os-variant ubuntu22.04 \
    --graphics none \
    --noautoconsole

  echo "  ✓ ${vm_name} creada (sin autostart)"
done

# ── Resumen ────────────────────────────────────────────────────────────────────
echo ""
echo "→ Esperando unos segundos para que las VMs terminen de bootear..."
sleep 5

echo ""
echo "==> Estado de las VMs (virsh list):"
virsh list --all

echo ""
echo "==> Verificación manual (ajusta la clave privada correspondiente a ${SSH_PUBKEY_FILE}):"
for entry in "${VMS[@]}"; do
  IFS=":" read -r vm_name vm_vcpu vm_ram vm_disk vm_ip <<< "${entry}"
  echo "  ssh -o StrictHostKeyChecking=no ubuntu@${vm_ip}   # ${vm_name}"
done
echo ""
echo "Nota: el primer boot de cloud-init puede tardar 1-3 minutos antes de que SSH responda."
echo "✓ create-testbed-vms.sh completado."
