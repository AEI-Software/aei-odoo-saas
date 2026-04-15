"""
routers/gc.py

Garbage-collection endpoints for orphaned Kubernetes resources.

GET  /api/v1/gc/pvs          — list Released PVs for deleted tenant namespaces
DELETE /api/v1/gc/pvs        — delete those PVs (pass ?dry_run=true to preview)
"""
from __future__ import annotations
import logging

from fastapi import APIRouter, Query

from k8s_utils.client import list_released_pvs, delete_pv

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/pvs")
def get_released_pvs():
    """List PersistentVolumes in Released phase for deleted tenant namespaces."""
    pvs = list_released_pvs()
    return {"count": len(pvs), "pvs": pvs}


@router.delete("/pvs")
def delete_released_pvs(dry_run: bool = Query(False, description="Preview without deleting")):
    """Delete orphaned PersistentVolumes left behind after tenant deletion.

    Pass ?dry_run=true to list what would be deleted without actually deleting.
    Returns the list of PVs acted on (or that would be acted on).
    """
    pvs = list_released_pvs()
    deleted = []
    errors = []

    for pv in pvs:
        if dry_run:
            deleted.append(pv["name"])
            continue
        try:
            delete_pv(pv["name"])
            logger.info("gc: deleted Released PV %s (was bound to %s/%s)",
                        pv["name"], pv["claim_namespace"], pv["claim_name"])
            deleted.append(pv["name"])
        except Exception as exc:
            logger.exception("gc: failed to delete PV %s: %s", pv["name"], exc)
            errors.append({"pv": pv["name"], "error": str(exc)})

    return {
        "dry_run": dry_run,
        "deleted": deleted,
        "errors": errors,
    }
