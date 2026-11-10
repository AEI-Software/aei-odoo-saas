"""
models/sale_subscription.py

Monthly support-hour balance per subscription:
  allowance = template.support_hours_included (per instance, from plan)
            + Σ (support-pack line qty × product.support_pack_hours)
  consumed  = Σ saas.support.log hours in the current calendar month
Hours expire monthly (no rollover) per the AEI support policy.
"""
from odoo import api, fields, models


class SaleSubscription(models.Model):
    _inherit = "sale.subscription"

    support_pack_hours = fields.Float(
        string="Support Pack Hours",
        compute="_compute_support_hours",
        help="Extra monthly hours from support-package lines on this subscription.",
    )
    support_hours_total = fields.Float(
        string="Support Hours (Total)",
        compute="_compute_support_hours",
        help="Plan allowance + support packages, per month.",
    )
    support_hours_consumed = fields.Float(
        string="Support Hours Consumed",
        compute="_compute_support_hours",
        help="Hours logged on this subscription's tickets during the current month.",
    )
    support_hours_available = fields.Float(
        string="Support Hours Available",
        compute="_compute_support_hours",
        help="Remaining hours this month. Negative means overage.",
    )
    ticket_count = fields.Integer(
        string="Tickets",
        compute="_compute_ticket_count",
    )

    @api.depends(
        "template_id.support_hours_included",
        "sale_subscription_line_ids.product_id",
        "sale_subscription_line_ids.product_uom_qty",
    )
    def _compute_support_hours(self):
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        Log = self.env["saas.support.log"].sudo()
        for rec in self:
            packs = sum(
                line.product_id.support_pack_hours * line.product_uom_qty
                for line in rec.sale_subscription_line_ids
                if line.product_id and line.product_id.support_pack_hours
            )
            included = rec.template_id.support_hours_included if rec.template_id else 0.0
            consumed = sum(
                Log.search([
                    ("subscription_id", "=", rec.id),
                    ("date", ">=", month_start),
                    ("date", "<=", today),
                ]).mapped("hours")
            ) if rec.id else 0.0

            rec.support_pack_hours = packs
            rec.support_hours_total = included + packs
            rec.support_hours_consumed = consumed
            rec.support_hours_available = included + packs - consumed

    def _compute_ticket_count(self):
        for rec in self:
            rec.ticket_count = (
                self.env["helpdesk.ticket"].sudo().search_count(
                    [("subscription_id", "=", rec.id)]
                ) if rec.id else 0
            )

    def action_view_support_tickets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Support Tickets",
            "res_model": "helpdesk.ticket",
            "view_mode": "list,form",
            "domain": [("subscription_id", "=", self.id)],
            "context": {
                "default_subscription_id": self.id,
                "default_partner_id": self.partner_id.id,
            },
        }
