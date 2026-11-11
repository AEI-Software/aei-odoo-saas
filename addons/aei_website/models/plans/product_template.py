"""Plan lookup for the public landing page.

The page never keeps its own copy of prices or capacities: it asks this model, which
reads them from the product, its subscription template and the module catalog.
"""
from odoo import api, models

from .plan_pricing import annual_amounts, format_money, format_number

SAAS_CATEGORY_XMLID = "odoo_k8s_saas.product_category_odoo_saas"


class ProductTemplate(models.Model):
    """Adds the public plan lookup to product templates."""

    _inherit = "product.template"

    @api.model
    def website_saas_plans(self):
        """Return the published SaaS plans as plain, public-safe dictionaries.

        Prices come from the product and capacities from its subscription
        template, so the landing page never keeps its own copy of them. The
        lookup runs with sudo because a visitor cannot read subscription
        templates; only the fields below leave this method.
        """
        category = self.env.ref(SAAS_CATEGORY_XMLID, raise_if_not_found=False)
        if not category:
            return []
        products = self.sudo().search(
            [
                ("categ_id", "=", category.id),
                ("subscribable", "=", True),
                ("sale_ok", "=", True),
                ("website_published", "=", True),
                ("subscription_template_id", "!=", False),
            ],
            order="list_price, id",
        )
        return [self._website_saas_plan_values(product) for product in products]

    @api.model
    def _website_saas_plan_values(self, product):
        """Build the public dictionary of one plan product.

        Only data that is safe to show a visitor is returned: name, amounts for
        both billing periods, capacities, the report count and the variant id the
        cart form posts.
        """
        template = product.subscription_template_id
        catalog = self.env["aei.website.catalog"]
        annual = annual_amounts(product.list_price)
        values = {
            "key": template.plan,
            "name": product.name,
            "price": product.list_price,
            "price_label": self._format_plan_price(product.list_price),
            "users": template.included_users,
            "storage_gi": template.storage_gi,
            "support_hours": int(template.support_hours_included),
            "report_count": catalog.report_count(catalog.plan_level(template.plan)),
            "variant_id": product.product_variant_id.id,
        }
        values.update(
            annual_price_label=format_number(annual["monthly_equivalent"]),
            annual_detail="%s facturados al año" % format_money(annual["total"]),
            annual_saving="Ahorras %s al año" % format_money(annual["saving"]),
        )
        return values

    @api.model
    def _format_plan_price(self, amount):
        """Format a price the Bolivian way: dot as thousands separator, no decimals."""
        return "{:,.0f}".format(amount).replace(",", ".")
