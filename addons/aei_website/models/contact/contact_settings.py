"""Settings field that edits the recipient of the /contactus inquiries."""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Exposes the contact recipient in Settings > Website (stored as a system parameter)."""

    _inherit = "res.config.settings"

    aei_contact_recipient = fields.Char(
        string="Contact form recipient",
        config_parameter="aei_website.contact_recipient",
        help="Address that receives the inquiries sent from /contactus. "
        "Separate several addresses with commas.",
    )
