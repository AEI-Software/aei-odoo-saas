#!/usr/bin/env bash
# =============================================================================
# infra/testbed/setup-minio.sh
#
# Instala y arranca MinIO (con TLS self-signed) en pg-test-1 (10.9.13.24) del
# testbed de portabilidad, simulando el S3 usado por pgBackRest para backups
# de PostgreSQL (bucket pg-backups).
#
# Se ejecuta EN la VM pg-test-1, como root. Idempotente.
#
# Uso:
#   sudo bash infra/testbed/setup-minio.sh
# =============================================================================
set -euo pipefail

MINIO_IP="10.9.13.24"
MINIO_BIN_URL="https://dl.min.io/server/minio/release/linux-amd64/minio"
MC_BIN_URL="https://dl.min.io/client/mc/release/linux-amd64/mc"

MINIO_USER="minio-user"
MINIO_HOME="/home/${MINIO_USER}"
MINIO_DATA_DIR="/var/lib/minio"
MINIO_CERT_DIR="${MINIO_HOME}/.minio/certs"
MINIO_ENV_FILE="/etc/default/minio"
MINIO_UNIT_FILE="/etc/systemd/system/minio.service"
CREDS_FILE="/root/minio-credentials.txt"
BUCKET_NAME="pg-backups"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "✗ Este script debe ejecutarse como root (sudo)."
  exit 1
fi

# ── Usuario de sistema ────────────────────────────────────────────────────────
if id "${MINIO_USER}" &>/dev/null; then
  echo "✓ Usuario ${MINIO_USER} ya existe"
else
  echo "→ Creando usuario de sistema ${MINIO_USER}..."
  useradd --system --home-dir "${MINIO_HOME}" --create-home --shell /usr/sbin/nologin "${MINIO_USER}"
  echo "  ✓ ${MINIO_USER} creado"
fi

# ── Binarios ───────────────────────────────────────────────────────────────────
if [[ -x /usr/local/bin/minio ]]; then
  echo "✓ Binario minio ya presente"
else
  echo "→ Descargando binario minio..."
  curl -fL --retry 3 -o /usr/local/bin/minio "${MINIO_BIN_URL}"
  chmod +x /usr/local/bin/minio
  echo "  ✓ /usr/local/bin/minio instalado"
fi

if [[ -x /usr/local/bin/mc ]]; then
  echo "✓ Binario mc ya presente"
else
  echo "→ Descargando cliente mc..."
  curl -fL --retry 3 -o /usr/local/bin/mc "${MC_BIN_URL}"
  chmod +x /usr/local/bin/mc
  echo "  ✓ /usr/local/bin/mc instalado"
fi

# ── Directorio de datos ───────────────────────────────────────────────────────
mkdir -p "${MINIO_DATA_DIR}"
chown -R "${MINIO_USER}:${MINIO_USER}" "${MINIO_DATA_DIR}"
echo "✓ Data dir ${MINIO_DATA_DIR} listo"

# ── Certificado TLS self-signed (MinIO habilita TLS solo si ve estos archivos) ─
mkdir -p "${MINIO_CERT_DIR}"
if [[ -f "${MINIO_CERT_DIR}/public.crt" && -f "${MINIO_CERT_DIR}/private.key" ]]; then
  echo "✓ Certificado TLS ya presente en ${MINIO_CERT_DIR} — se reutiliza"
else
  echo "→ Generando certificado self-signed (CN=${MINIO_IP}, SAN=IP:${MINIO_IP})..."
  openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
    -keyout "${MINIO_CERT_DIR}/private.key" \
    -out "${MINIO_CERT_DIR}/public.crt" \
    -subj "/CN=${MINIO_IP}" \
    -addext "subjectAltName=IP:${MINIO_IP}"
  echo "  ✓ Certificado generado"
fi
chown -R "${MINIO_USER}:${MINIO_USER}" "${MINIO_HOME}/.minio"
chmod 600 "${MINIO_CERT_DIR}/private.key"

# ── Credenciales root ──────────────────────────────────────────────────────────
if [[ -f "${CREDS_FILE}" ]]; then
  echo "✓ Credenciales ya existen en ${CREDS_FILE} — se reutilizan"
  # shellcheck disable=SC1090
  source "${CREDS_FILE}"
else
  echo "→ Generando credenciales root..."
  MINIO_ROOT_USER="admin-$(openssl rand -hex 4)"
  MINIO_ROOT_PASSWORD="$(openssl rand -base64 24 | tr -d '=+/')"
  cat > "${CREDS_FILE}" <<EOF
MINIO_ROOT_USER=${MINIO_ROOT_USER}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
EOF
  chmod 600 "${CREDS_FILE}"
  echo "  ✓ Credenciales guardadas en ${CREDS_FILE} (chmod 600)"
fi

# ── Environment file para systemd ──────────────────────────────────────────────
cat > "${MINIO_ENV_FILE}" <<EOF
MINIO_ROOT_USER=${MINIO_ROOT_USER}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
MINIO_VOLUMES=${MINIO_DATA_DIR}
EOF
chmod 600 "${MINIO_ENV_FILE}"
echo "✓ ${MINIO_ENV_FILE} escrito"

# ── Unit systemd ────────────────────────────────────────────────────────────────
cat > "${MINIO_UNIT_FILE}" <<EOF
[Unit]
Description=MinIO (testbed pg-backups)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${MINIO_USER}
Group=${MINIO_USER}
EnvironmentFile=${MINIO_ENV_FILE}
ExecStart=/usr/local/bin/minio server ${MINIO_DATA_DIR} --console-address :9001
Restart=on-failure
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
echo "✓ ${MINIO_UNIT_FILE} escrito"

systemctl daemon-reload
systemctl enable --now minio.service
echo "✓ minio.service habilitado y arrancado"

# ── Esperar a que el endpoint responda ────────────────────────────────────────
echo "→ Esperando a que MinIO responda en https://127.0.0.1:9000 ..."
for i in $(seq 1 30); do
  if curl -sk -o /dev/null "https://127.0.0.1:9000/minio/health/live"; then
    echo "  ✓ MinIO respondiendo"
    break
  fi
  if [[ "${i}" -eq 30 ]]; then
    echo "✗ MinIO no respondió tras 30 intentos. Revisa: journalctl -u minio -n 50"
    exit 1
  fi
  sleep 2
done

# ── Alias mc + bucket ──────────────────────────────────────────────────────────
echo "→ Configurando alias mc y creando bucket ${BUCKET_NAME}..."
export MC_HOST_local=""
/usr/local/bin/mc alias set local "https://127.0.0.1:9000" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" --insecure

if /usr/local/bin/mc ls "local/${BUCKET_NAME}" --insecure &>/dev/null; then
  echo "  ✓ Bucket ${BUCKET_NAME} ya existe"
else
  /usr/local/bin/mc mb "local/${BUCKET_NAME}" --insecure
  echo "  ✓ Bucket ${BUCKET_NAME} creado"
fi

# ── Resumen ────────────────────────────────────────────────────────────────────
echo ""
echo "==> MinIO listo."
echo "    Endpoint S3:      https://${MINIO_IP}:9000  (TLS self-signed, usar verify-tls=n / --insecure)"
echo "    Consola web:      https://${MINIO_IP}:9001"
echo "    Bucket:           ${BUCKET_NAME}"
echo "    Credenciales:     ${CREDS_FILE} (chmod 600)"
echo "✓ setup-minio.sh completado."
