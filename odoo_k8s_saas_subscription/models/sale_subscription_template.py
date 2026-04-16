"""
models/sale_subscription_template.py

Extends sale.subscription.template with per-user pricing fields.
Each plan defines the number of included users and the price
for each additional user.
"""
from odoo import fields, models


class SaleSubscriptionTemplate(models.Model):
    _inherit = "sale.subscription.template"

    is_saas_plan = fields.Boolean(
        string="Is SaaS Plan",
        default=False,
        help="If True, subscriptions with this template trigger automatic "
             "SaaS instance provisioning on activation.",
    )
    included_users = fields.Integer(
        string="Included Users",
        default=1,
        help="Number of users included in the base price of this plan.",
    )
    price_per_extra_user = fields.Float(
        string="Price per Extra User",
        digits="Product Price",
        default=0.0,
        help="Monthly price charged for each user beyond the included amount.",
    )
    plan = fields.Selection([
        ("starter", "Starter"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise")
    ], string="K8s Plan", default="starter",
       help="Compute resources allocated to instances on this plan.")
    storage_gi = fields.Integer(
        string="Storage (GB)",
        default=10,
        help="Persistent storage allocated for instances on this plan.")
    product_id = fields.Many2one(
        "product.product",
        string="Recurring Product",
        help="Product used on the subscription billing line for this plan. "
             "When a customer upgrades/downgrades, the billing line is replaced "
             "with this product at its list price.",
    )
    recurring_price = fields.Float(
        string="Recurring Price",
        digits="Product Price",
        default=0.0,
        help="Monthly price for this plan. Overrides the product list price on "
             "the billing line when set. Leave 0 to use the product's list price.",
    )
