#!/bin/bash
# =============================================================================
# deploy-all.sh — Orquestador de despliegue del clúster PostgreSQL HA
#
# Ejecuta TODOS los scripts en las 3 VMs en el orden correcto.
# Se ejecuta desde tu máquina local (no desde las VMs).
#
# Prerequisitos:
#   1. Acceso SSH a las 3 VMs con la clave ~/.ssh/id_rsa
#   2. RadosGW habilitado (ver plan de implementación)
#   3. Archivo .env con las credenciales S3 (copiar de .env.example)
#
# Uso:
#   cp .env.example .env
#   nano .env   # completar credenciales RadosGW
#   ./deploy-all.sh
#
# Las contraseñas de PostgreSQL se generan automáticamente la primera vez.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║  PostgreSQL HA Cluster — Despliegue Automatizado        ║"
echo "  ║  N nodos: Patroni + etcd + PgBouncer + HAProxy          ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""

# ─── Cargar inventario de entorno ────────────────────────────────────────────
# Primer argumento posicional: ruta al env file (infra/environments/*.env).
# Sin argumento, se usa cotas.env (comportamiento actual = default).
ENV_FILE="${1:-${REPO_ROOT}/infra/environments/cotas.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "  ✗ Archivo de entorno no encontrado: ${ENV_FILE}"
  echo "    Uso: $0 [ruta/al/entorno.env]"
  exit 1
fi

echo "→ Cargando inventario de entorno: ${ENV_FILE}"
source "$ENV_FILE"

# ─── SSH Config (desde el env file) ──────────────────────────────────────────
SSH_KEY="${SSH_KEY:?ERROR: SSH_KEY no definido en ${ENV_FILE}}"
SSH_USER="${SSH_USER:?ERROR: SSH_USER no definido en ${ENV_FILE}}"
SSH_OPTS="-i ${SSH_KEY} -o StrictHostKeyChecking=no -o ConnectTimeout=10"

# ─── Nodos: name:ssh_ip:internal_ip (desde PG_NODES del env file) ───────────
NODES=("${PG_NODES[@]}")

# ─── Lista de nodos para propagar a los scripts remotos ──────────────────────
# Formato: "name:internal_ip,name:internal_ip,..." (usado por etcd/patroni/haproxy)
PG_NODE_LIST=""
for node in "${NODES[@]}"; do
  IFS=':' read -r name ssh_ip internal_ip <<< "$node"
  if [ -z "$PG_NODE_LIST" ]; then
    PG_NODE_LIST="${name}:${internal_ip}"
  else
    PG_NODE_LIST="${PG_NODE_LIST},${name}:${internal_ip}"
  fi
done

# ─── Endpoint S3 para pgBackRest (stunnel local o directo, según entorno) ────
if [ "${S3_USE_STUNNEL:-true}" = "true" ]; then
  S3_REPO_ENDPOINT="${S3_REPO_ENDPOINT:-127.0.0.1:18480}"
else
  S3_REPO_ENDPOINT="${S3_REPO_ENDPOINT:?ERROR: S3_REPO_ENDPOINT no definido (requerido con S3_USE_STUNNEL=false)}"
fi

# ─── Cargar variables de entorno (.env, con variante por entorno) ────────────
# Para entornos distintos de cotas se usa .env.<ENV_NAME> / .secrets.generated.<ENV_NAME>
# para no mezclar credenciales entre entornos.
ENV_SUFFIX=""
if [ "${ENV_NAME:-cotas}" != "cotas" ]; then
  ENV_SUFFIX=".${ENV_NAME}"
fi

DOTENV_FILE="${SCRIPT_DIR}/.env${ENV_SUFFIX}"
if [ -f "${DOTENV_FILE}" ]; then
  echo "→ Cargando ${DOTENV_FILE}..."
  set -a
  source "${DOTENV_FILE}"
  set +a
else
  echo "⚠️  Archivo ${DOTENV_FILE} no encontrado."
  echo "   Copia .env.example a ${DOTENV_FILE} y completa las credenciales S3:"
  echo "   cp ${SCRIPT_DIR}/.env.example ${DOTENV_FILE}"
  exit 1
fi

# ─── Generar contraseñas automáticamente ─────────────────────────────────────
SECRETS_FILE="${SCRIPT_DIR}/.secrets.generated${ENV_SUFFIX}"

if [ ! -f "$SECRETS_FILE" ]; then
  echo "→ Generando contraseñas automáticamente..."
  cat > "$SECRETS_FILE" <<EOF
# Auto-generated passwords — $(date -Iseconds)
# ⚠️  NUNCA commitear este archivo. Está en .gitignore
DB_PASSWORD=$(openssl rand -base64 24 | tr -d '=/+' | head -c 32)
REPLICATOR_PASSWORD=$(openssl rand -base64 24 | tr -d '=/+' | head -c 32)
PG_SUPERUSER_PASSWORD=$(openssl rand -base64 24 | tr -d '=/+' | head -c 32)
HAPROXY_STATS_PASSWORD=$(openssl rand -base64 16 | tr -d '=/+' | head -c 16)
BACKUP_ENCRYPTION_KEY=$(openssl rand -base64 32 | tr -d '=/+' | head -c 48)
EOF
  chmod 600 "$SECRETS_FILE"
  echo "  ✅ Contraseñas guardadas en: $SECRETS_FILE"
  echo ""
  echo "  ╔════════════════════════════════════════════════════════╗"
  echo "  ║  ⚠️  GUARDA ESTE ARCHIVO EN UN LUGAR SEGURO           ║"
  echo "  ║  Sin él no podrás conectarte al clúster ni restaurar  ║"
  echo "  ║  backups. NUNCA hacer git commit de este archivo.     ║"
  echo "  ╚════════════════════════════════════════════════════════╝"
  echo ""
else
  echo "→ Usando contraseñas existentes de: $SECRETS_FILE"
fi

set -a
source "$SECRETS_FILE"
set +a

# ─── Validar que tenemos todas las variables ─────────────────────────────────
echo "→ Validando variables de entorno..."

REQUIRED_VARS=(DB_PASSWORD REPLICATOR_PASSWORD PG_SUPERUSER_PASSWORD HAPROXY_STATS_PASSWORD BACKUP_ENCRYPTION_KEY)
for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var:-}" ]; then
    echo "  ✗ ${var} no definido"
    exit 1
  fi
  echo "  ✓ ${var}"
done

# Variables de S3 (opcionales si no hay RadosGW aún)
S3_VARS=(RADOSGW_ENDPOINT S3_ACCESS_KEY S3_SECRET_KEY)
S3_READY=true
for var in "${S3_VARS[@]}"; do
  if [ -z "${!var:-}" ] || [[ "${!var}" == *"<"* ]]; then
    echo "  ⊘ ${var} — no configurado (pgBackRest se saltará)"
    S3_READY=false
  else
    echo "  ✓ ${var}"
  fi
done

# ─── Verificar conectividad SSH ──────────────────────────────────────────────
echo ""
echo "→ Verificando conectividad SSH..."
for node in "${NODES[@]}"; do
  IFS=':' read -r name ssh_ip internal_ip <<< "$node"
  if ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} "echo OK" &>/dev/null; then
    echo "  ✓ ${name} (${ssh_ip})"
  else
    echo "  ✗ ${name} (${ssh_ip}) — No se puede conectar"
    echo "    Verifica: ssh -i ${SSH_KEY} ${SSH_USER}@${ssh_ip}"
    exit 1
  fi
done

# ─── Función helper para ejecutar scripts remotamente ────────────────────────
run_remote() {
  local name="$1"
  local ssh_ip="$2"
  local internal_ip="$3"
  local script="$4"

  echo ""
  echo "  ┌─────────────────────────────────────────────"
  echo "  │ ${script} → ${name} (${ssh_ip})"
  echo "  └─────────────────────────────────────────────"

  # Construir exports de variables
  local env_exports
  env_exports="export NODE_NAME='${name}';"
  env_exports+="export NODE_IP='${internal_ip}';"
  env_exports+="export DB_PASSWORD='${DB_PASSWORD}';"
  env_exports+="export REPLICATOR_PASSWORD='${REPLICATOR_PASSWORD}';"
  env_exports+="export PG_SUPERUSER_PASSWORD='${PG_SUPERUSER_PASSWORD}';"
  env_exports+="export HAPROXY_STATS_PASSWORD='${HAPROXY_STATS_PASSWORD}';"
  env_exports+="export BACKUP_ENCRYPTION_KEY='${BACKUP_ENCRYPTION_KEY}';"
  env_exports+="export RADOSGW_ENDPOINT='${RADOSGW_ENDPOINT:-}';"
  env_exports+="export S3_ACCESS_KEY='${S3_ACCESS_KEY:-}';"
  env_exports+="export S3_SECRET_KEY='${S3_SECRET_KEY:-}';"
  env_exports+="export S3_BUCKET='${S3_BUCKET:-pg-backups}';"
  env_exports+="export PG_NODE_LIST='${PG_NODE_LIST}';"
  env_exports+="export S3_REPO_ENDPOINT='${S3_REPO_ENDPOINT}';"
  env_exports+="export S3_USE_STUNNEL='${S3_USE_STUNNEL:-true}';"

  ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} \
    "sudo bash -c '${env_exports} bash -s'" < "${SCRIPT_DIR}/${script}"
}

# ─── Tiempo total ────────────────────────────────────────────────────────────
START_TIME=$(date +%s)

# =============================================================================
# PASO 1: Instalar paquetes en los 3 nodos
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PASO 1/6: Instalando paquetes base"
echo "═══════════════════════════════════════════════════════════"

for node in "${NODES[@]}"; do
  IFS=':' read -r name ssh_ip internal_ip <<< "$node"

  # Limpiar PPA vbernat roto (si quedó de una ejecución anterior fallida)
  echo "  → Limpiando PPA vbernat en ${name}..."
  ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} "sudo rm -f \
    /etc/apt/sources.list.d/vbernat-ubuntu-haproxy*.list \
    /etc/apt/sources.list.d/*haproxy*.list \
    /etc/apt/sources.list.d/*vbernat*.list 2>/dev/null; \
    sudo apt-get update -qq 2>/dev/null || true"

  run_remote "$name" "$ssh_ip" "$internal_ip" "00-install-base.sh"
done

# =============================================================================
# PASO 2: Configurar etcd en los 3 nodos
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PASO 2/6: Configurando etcd cluster"
echo "═══════════════════════════════════════════════════════════"
echo "  NOTA: etcd necesita quórum (2/3 nodos). Se lanza en los 3"
echo "  nodos primero, luego se verifica el clúster."

# Lanzar etcd en los 3 nodos (01-setup-etcd.sh solo inicia el servicio,
# NO espera quórum — la verificación se hace después)
for node in "${NODES[@]}"; do
  IFS=':' read -r name ssh_ip internal_ip <<< "$node"
  run_remote "$name" "$ssh_ip" "$internal_ip" "01-setup-etcd.sh"
done

# Ahora que los 3 etcd están corriendo, esperar a que alcancen quórum
echo ""
echo "→ Esperando a que etcd cluster forme quórum (30s)..."
sleep 30

# Verificar etcd cluster health (todos los endpoints)
echo "→ Verificando etcd cluster..."
IFS=':' read -r name ssh_ip internal_ip <<< "${NODES[0]}"

# Construir --endpoints= a partir de las internal_ip de todos los nodos
ETCD_ENDPOINTS=""
for node in "${NODES[@]}"; do
  IFS=':' read -r n_name n_ssh_ip n_internal_ip <<< "$node"
  if [ -z "$ETCD_ENDPOINTS" ]; then
    ETCD_ENDPOINTS="http://${n_internal_ip}:2379"
  else
    ETCD_ENDPOINTS="${ETCD_ENDPOINTS},http://${n_internal_ip}:2379"
  fi
done

for attempt in 1 2 3; do
  if ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} "sudo etcdctl endpoint health \
    --endpoints=${ETCD_ENDPOINTS} \
    --write-out=table 2>&1"; then
    break
  fi
  echo "  Intento ${attempt}/3 fallido, esperando 10s..."
  sleep 10
done

# =============================================================================
# PASO 3: Configurar Patroni + PostgreSQL (secuencial: leader primero)
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PASO 3/6: Configurando Patroni + PostgreSQL"
echo "  (nodo 1 primero → se convierte en Leader)"
echo "═══════════════════════════════════════════════════════════"

LAST_INDEX=$(( ${#NODES[@]} - 1 ))

for i in "${!NODES[@]}"; do
  IFS=':' read -r name ssh_ip internal_ip <<< "${NODES[$i]}"
  run_remote "$name" "$ssh_ip" "$internal_ip" "02-setup-patroni.sh"

  # Los sleeps solo tienen sentido si queda al menos un nodo más por configurar
  # (con 1 solo nodo, i==0==LAST_INDEX y no hay siguiente nodo que esperar).
  if [ "$i" -lt "$LAST_INDEX" ]; then
    if [ "$i" -eq 0 ]; then
      # Nodo 1 inicializa el clúster PG desde cero — darle más tiempo
      echo "→ Nodo 1 inicializando PostgreSQL, esperando 30s..."
      sleep 30
    else
      echo "→ Esperando 20s antes del siguiente nodo..."
      sleep 20
    fi
  fi
done

echo ""
echo "→ Verificando clúster Patroni..."
IFS=':' read -r name ssh_ip internal_ip <<< "${NODES[0]}"
ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} "sudo patronictl -c /etc/patroni/patroni.yml list"

# =============================================================================
# PASO 4: Configurar PgBouncer + HAProxy
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PASO 4/6: Configurando PgBouncer + HAProxy"
echo "═══════════════════════════════════════════════════════════"

for node in "${NODES[@]}"; do
  IFS=':' read -r name ssh_ip internal_ip <<< "$node"
  run_remote "$name" "$ssh_ip" "$internal_ip" "03-setup-pgbouncer.sh"
done

for node in "${NODES[@]}"; do
  IFS=':' read -r name ssh_ip internal_ip <<< "$node"
  run_remote "$name" "$ssh_ip" "$internal_ip" "04-setup-haproxy.sh"
done

# =============================================================================
# PASO 5: Configurar pgBackRest (si S3 está disponible)
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PASO 5/6: Configurando pgBackRest"
echo "═══════════════════════════════════════════════════════════"

if [ "$S3_READY" = true ]; then
  if [ "${S3_USE_STUNNEL:-true}" = "true" ]; then
    # 05b: Stunnel TLS proxy (pgBackRest necesita HTTPS, RadosGW solo tiene HTTP)
    echo "→ Configurando stunnel como proxy TLS para S3/RadosGW..."
    for node in "${NODES[@]}"; do
      IFS=':' read -r name ssh_ip internal_ip <<< "$node"
      run_remote "$name" "$ssh_ip" "$internal_ip" "05b-setup-stunnel-s3proxy.sh"
    done
  else
    echo "  ⊘ S3_USE_STUNNEL=false — saltando proxy stunnel (conexión directa a ${S3_REPO_ENDPOINT})"
  fi

  # 05: pgBackRest (usa S3_REPO_ENDPOINT — stunnel local o endpoint directo)
  for node in "${NODES[@]}"; do
    IFS=':' read -r name ssh_ip internal_ip <<< "$node"
    run_remote "$name" "$ssh_ip" "$internal_ip" "05-setup-pgbackrest.sh"
  done
else
  echo "  ⊘ S3/RadosGW no configurado. Saltando pgBackRest."
  echo "  Cuando tengas RadosGW listo, ejecuta manualmente:"
  echo "  ./deploy-all.sh --only 05-setup-pgbackrest.sh"
fi

# =============================================================================
# PASO 6: Configurar monitoreo
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PASO 6/6: Configurando monitoreo"
echo "═══════════════════════════════════════════════════════════"

for node in "${NODES[@]}"; do
  IFS=':' read -r name ssh_ip internal_ip <<< "$node"
  run_remote "$name" "$ssh_ip" "$internal_ip" "06-setup-monitoring.sh"
done

# =============================================================================
# VALIDACIÓN FINAL
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  VALIDACIÓN FINAL"
echo "═══════════════════════════════════════════════════════════"

IFS=':' read -r name ssh_ip internal_ip <<< "${NODES[0]}"

echo ""
echo "→ Estado del clúster Patroni:"
ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} "sudo patronictl -c /etc/patroni/patroni.yml list"

echo ""
echo "→ Test de conexión via HAProxy (RW → Primary):"
ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} \
  "PGPASSWORD='${DB_PASSWORD}' psql -h ${internal_ip} -p 5000 -U odoo -d postgres -c 'SELECT NOT pg_is_in_recovery() AS is_primary;'" || \
  echo "  (Test de conexión falló — verificar manualmente)"

echo ""
echo "→ Test de conexión via PgBouncer (pooled):"
ssh ${SSH_OPTS} ${SSH_USER}@${ssh_ip} \
  "PGPASSWORD='${DB_PASSWORD}' psql -h ${internal_ip} -p 5002 -U odoo -d postgres -c 'SELECT version();'" || \
  echo "  (Test de conexión falló — verificar manualmente)"

# ─── Resumen ─────────────────────────────────────────────────────────────────
END_TIME=$(date +%s)
ELAPSED=$(( END_TIME - START_TIME ))

# Construir lista de IPs internas (para el banner de endpoints)
NODE_IPS_CSV=""
for node in "${NODES[@]}"; do
  IFS=':' read -r n_name n_ssh_ip n_internal_ip <<< "$node"
  if [ -z "$NODE_IPS_CSV" ]; then
    NODE_IPS_CSV="${n_internal_ip}"
  else
    NODE_IPS_CSV="${NODE_IPS_CSV},${n_internal_ip}"
  fi
done
IFS=':' read -r first_name first_ssh_ip first_internal_ip <<< "${NODES[0]}"

echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║                ✅ DESPLIEGUE COMPLETADO                  ║"
echo "  ╠══════════════════════════════════════════════════════════╣"
echo "  ║                                                          ║"
echo "  ║  Tiempo total: $(printf '%02d:%02d:%02d' $((ELAPSED/3600)) $(((ELAPSED%3600)/60)) $((ELAPSED%60)))                              ║"
echo "  ║                                                          ║"
echo "  ║  Endpoints de conexión:                                  ║"
echo "  ║    RW directo:  ${NODE_IPS_CSV}:5000"
echo "  ║    RO replicas: ${NODE_IPS_CSV}:5001"
echo "  ║    RW pooled:   ${NODE_IPS_CSV}:5002"
echo "  ║    HAProxy UI:  http://${first_internal_ip}:7000"
echo "  ║                                                          ║"
echo "  ║  Credenciales: ${SECRETS_FILE}"
echo "  ║                                                          ║"
echo "  ║  Siguiente paso: Fase 2 — Conectar K3s al clúster       ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""
