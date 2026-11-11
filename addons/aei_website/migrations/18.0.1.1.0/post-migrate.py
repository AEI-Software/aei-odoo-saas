"""Replace the placeholder plans created by aei_website 18.0.1.0.0 with the approved ones.

The plan records are loaded with noupdate, so editing the XML does not touch an
installed database. A record is only changed while it still carries its
placeholder name, so anything edited by hand since then is left alone.
"""
from odoo import SUPERUSER_ID, api

# xmlid -> (placeholder name, new values)
PLAN_UPDATES = {
    "aei_website.product_saas_plan_starter": ("Plan Inicial — Odoo 18 SaaS", {
        "name": "Starter",
        "list_price": 349.0,
        "description_sale": "Odoo 18 en la nube con facturación electrónica SIAT incluida. "
                            "Para ordenar finanzas y prestar servicios a precio fijo.",
    }),
    "aei_website.product_saas_plan_pro": ("Plan Crecimiento — Odoo 18 SaaS", {
        "name": "Pro",
        "list_price": 649.0,
        "description_sale": "Todo Starter, más inventario, proyectos, centros de costos y multimoneda. "
                            "Para comercio y trabajo por proyectos.",
    }),
    "aei_website.product_saas_plan_enterprise": ("Plan Empresarial — Odoo 18 SaaS", {
        "name": "Advanced",
        "list_price": 1290.0,
        "description_sale": "Todo Pro, más fabricación básica, costos y producción en curso. Para industria.",
    }),
}


def apply_plan_updates(env):
    for xmlid, (placeholder_name, values) in PLAN_UPDATES.items():
        product = env.ref(xmlid, raise_if_not_found=False)
        if product and product.name == placeholder_name:
            product.write(values)


def migrate(cr, version):
    apply_plan_updates(api.Environment(cr, SUPERUSER_ID, {}))

