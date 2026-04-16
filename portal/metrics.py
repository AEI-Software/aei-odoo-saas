"""
metrics.py — Prometheus metrics for the SaaS portal.

Exposes:
  - HTTP request metrics (via prometheus-fastapi-instrumentator)
  - portal_tenant_operations_total   counter  provisioning/delete/stop/start/upgrade
  - portal_tenant_errors_total       counter  errors by operation and reason
  - portal_active_tenants            gauge    tenants by state (queried from K8s live)
"""
import logging
import os

from prometheus_client import Counter, Gauge, CollectorRegistry, REGISTRY
from kubernetes import client as k8s_client, config as k8s_config

logger = logging.getLogger(__name__)

# ── Custom counters ────────────────────────────────────────────────────────────

tenant_operations = Counter(
    "portal_tenant_operations_total",
    "Tenant lifecycle operations",
    ["operation"],          # provision | delete | stop | start | upgrade
)

tenant_errors = Counter(
    "portal_tenant_errors_total",
    "Errors during tenant operations",
    ["operation", "reason"],  # reason: k8s_error | pg_error | validation | unknown
)

# ── Live tenant state gauge (populated at scrape time) ─────────────────────────

active_tenants = Gauge(
    "portal_active_tenants",
    "Number of tenant namespaces by detected state",
    ["state"],              # running | stopped | not_ready | unknown
)


def _get_k8s():
    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()
    return k8s_client.CoreV1Api(), k8s_client.AppsV1Api()


def refresh_tenant_gauges() -> None:
    """Query K8s for all odoo-* namespaces and update the active_tenants gauge."""
    try:
        core_v1, apps_v1 = _get_k8s()
        ns_list = core_v1.list_namespace(label_selector="").items
        tenant_ns = [ns.metadata.name for ns in ns_list
                     if ns.metadata.name.startswith("odoo-")
                     and ns.metadata.name not in ("odoo-admin", "odoo-stg")]

        counts = {"running": 0, "stopped": 0, "not_ready": 0, "unknown": 0}

        for ns in tenant_ns:
            try:
                deps = apps_v1.list_namespaced_deployment(namespace=ns).items
                if not deps:
                    counts["unknown"] += 1
                    continue
                dep = deps[0]
                desired = dep.spec.replicas or 0
                ready = dep.status.ready_replicas or 0
                if desired == 0:
                    counts["stopped"] += 1
                elif ready == desired:
                    counts["running"] += 1
                else:
                    counts["not_ready"] += 1
            except Exception:
                counts["unknown"] += 1

        for state, count in counts.items():
            active_tenants.labels(state=state).set(count)

    except Exception as exc:
        logger.warning("refresh_tenant_gauges failed: %s", exc)


# ── Helper functions called from router endpoints ──────────────────────────────

def record_operation(operation: str) -> None:
    tenant_operations.labels(operation=operation).inc()


def record_error(operation: str, reason: str = "unknown") -> None:
    tenant_errors.labels(operation=operation, reason=reason).inc()
