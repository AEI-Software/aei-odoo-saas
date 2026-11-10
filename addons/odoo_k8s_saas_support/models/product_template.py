"""
models/product_template.py

Marks a product as a support-hour package. Subscription lines carrying
such a product add (qty × support_pack_hours) to the monthly allowance.
"""
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    support_pack_hours = fields.Float(
        string="Support Pack Hours",
        default=0.0,
        help="Monthly support hours this product adds to a subscription's "
             "allowance per unit. Leave 0 for non-support products.",
    )
