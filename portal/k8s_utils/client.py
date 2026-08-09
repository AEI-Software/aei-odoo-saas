"""
k8s_utils/client.py

Thin wrapper around the kubernetes Python SDK.
Loads in-cluster config when running inside pods,
falls back to kubeconfig file for local dev.
"""
from __future__ import annotations
import logging
import os

from kubernetes import client, config as kube_config

logger = logging.getLogger(__name__)

_config_loaded = False
_core_api: client.CoreV1Api | None = None
_apps_api: client.AppsV1Api | None = None
_net_api: client.NetworkingV1Api | None = None
_policy_api: client.PolicyV1Api | None = None


def _load_config():
    global _config_loaded
    if _config_loaded:
        return
    try:
        kube_config.load_incluster_config()
        logger.info("Using in-cluster kubeconfig")
    except Exception:
        kube_config.load_kube_config()
        logger.info("Using local kubeconfig")
    _config_loaded = True


def _core() -> client.CoreV1Api:
    global _core_api
    if _core_api is None:
        _load_config()
        _core_api = client.CoreV1Api()
    return _core_api


def _apps() -> client.AppsV1Api:
    global _apps_api
    if _apps_api is None:
        _load_config()
        _apps_api = client.AppsV1Api()
    return _apps_api


def _networking() -> client.NetworkingV1Api:
    global _net_api
    if _net_api is None:
        _load_config()
        _net_api = client.NetworkingV1Api()
    return _net_api


def _policy() -> client.PolicyV1Api:
    global _policy_api
    if _policy_api is None:
        _load_config()
        _policy_api = client.PolicyV1Api()
    return _policy_api


def apply_manifest(manifest: dict) -> None:
    """Apply a single manifest dict to the cluster."""
    kind = manifest.get("kind")
    ns = manifest.get("metadata", {}).get("namespace")

    if kind == "Namespace":
        try:
            _core().create_namespace(body=manifest)
        except client.exceptions.ApiException as e:
            if e.status == 409:
                pass  # already exists
            else:
                raise

    elif kind == "PersistentVolumeClaim":
        try:
            _core().create_namespaced_persistent_volume_claim(namespace=ns, body=manifest)
        except client.exceptions.ApiException as e:
            if e.status != 409:
                raise

    elif kind == "Secret":
        try:
            _core().create_namespaced_secret(namespace=ns, body=manifest)
        except client.exceptions.ApiException as e:
            if e.status != 409:
                raise

    elif kind == "ConfigMap":
        try:
            _core().create_namespaced_config_map(namespace=ns, body=manifest)
        except client.exceptions.ApiException as e:
            if e.status != 409:
                raise

    elif kind == "Deployment":
        try:
            _apps().create_namespaced_deployment(namespace=ns, body=manifest)
        except client.exceptions.ApiException as e:
            if e.status != 409:
                raise

    elif kind == "Service":
        try:
            _core().create_namespaced_service(namespace=ns, body=manifest)
        except client.exceptions.ApiException as e:
            if e.status != 409:
                raise

    elif kind == "Ingress":
        try:
            _networking().create_namespaced_ingress(namespace=ns, body=manifest)
        except client.exceptions.ApiException as e:
            if e.status != 409:
                raise

    elif kind == "NetworkPolicy":
        try:
            _networking().create_namespaced_network_policy(namespace=ns, body=manifest)
        except client.exceptions.ApiException as e:
            if e.status == 409:
                name = manifest.get("metadata", {}).get("name")
                _networking().replace_namespaced_network_policy(
                    name=name, namespace=ns, body=manifest
                )
            else:
                raise

    elif kind == "LimitRange":
        try:
            _core().create_namespaced_limit_range(namespace=ns, body=manifest)
        except client.exceptions.ApiException as e:
            if e.status == 409:
                name = manifest.get("metadata", {}).get("name")
                _core().replace_namespaced_limit_range(name=name, namespace=ns, body=manifest)
            else:
                raise

    elif kind == "ResourceQuota":
        try:
            _core().create_namespaced_resource_quota(namespace=ns, body=manifest)
        except client.exceptions.ApiException as e:
            if e.status == 409:
                name = manifest.get("metadata", {}).get("name")
                _core().replace_namespaced_resource_quota(name=name, namespace=ns, body=manifest)
            else:
                raise

    elif kind == "PodDisruptionBudget":
        try:
            _policy().create_namespaced_pod_disruption_budget(namespace=ns, body=manifest)
        except client.exceptions.ApiException as e:
            if e.status != 409:
                raise

    elif kind == "CiliumNetworkPolicy":
        _load_config()
        co = client.CustomObjectsApi()
        try:
            co.create_namespaced_custom_object(
                group="cilium.io", version="v2", namespace=ns,
                plural="ciliumnetworkpolicies", body=manifest,
            )
        except client.exceptions.ApiException as e:
            if e.status != 409:
                raise

    elif kind == "Cluster" and str(manifest.get("apiVersion", "")).startswith("postgresql.cnpg.io"):
        # CNPG per-tenant Postgres (PG_TOPOLOGY=cnpg). Custom resource → va por
        # CustomObjectsApi, no por los clientes tipados. 409 = ya existe (ok);
        # NO se hace replace en 409: el spec de un Cluster vivo se cambia solo
        # a propósito (upgrade de plan/imagen), nunca como side-effect de un
        # re-provisión idempotente.
        _load_config()
        co = client.CustomObjectsApi()
        try:
            co.create_namespaced_custom_object(
                group="postgresql.cnpg.io",
                version="v1",
                namespace=ns,
                plural="clusters",
                body=manifest,
            )
        except client.exceptions.ApiException as e:
            if e.status != 409:
                raise

    else:
        logger.warning("apply_manifest: unhandled kind %s", kind)


def delete_namespace(namespace: str) -> None:
    try:
        _core().delete_namespace(name=namespace)
    except client.exceptions.ApiException as e:
        if e.status != 404:
            raise


def get_deployment_status(namespace: str, name: str = "odoo") -> dict:
    """Return pod readiness info for a namespace."""
    try:
        pods = _core().list_namespaced_pod(namespace=namespace, label_selector="app=odoo")
        if not pods.items:
            return {"phase": "Pending", "ready": False}
        pod = pods.items[0]
        phase = pod.status.phase or "Unknown"
        ready = any(
            c.ready
            for c in (pod.status.container_statuses or [])
        )
        return {"phase": phase, "ready": ready}
    except client.exceptions.ApiException as e:
        if e.status == 404:
            return {"phase": "NotFound", "ready": False}
        raise


def namespace_exists(namespace: str) -> bool:
    """Return True if a K8s namespace already exists."""
    try:
        _core().read_namespace(name=namespace)
        return True
    except client.exceptions.ApiException as e:
        if e.status == 404:
            return False
        raise

def persistent_volume_claim_exists(namespace: str, name: str) -> bool:
    """PVCs need an existence check ahead of apply_manifest(), unlike
    Secret/Deployment/Service — verified live: when a namespace's
    ResourceQuota is already at its PVC cap, the API server's quota
    admission control rejects a CREATE for an object that would in fact be
    a harmless duplicate with 403 Forbidden ("exceeded quota") *before*
    reaching the uniqueness check that would otherwise return a clean 409
    (which apply_manifest already treats as already-applied). A re-enable
    of the AI agent add-on — or any tenant that already has the PVC from
    an earlier attempt — would hit this without the check.

    A PVC mid-deletion still reads back successfully (deletion isn't
    instantaneous — Longhorn needs to detach/clean up the underlying
    volume first) with `metadata.deletion_timestamp` set, so a bare
    existence check can say "exists" for an object that's about to vanish
    entirely. Verified live: a disable immediately followed by an enable
    hit exactly this — the PVC read back as present, so the create was
    skipped, and by the time the Deployment actually needed it moments
    later it was gone, leaving the agent pod stuck `Pending` with
    `persistentvolumeclaim "agent-workspace" not found`. Treat a
    terminating PVC as absent so the caller creates a fresh one instead of
    racing the old one's teardown.
    """
    try:
        pvc = _core().read_namespaced_persistent_volume_claim(name=name, namespace=namespace)
        return pvc.metadata.deletion_timestamp is None
    except client.exceptions.ApiException as e:
        if e.status == 404:
            return False
        raise


def read_namespaced_secret(namespace: str, name: str) -> dict:
    """Return a Secret's data, base64-decoded to plain strings. {} if absent."""
    import base64
    try:
        secret = _core().read_namespaced_secret(name=name, namespace=namespace)
        return {k: base64.b64decode(v).decode() for k, v in (secret.data or {}).items()}
    except client.exceptions.ApiException as e:
        if e.status == 404:
            return {}
        raise


def read_namespaced_config_map(namespace: str, name: str) -> dict:
    try:
        cm = _core().read_namespaced_config_map(name=name, namespace=namespace)
        return cm.data or {}
    except client.exceptions.ApiException as e:
        if e.status == 404:
            return {}
        raise

def patch_namespaced_config_map(namespace: str, name: str, data: dict) -> None:
    _core().patch_namespaced_config_map(name=name, namespace=namespace, body={"data": data})

def read_namespaced_pod_log(namespace: str, app_label: str = "app=odoo", tail_lines: int = 200) -> str:
    try:
        pods = _core().list_namespaced_pod(namespace=namespace, label_selector=app_label)
        if not pods.items:
            return "No pods found."
        pod_name = pods.items[0].metadata.name
        return _core().read_namespaced_pod_log(name=pod_name, namespace=namespace, tail_lines=tail_lines)
    except Exception as e:
        return f"Could not fetch logs: {e}"

def restart_deployment(namespace: str, name: str = "odoo") -> None:
    from datetime import datetime, timezone
    body = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "kubectl.kubernetes.io/restartedAt": datetime.now(timezone.utc).isoformat()
                    }
                }
            }
        }
    }
    _apps().patch_namespaced_deployment(name=name, namespace=namespace, body=body)

def scale_deployment(namespace: str, name: str, replicas: int) -> None:
    body = {"spec": {"replicas": replicas}}
    _apps().patch_namespaced_deployment_scale(name=name, namespace=namespace, body=body)


def delete_pdb(namespace: str, name: str) -> None:
    try:
        _policy().delete_namespaced_pod_disruption_budget(name=name, namespace=namespace)
    except client.exceptions.ApiException as e:
        if e.status != 404:
            raise


def patch_deployment_env(namespace: str, name: str, env: dict[str, str]) -> None:
    """Merge plain env vars into a deployment's first container, preserving
    whatever's already there. A naive JSON merge patch on `env` would
    REPLACE the whole list (K8s merge semantics don't merge list items by
    key), wiping unrelated vars like DB_PASSWORD — so this reads the
    current spec first and merges by name in Python.
    """
    apps = _apps()
    dep = apps.read_namespaced_deployment(name=name, namespace=namespace)
    container = dep.spec.template.spec.containers[0]
    existing = {e.name: e for e in (container.env or [])}
    for key, value in env.items():
        existing[key] = client.V1EnvVar(name=key, value=value)
    container.env = list(existing.values())
    apps.patch_namespaced_deployment(name=name, namespace=namespace, body=dep)


def delete_agent_resources(namespace: str) -> None:
    """Tear down the AI agent add-on's K8s objects for one tenant, leaving
    the rest of the namespace (odoo, postgres access, etc.) untouched.
    404s are expected/ignored — disable is idempotent."""
    def _ignore_404(fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
        except client.exceptions.ApiException as e:
            if e.status != 404:
                raise

    _ignore_404(_apps().delete_namespaced_deployment, name="agent", namespace=namespace)
    _ignore_404(_core().delete_namespaced_service, name="agent", namespace=namespace)
    _ignore_404(_core().delete_namespaced_secret, name="agent-secret", namespace=namespace)
    _ignore_404(_core().delete_namespaced_persistent_volume_claim, name="agent-workspace", namespace=namespace)
    _ignore_404(_networking().delete_namespaced_network_policy, name="agent-isolation", namespace=namespace)


_EXCLUDED_NAMESPACES = {"odoo-admin", "odoo-stg"}


def list_tenant_namespaces() -> list[str]:
    """Return all odoo-* namespace names that belong to real tenants."""
    ns_list = _core().list_namespace()
    return [
        ns.metadata.name
        for ns in ns_list.items
        if ns.metadata.name.startswith("odoo-")
        and ns.metadata.name not in _EXCLUDED_NAMESPACES
    ]


def list_released_pvs() -> list[dict]:
    """Return PVs in 'Released' phase whose claimRef points to an odoo-* namespace.

    These are orphaned volumes left behind after a tenant namespace is deleted.
    Safe to delete: the namespace (and its PVC) no longer exists.
    """
    pvs = _core().list_persistent_volume()
    result = []
    for pv in pvs.items:
        if pv.status.phase != "Released":
            continue
        claim_ref = pv.spec.claim_ref
        if claim_ref is None:
            continue
        ns = claim_ref.namespace or ""
        if not ns.startswith("odoo-"):
            continue
        # Double-check the namespace is truly gone
        try:
            _core().read_namespace(name=ns)
            # Namespace still exists — skip (PVC deleted inside a live namespace)
            continue
        except client.exceptions.ApiException as e:
            if e.status != 404:
                raise
        result.append({
            "name": pv.metadata.name,
            "claim_namespace": ns,
            "claim_name": claim_ref.name or "",
            "capacity": pv.spec.capacity or {},
            "storage_class": pv.spec.storage_class_name or "",
            "reclaim_policy": pv.spec.persistent_volume_reclaim_policy or "",
        })
    return result


def delete_pv(name: str) -> None:
    """Delete a PersistentVolume by name."""
    try:
        _core().delete_persistent_volume(name=name)
    except client.exceptions.ApiException as e:
        if e.status != 404:
            raise
