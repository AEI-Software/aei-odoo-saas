"""Recipient of the /contactus inquiries: configurable, defaulting to the commercial mailbox."""
from odoo.tests import TransactionCase, tagged

PARAM = "aei_website.contact_recipient"
DEFAULT_RECIPIENT = "ebendek@ribentek.com"
PAYLOAD = {
    "name": "Gerencia Demo",
    "email_from": "gerencia@empresa.bo",
    "subject": "Consulta Plan Pro",
    "description": "Quisiera una demostración para 10 usuarios.",
}


@tagged("post_install", "-at_install")
class TestContactRecipient(TransactionCase):
    """Where the queued inquiry mail is addressed and how that address is configured."""

    def setUp(self):
        super().setUp()
        self.website = self.env["website"].search([], limit=1)
        self.params = self.env["ir.config_parameter"].sudo()

    def _submit_and_get_recipient(self):
        """Submit a valid inquiry and return the email_to of the single mail it queued."""
        mails = self.env["mail.mail"].sudo()
        before = mails.search([]).ids
        ok, _cleaned = self.website.submit_aei_contact_form(dict(PAYLOAD))
        self.assertTrue(ok)
        created = mails.search([("id", "not in", before)])
        self.assertEqual(len(created), 1)
        return created.email_to

    def test_installed_default_points_to_the_commercial_mailbox(self):
        self.assertEqual(self.params.get_param(PARAM), DEFAULT_RECIPIENT)

    def test_inquiry_goes_to_the_configured_recipient(self):
        self.params.set_param(PARAM, "ventas@empresa.bo")
        self.assertEqual(self._submit_and_get_recipient(), "ventas@empresa.bo")

    def test_company_email_does_not_receive_the_inquiries(self):
        self.website.company_id.email = "info@aeisoftware.com"
        self.params.set_param(PARAM, DEFAULT_RECIPIENT)
        self.assertEqual(self._submit_and_get_recipient(), DEFAULT_RECIPIENT)

    def test_several_recipients_are_accepted(self):
        self.params.set_param(PARAM, "a@empresa.bo,  b@empresa.bo")
        self.assertEqual(self._submit_and_get_recipient(), "a@empresa.bo, b@empresa.bo")

    def test_invalid_value_falls_back_to_the_default(self):
        for bad in ("no-es-correo", "a@empresa.bo, malo"):
            self.params.set_param(PARAM, bad)
            self.assertEqual(self._submit_and_get_recipient(), DEFAULT_RECIPIENT, bad)

    def test_empty_value_falls_back_to_the_default(self):
        self.params.set_param(PARAM, "")
        self.assertEqual(self._submit_and_get_recipient(), DEFAULT_RECIPIENT)

    def test_settings_field_saves_the_parameter(self):
        settings = self.env["res.config.settings"].create({"aei_contact_recipient": "x@empresa.bo"})
        settings.execute()
        self.assertEqual(self.params.get_param(PARAM), "x@empresa.bo")

    def test_settings_form_shows_the_field(self):
        arch = self.env["res.config.settings"].get_view(view_type="form")["arch"]
        self.assertIn("aei_contact_recipient", arch)
