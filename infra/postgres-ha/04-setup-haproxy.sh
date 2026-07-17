#!/bin/bash
# =============================================================================
# 04-setup-haproxy.sh — Configura HAProxy para routing PostgreSQL HA
#
# HAProxy usa health checks contra la API REST de Patroni (:8008) para
# determinar cuál nodo es el primary y cuáles son replicas.
#
# Puertos expuestos:
#   5000 — Read/Write directo a PostgreSQL (primary) — para longpolling
#   5001 — Read-Only a PostgreSQL (replicas) — para reportes pesados
#   5002 — Read/Write via PgBouncer (primary) — para HTTP workers Odoo
#   7000 — Dashboard de estadísticas
#
# Variables de entorno requeridas:
#   HAPROXY_STATS_PASSWORD — Password para el dashboard de stats
#   PG_NODE_LIST           — Inventario de todos los nodos:
#                            "name:internal_ip,name:internal_ip,..." (1 o N nodos)
# =============================================================================
set -euo pipefail

echo "══════════════════════════════════════════════════"
echo "  04-setup-haproxy.sh — Configurando HAProxy"
echo "══════════════════════════════════════════════════"

: "${HAPROXY_STATS_PASSWORD:?ERROR: HAPROXY_STATS_PASSWORD no definido}"
: "${PG_NODE_LIST:?ERROR: PG_NODE_LIST no definido}"

# ─── Líneas "server" de los backends a partir del inventario PG_NODE_LIST ───
# PG_NODE_LIST: "name:internal_ip,name:internal_ip,..." (1 o N nodos)
SERVERS_5432=""
SERVERS_6432=""
IFS=',' read -ra PG_NODE_ENTRIES <<< "$PG_NODE_LIST"
for entry in "${PG_NODE_ENTRIES[@]}"; do
  IFS=':' read -r entry_name entry_ip <<< "$entry"
  SERVERS_5432="${SERVERS_5432}    server ${entry_name} ${entry_ip}:5432 check port 8008
"
  SERVERS_6432="${SERVERS_6432}    server ${entry_name} ${entry_ip}:6432 check port 8008
"
done

# Con 1 solo nodo no existen replicas: el backend RO (5001) usa /read-only
# (el Leader también responde 200) para que los consumidores de solo-lectura
# —p.ej. los dumps de backup— sigan funcionando. Con 2+ nodos se mantiene
# /replica (solo replicas) como siempre.
if [ "${#PG_NODE_ENTRIES[@]}" -eq 1 ]; then
  RO_CHECK_PATH="/read-only"
else
  RO_CHECK_PATH="/replica"
fi

# ─── Generar configuración ──────────────────────────────────────────────────
echo "→ Generando /etc/haproxy/haproxy.cfg..."

cat > /etc/haproxy/haproxy.cfg <<EOF
# ─────────────────────────────────────────────────────────────────────────────
# HAProxy Configuration — PostgreSQL HA Cluster
# Routes traffic based on Patroni REST API health checks
# ─────────────────────────────────────────────────────────────────────────────

global
    maxconn 5000
    log /dev/log local0
    log /dev/log local1 notice
    chroot /var/lib/haproxy
    stats socket /run/haproxy/admin.sock mode 660 level admin
    stats timeout 30s
    user haproxy
    group haproxy
    daemon

defaults
    mode tcp
    log global
    option tcplog
    option dontlognull
    retries 3
    timeout connect 5s
    timeout client 30min
    timeout server 30min
    timeout check 5s

# ─────────────────────────────────────────────────────────────────────────────
# Primary PostgreSQL directo (Read/Write)
# Uso: longpolling de Odoo (LISTEN/NOTIFY), admin, DDL
# Los clientes se conectan al puerto 5000
# Solo el nodo con rol PRIMARY responde 200 en /primary
# ─────────────────────────────────────────────────────────────────────────────
listen postgres_rw
    bind *:5000
    option httpchk GET /primary
    http-check expect status 200
    default-server inter 2s downinter 5s rise 2 fall 3 maxconn 200 on-marked-down shutdown-sessions
${SERVERS_5432%$'\n'}

# ─────────────────────────────────────────────────────────────────────────────
# Replicas PostgreSQL directo (Read-Only)
# Uso: reportes pesados, analytics, lectura masiva
# Solo nodos con rol REPLICA responden 200 en /replica
# Round-robin entre replicas disponibles
# ─────────────────────────────────────────────────────────────────────────────
listen postgres_ro
    bind *:5001
    balance roundrobin
    option httpchk GET ${RO_CHECK_PATH}
    http-check expect status 200
    default-server inter 2s downinter 5s rise 2 fall 3 maxconn 200 on-marked-down shutdown-sessions
${SERVERS_5432%$'\n'}

# ─────────────────────────────────────────────────────────────────────────────
# Primary via PgBouncer (Read/Write con connection pooling)
# Uso: HTTP workers de Odoo (tráfico principal)
# Enruta al PgBouncer (:6432) del nodo PRIMARY
# ─────────────────────────────────────────────────────────────────────────────
listen pgbouncer_rw
    bind *:5002
    option httpchk GET /primary
    http-check expect status 200
    default-server inter 2s downinter 5s rise 2 fall 3 maxconn 1500 on-marked-down shutdown-sessions
${SERVERS_6432%$'\n'}

# ─────────────────────────────────────────────────────────────────────────────
# Stats Dashboard
# Acceso: http://<any-node-ip>:7000/
# Auth: admin / <HAPROXY_STATS_PASSWORD>
# ─────────────────────────────────────────────────────────────────────────────
listen stats
    bind *:7000
    mode http
    stats enable
    stats uri /
    stats refresh 5s
    stats show-legends
    stats show-node
    stats auth admin:${HAPROXY_STATS_PASSWORD}
    stats admin if TRUE
EOF

# ─── Crear directorio para socket ────────────────────────────────────────────
mkdir -p /run/haproxy

# ─── Validar configuración ──────────────────────────────────────────────────
echo "→ Validando configuración..."
if haproxy -c -f /etc/haproxy/haproxy.cfg; then
  echo "  Configuración válida ✓"
else
  echo "  ⚠️  Error en la configuración!"
  exit 1
fi

# ─── Iniciar HAProxy ────────────────────────────────────────────────────────
echo "→ Iniciando HAProxy..."
systemctl daemon-reload
systemctl enable haproxy
systemctl restart haproxy

sleep 2

# ─── Verificar ──────────────────────────────────────────────────────────────
echo "→ Verificando HAProxy..."
if systemctl is-active --quiet haproxy; then
  echo "  HAProxy activo"
else
  echo "  ⚠️  HAProxy no está activo. Revisa: journalctl -u haproxy -n 20"
  exit 1
fi

# Verificar puertos
for port in 5000 5001 5002 7000; do
  if ss -tlnp | grep -q ":${port} "; then
    echo "  Puerto ${port} escuchando ✓"
  else
    echo "  ⚠️  Puerto ${port} no escuchando"
  fi
done

echo ""
echo "══════════════════════════════════════════════════"
echo "  ✅ HAProxy configurado y activo"
echo ""
echo "  Puertos:"
echo "    5000 — Primary PostgreSQL (RW directo)"
echo "    5001 — Replicas PostgreSQL (RO)"
echo "    5002 — Primary PgBouncer (RW pooled)"
echo "    7000 — Stats Dashboard"
echo ""
echo "  Stats: http://$(hostname -I | awk '{print $1}'):7000/"
echo "  Auth:  admin / ****"
echo "══════════════════════════════════════════════════"
