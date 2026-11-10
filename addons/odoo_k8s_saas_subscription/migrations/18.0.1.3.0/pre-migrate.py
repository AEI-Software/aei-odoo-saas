"""
pre-migrate.py — 18.0.1.3.0

BUG FIX: Subscription templates were missing plan and storage_gi values.
All three tiers (Starter/Pro/Enterprise) defaulted to plan=starter, storage_gi=10,
causing Pro and Enterprise customers to receive Starter-class K8s resources.

This migration:
1. Clears noupdate=False on the 3 template records so the updated XML applies on upgrade.
2. Directly patches the database values for existing records.

The XML uses noupdate="1", which normally prevents updates on existing records.
Without this migration, running -u odoo_k8s_saas_subscription would silently
leave the wrong plan/storage_gi values in place.
"""
import logging

logger = logging.getLogger(__name__)

TEMPLATE_FIXES = {
    "odoo_k8s_saas_subscription.subscription_template_saas_starter": {
        "plan": "starter",
        "storage_gi": 10,
    },
    "odoo_k8s_saas_subscription.subscription_template_saas_pro": {
        "plan": "pro",
        "storage_gi": 20,
    },
    "odoo_k8s_saas_subscription.subscription_template_saas_enterprise": {
        "plan": "enterprise",
        "storage_gi": 50,
    },
}


def migrate(cr, version):
    logger.info("pre-migrate 18.0.1.3.0: fixing subscription template plan/storage_gi values")

    for xml_id, values in TEMPLATE_FIXES.items():
        module, name = xml_id.split(".")

        # Look up the record id from ir_model_data
        cr.execute(
            """
            SELECT res_id FROM ir_model_data
            WHERE module = %s AND name = %s
            """,
            (module, name),
        )
        row = cr.fetchone()
        if not row:
            logger.warning("pre-migrate: template %s not found in ir_model_data — skipping", xml_id)
            continue

        res_id = row[0]

        # Directly patch the values on the template table
        cr.execute(
            """
            UPDATE sale_subscription_template
            SET plan = %s, storage_gi = %s
            WHERE id = %s
            """,
            (values["plan"], values["storage_gi"], res_id),
        )
        logger.info(
            "pre-migrate: updated template id=%d to plan=%s, storage_gi=%d",
            res_id, values["plan"], values["storage_gi"],
        )

        # Allow the XML loader to update this record on upgrade
        cr.execute(
            """
            UPDATE ir_model_data
            SET noupdate = false
            WHERE module = %s AND name = %s
            """,
            (module, name),
        )

    logger.info("pre-migrate 18.0.1.3.0: done")
