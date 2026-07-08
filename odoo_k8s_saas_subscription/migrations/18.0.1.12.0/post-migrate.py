"""Set support_hours_included on the stock SaaS plan templates.

The templates data file is noupdate="1", so existing databases never
receive the new values from XML. Only fills records still at 0 so any
manually configured value is preserved.
"""
import logging

logger = logging.getLogger(__name__)

_HOURS_BY_XMLID = {
    "odoo_k8s_saas_subscription.subscription_template_saas_starter": 2.0,
    "odoo_k8s_saas_subscription.subscription_template_saas_pro": 5.0,
    "odoo_k8s_saas_subscription.subscription_template_saas_enterprise": 10.0,
}


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, hours in _HOURS_BY_XMLID.items():
        template = env.ref(xmlid, raise_if_not_found=False)
        if template and not template.support_hours_included:
            template.support_hours_included = hours
            logger.info(
                "post-migrate 18.0.1.12.0: %s → support_hours_included=%.1f",
                xmlid, hours,
            )
