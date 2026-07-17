#!/bin/bash
# =============================================================================
# 05-install-traefik.sh — Instala Traefik v3 via Helm en el clúster K3s HA
#
# Ejecutado desde k3s-control-1 DESPUÉS de que los 3 nodos estén Ready.
# Traefik escucha en el VIP (192.168.0.150) puertos 80 y 443.
#
# Variables:
#   KUBE_VIP_IP — 192.168.0.150
# =============================================================================
set -euo pipefail

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
VIP="${KUBE_VIP_IP:-192.168.0.150}"
TRAEFIK_VERSION="39.0.7"   # chart = Traefik v3.6.12 — misma versión que corre en COTAS

echo ""
echo "  ┌─────────────────────────────────────────────────────────"
echo "  │  05-install-traefik v3"
echo "  │  Ingress en ${VIP}:80 y ${VIP}:443"
echo "  └─────────────────────────────────────────────────────────"

helm repo add traefik https://traefik.github.io/charts 2>/dev/null || true
helm repo update traefik

# ── Crear namespace si no existe ─────────────────────────────────────────────
kubectl create namespace traefik --dry-run=client -o yaml | kubectl apply -f -

# ── Instalar Traefik ──────────────────────────────────────────────────────────
echo "→ Instalando Traefik ${TRAEFIK_VERSION}..."

helm upgrade --install traefik traefik/traefik \
  --version "${TRAEFIK_VERSION}" \
  --namespace kube-system \
  --set service.type=LoadBalancer \
  --set "service.spec.externalIPs[0]=${VIP}" \
  --set "ports.web.exposedPort=80" \
  --set "ports.websecure.exposedPort=443" \
  --set "providers.kubernetesCRD.enabled=true" \
  --set "providers.kubernetesCRD.allowCrossNamespace=true" \
  --set "providers.kubernetesIngress.enabled=true" \
  --set "providers.kubernetesIngress.allowExternalNameServices=true" \
  --set "ingressClass.enabled=true" \
  --set "ingressClass.isDefaultClass=true" \
  --set "logs.general.level=INFO" \
  --set "logs.access.enabled=true" \
  --set "metrics.prometheus.enabled=true" \
  --set "additionalArguments[0]=--api.dashboard=false" \
  --wait --timeout=120s

echo ""
echo "→ Verificando Traefik..."
kubectl -n kube-system get svc traefik
kubectl -n kube-system get pods -l app.kubernetes.io/name=traefik

echo ""
echo "  ✅ Traefik instalado"
echo "  Ingress activo en: http://${VIP} y https://${VIP}"
