#!/bin/bash

# =========================================================================
# Script de Configuración Inicial - Replicación de Servidor Odoo SaaS
# Basado en la configuración extraída del servidor original (Ubuntu 24.04)
# =========================================================================

set -e

echo "[1/3] Configurando parámetros de optimización del Kernel (Inotify & Swappiness)..."

# 1. Ajustar límites de inotify para los watchdogs de Odoo 19
cat <<EOF | sudo tee /etc/sysctl.d/99-oecsh-inotify.conf
# oec.sh: raised inotify limits for Odoo 19 watchdog file monitoring
# Odoo scans ~14,000+ module directories at startup; the default (8,192) is too low.
fs.inotify.max_user_watches=524288
fs.inotify.max_user_instances=512
EOF

# 2. Configurar perfil de memoria Swap para priorizar RAM (Ideal para la DB PostgreSQL)
cat <<EOF | sudo tee /etc/sysctl.d/99-swap.conf
# Priorizar uso de memoria RAM sobre disco, ideal para PostgreSQL
vm.swappiness=10
EOF

# Aplicamos los cambios en caliente sin reiniciar
sudo sysctl -p /etc/sysctl.d/99-oecsh-inotify.conf
sudo sysctl -p /etc/sysctl.d/99-swap.conf

echo "[2/3] Preparando estructura de directorios y volúmenes para Docker..."

# Directorio base del proyecto
BASE_DIR="/opt/odoo-saas"
sudo mkdir -p $BASE_DIR/{traefik,odoo_instance}

# Subdirectorios para Traefik
sudo mkdir -p $BASE_DIR/traefik/{acme,dynamic,certs,plugins-local}
# Crear archivo de certificados para el acme resolver (Debe tener permisos 600)
sudo touch $BASE_DIR/traefik/acme/acme.json
sudo chmod 600 $BASE_DIR/traefik/acme/acme.json

# Subdirectorios para el entorno Odoo (replicando ee8aaad1-94cb-45c1-b087-836dd4e2aa0b)
sudo mkdir -p $BASE_DIR/odoo_instance/{addons,data,logs}

# Script simulado de auto-renovación de wildcard
sudo mkdir -p $BASE_DIR/scripts
cat <<'EOF' | sudo tee $BASE_DIR/scripts/fetch-wildcard-cert.sh
#!/bin/bash
# Mock script - Aquí iba la lógica de fetch-wildcard-cert.sh
echo "Sincronizando certificados Let's Encrypt Wildcard..."
EOF
sudo chmod +x $BASE_DIR/scripts/fetch-wildcard-cert.sh


echo "[3/3] Estructura creada con éxito. Procede a ejecutar: docker-compose up -d en $BASE_DIR"
