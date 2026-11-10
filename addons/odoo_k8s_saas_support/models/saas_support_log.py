"""
models/saas_support_log.py

Lightweight support-time log attached to helpdesk tickets.
Deliberately independent from hr_timesheet: no employee setup needed,
which keeps the MVP operable with a small support team.
"""
from odoo import api, fields, models


class SaasSupportLog(models.Model):
    _name = "saas.support.log"
    _description = "SaaS Support Time Log"
    _order = "date desc, id desc"

    name = fields.Char(string="Work Done", required=True)
    ticket_id = fields.Many2one(
        "helpdesk.ticket",
        string="Ticket",
        required=True,
        ondelete="cascade",
        index=True,
    )
    subscription_id = fields.Many2one(
        related="ticket_id.subscription_id",
        store=True,
        index=True,
    )
    partner_id = fields.Many2one(
        related="ticket_id.partner_id",
        store=True,
    )
    date = fields.Date(
        string="Date",
        required=True,
        default=fields.Date.context_today,
    )
    hours = fields.Float(string="Hours", required=True)
    user_id = fields.Many2one(
        "res.users",
        string="Technician",
        required=True,
        default=lambda self: self.env.user,
    )

    _sql_constraints = [
        ("hours_positive", "CHECK(hours > 0)", "Logged hours must be positive."),
    ]
