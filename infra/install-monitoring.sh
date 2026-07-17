#!/bin/bash
# =============================================================================
# install-monitoring.sh
#
# Installs the full monitoring stack on K3s:
#   1. kube-prometheus-stack (Prometheus + Grafana + AlertManager)
#   2. Loki + Promtail (log aggregation)
#   3. Configures scrape targets for PG HA cluster exporters
#
# Storage: All persistent data on ${STORAGE_CLASS} StorageClass (default ceph-rbd)
#
# Variables (optional):
#   GRAFANA_PASSWORD  — Grafana admin password (default: AeiMonitor2026)
# =============================================================================
set -euo pipefail

GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-AeiMonitor2026}"
STORAGE_CLASS="${STORAGE_CLASS:-ceph-rbd}"
NAMESPACE="monitoring"

echo "══════════════════════════════════════════════════"
echo "  install-monitoring.sh — Full Monitoring Stack"
echo "══════════════════════════════════════════════════"

# ─── Prerequisites ───────────────────────────────────────────────────────────
echo "→ Checking Helm..."
if ! command -v helm &>/dev/null; then
    echo "  Installing Helm..."
    curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

echo "→ Adding Helm repos..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
helm repo add grafana https://grafana.github.io/helm-charts 2>/dev/null || true
helm repo update

echo "→ Creating namespace..."
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

# ─── Prometheus + Grafana + AlertManager ─────────────────────────────────────
echo ""
echo "→ Installing kube-prometheus-stack..."
helm upgrade --install kube-prom prometheus-community/kube-prometheus-stack \
  --namespace ${NAMESPACE} \
  --set prometheus.prometheusSpec.retention=15d \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.storageClassName=${STORAGE_CLASS} \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.accessModes[0]=ReadWriteOnce \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=20Gi \
  --set grafana.persistence.enabled=true \
  --set grafana.persistence.storageClassName=${STORAGE_CLASS} \
  --set grafana.persistence.size=5Gi \
  --set grafana.adminPassword="${GRAFANA_PASSWORD}" \
  --set alertmanager.enabled=true \
  --set alertmanager.alertmanagerSpec.storage.volumeClaimTemplate.spec.storageClassName=${STORAGE_CLASS} \
  --set alertmanager.alertmanagerSpec.storage.volumeClaimTemplate.spec.accessModes[0]=ReadWriteOnce \
  --set alertmanager.alertmanagerSpec.storage.volumeClaimTemplate.spec.resources.requests.storage=2Gi \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[0].job_name=postgres-exporters" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[0].static_configs[0].targets[0]=192.168.0.127:9187" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[0].static_configs[0].targets[1]=192.168.0.186:9187" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[0].static_configs[0].targets[2]=192.168.0.226:9187" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[0].static_configs[0].labels.cluster=odoo-saas-ha" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[1].job_name=node-exporters-pg" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[1].static_configs[0].targets[0]=192.168.0.127:9100" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[1].static_configs[0].targets[1]=192.168.0.186:9100" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[1].static_configs[0].targets[2]=192.168.0.226:9100" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[1].static_configs[0].labels.cluster=odoo-saas-ha" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[2].job_name=patroni" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[2].metrics_path=/metrics" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[2].static_configs[0].targets[0]=192.168.0.127:8008" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[2].static_configs[0].targets[1]=192.168.0.186:8008" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[2].static_configs[0].targets[2]=192.168.0.226:8008" \
  --set "prometheus.prometheusSpec.additionalScrapeConfigs[2].static_configs[0].labels.cluster=odoo-saas-ha" \
  --wait --timeout 5m

# ─── Loki + Promtail (logs) ─────────────────────────────────────────────────
echo ""
echo "→ Installing Loki + Promtail..."
helm upgrade --install loki grafana/loki-stack \
  --namespace ${NAMESPACE} \
  --set grafana.enabled=false \
  --set promtail.enabled=true \
  --set loki.persistence.enabled=true \
  --set loki.persistence.storageClassName=${STORAGE_CLASS} \
  --set loki.persistence.size=50Gi \
  --set "loki.config.table_manager.retention_deletes_enabled=true" \
  --set "loki.config.table_manager.retention_period=744h" \
  --set "loki.config.chunk_store_config.max_look_back_period=744h" \
  --wait --timeout 3m

# ─── Add Loki datasource to Grafana ─────────────────────────────────────────
echo ""
echo "→ Adding Loki datasource to Grafana..."
GRAFANA_POD=$(kubectl -n ${NAMESPACE} get pod -l app.kubernetes.io/name=grafana -o name | head -1)
kubectl -n ${NAMESPACE} exec ${GRAFANA_POD} -c grafana -- \
  curl -s -X POST http://localhost:3000/api/datasources \
    -H "Content-Type: application/json" \
    -u "admin:${GRAFANA_PASSWORD}" \
    -d '{"name":"Loki","type":"loki","url":"http://loki.monitoring.svc:3100","access":"proxy","isDefault":false}' \
  2>/dev/null || echo "  (Loki datasource may already exist)"

# ─── Grafana Ingress ─────────────────────────────────────────────────────────
echo ""
echo "→ Creating Grafana Ingress..."
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: grafana-ingress
  namespace: ${NAMESPACE}
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web,websecure
spec:
  rules:
    - host: grafana.aeisoftware.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: kube-prom-grafana
                port:
                  number: 80
EOF

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "  ✅ Monitoring stack installed"
echo ""
echo "  Components:"
echo "    Prometheus     → 20Gi storage, 15d retention"
echo "    Grafana        → 5Gi storage, persistent dashboards"
echo "    AlertManager   → 2Gi storage"
echo "    Loki           → 50Gi storage, 31d retention (log aggregation)"
echo "    Promtail       → DaemonSet on all nodes"
echo ""
echo "  Scrape Targets:"
echo "    K3s cluster    → apiserver, kubelet, coredns"
echo "    K3s nodes      → node-exporter (3 nodes)"
echo "    PG HA nodes    → postgres_exporter (3 nodes)"
echo "    PG HA nodes    → node-exporter (3 nodes)"
echo "    PG HA cluster  → Patroni REST API (3 nodes)"
echo ""
echo "  Access:"
echo "    Grafana UI     → https://grafana.aeisoftware.com"
echo "    Grafana login  → admin / ${GRAFANA_PASSWORD}"
echo ""
echo "  Useful commands:"
echo "    kubectl -n monitoring get pods"
echo "    kubectl -n monitoring port-forward svc/kube-prom-grafana 3000:80"
echo "    kubectl -n monitoring port-forward svc/kube-prom-kube-prometheus-prometheus 9090:9090"
echo "══════════════════════════════════════════════════"
