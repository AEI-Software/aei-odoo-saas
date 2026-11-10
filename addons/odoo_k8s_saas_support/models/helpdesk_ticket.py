"""
models/helpdesk_ticket.py

Links helpdesk tickets to SaaS subscriptions so logged support time
counts against the subscription's monthly hour allowance.
"""
from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    subscription_id = fields.Many2one(
        "sale.subscription",
        string="Subscription",
        tracking=True,
        index=True,
        help="Subscription whose support-hour allowance this ticket consumes.",
    )
    support_log_ids = fields.One2many(
        "saas.support.log",
        "ticket_id",
        string="Support Time Logs",
    )
    hours_spent = fields.Float(
        string="Hours Spent",
        compute="_compute_hours_spent",
        help="Total support hours logged on this ticket.",
    )

    @api.depends("support_log_ids.hours")
    def _compute_hours_spent(self):
        for rec in self:
            rec.hours_spent = sum(rec.support_log_ids.mapped("hours"))

    @api.model_create_multi
    def create(self, vals_list):
        """Default the subscription from the partner's active subscription."""
        tickets = super().create(vals_list)
        for ticket in tickets.filtered(lambda t: t.partner_id and not t.subscription_id):
            commercial = ticket.partner_id.commercial_partner_id
            sub = self.env["sale.subscription"].sudo().search(
                [
                    ("partner_id", "child_of", commercial.id),
                    ("in_progress", "=", True),
                ],
                limit=1,
            )
            if sub:
                ticket.subscription_id = sub.id
        return tickets
