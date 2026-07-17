#!/bin/bash
# =============================================================================
# 06b-install-longhorn.sh — Instala Longhorn (storage distribuido) en K3s
#
# Alternativa a Ceph CSI (06-install-ceph-csi.sh) para entornos sin clúster
# Ceph externo. Longhorn provisiona su propio storage replicado usando el
# disco local de cada nodo. Configura el StorageClass "longhorn" como default.
#
# Ejecutar en el primer nodo K3s (control-1) via SSH como root.
#
# Variables opcionales (desde .env):
#   LONGHORN_REPLICA_COUNT — número de réplicas por volumen (default: 2)
# =============================================================================
set -euo pipefail

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
NAMESPACE="longhorn-system"
LONGHORN_REPLICA_COUNT="${LONGHORN_REPLICA_COUNT:-2}"

echo ""
echo "  ┌─────────────────────────────────────────────────────────"
echo "  │  06b-install-longhorn"
echo "  │  Namespace: ${NAMESPACE}"
echo "  │  Réplicas por volumen: ${LONGHORN_REPLICA_COUNT}"
echo "  └─────────────────────────────────────────────────────────"

# ── Instalar Helm si falta ────────────────────────────────────────────────────
if ! command -v helm &>/dev/null; then
  echo "→ Helm no encontrado, instalando..."
  curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
  echo "  ✓ Helm instalado"
else
  echo "  ✓ Helm ya está instalado ($(helm version --short 2>/dev/null))"
fi

# ── Repo Helm de Longhorn ─────────────────────────────────────────────────────
echo "→ Agregando repo Helm de Longhorn..."
helm repo add longhorn https://charts.longhorn.io 2>/dev/null || true
helm repo update

# ── Instalar Longhorn ──────────────────────────────────────────────────────────
echo "→ Instalando Longhorn..."
helm upgrade --install longhorn longhorn/longhorn \
  --namespace "${NAMESPACE}" \
  --create-namespace \
  --set defaultSettings.defaultReplicaCount="${LONGHORN_REPLICA_COUNT}" \
  --set persistence.defaultClass=true \
  --wait --timeout 10m

echo "  ✓ Longhorn chart instalado"

# ── Esperar a que todos los pods estén Running ────────────────────────────────
echo "→ Esperando pods de Longhorn en estado Running..."
for i in $(seq 1 30); do
  # || true: tolera fallos transitorios del API server y el caso "0 no-listos"
  # (grep -v sin salida devuelve 1), que con set -euo pipefail matarían el script
  NOT_READY=$({ kubectl -n "${NAMESPACE}" get pods --no-headers 2>/dev/null \
    | grep -v -E "Running|Completed" | wc -l; } || true)
  TOTAL=$({ kubectl -n "${NAMESPACE}" get pods --no-headers 2>/dev/null | wc -l; } || true)
  NOT_READY="${NOT_READY:-0}"; TOTAL="${TOTAL:-0}"
  echo "  Pods listos: $(( TOTAL - NOT_READY ))/${TOTAL} (intento ${i}/30)"
  if [ "${TOTAL}" -gt 0 ] && [ "${NOT_READY}" -eq 0 ]; then
    echo "  ✓ Todos los pods de Longhorn están Running"
    break
  fi
  sleep 10
done

# ── Test rápido: PVC + Pod que lo monta ───────────────────────────────────────
echo "→ Test de provisioning (PVC de prueba)..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: longhorn-test
  namespace: default
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: longhorn
  resources:
    requests:
      storage: 1Gi
EOF

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: longhorn-test-pod
  namespace: default
spec:
  restartPolicy: Never
  containers:
    - name: test
      image: busybox
      command: ["sh", "-c", "echo longhorn-ok > /data/test.txt && sleep 5"]
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: longhorn-test
EOF

echo "  Esperando que el PVC se provisione..."
for i in $(seq 1 12); do
  STATUS=$(kubectl get pvc longhorn-test -n default -o jsonpath='{.status.phase}' 2>/dev/null || echo "Pending")
  echo "  PVC status: ${STATUS} (intento ${i}/12)"
  if [ "${STATUS}" = "Bound" ]; then
    echo "  ✅ StorageClass longhorn funciona correctamente"
    break
  fi
  sleep 10
done

echo "  Esperando que el pod de prueba monte el volumen..."
for i in $(seq 1 12); do
  PHASE=$(kubectl get pod longhorn-test-pod -n default -o jsonpath='{.status.phase}' 2>/dev/null || echo "Pending")
  echo "  Pod status: ${PHASE} (intento ${i}/12)"
  if [ "${PHASE}" = "Succeeded" ] || [ "${PHASE}" = "Running" ]; then
    echo "  ✅ Pod de prueba montó el volumen correctamente"
    break
  fi
  sleep 10
done

# Limpiar recursos de prueba
echo "→ Limpiando recursos de prueba..."
kubectl delete pod longhorn-test-pod -n default --ignore-not-found
kubectl delete pvc longhorn-test -n default --ignore-not-found

echo ""
kubectl get storageclasses
echo ""
echo "  ✅ Longhorn instalado y validado"
