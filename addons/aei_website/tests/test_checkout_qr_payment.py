"""Step 3 of /checkout with the Banco Ganadero QR: visible failure and automatic status polling."""
from unittest.mock import MagicMock, patch

from lxml import html

from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

STEP3 = "/checkout?plan=starter&cycle=monthly&mode=paid&step=3"
FAKE_PROVIDER_VALUES = {
    "qr_ganadero_base_url": "https://bank.example.test/qa",
    "qr_ganadero_api_key": "FAKEAPIKEY0001",
    "qr_ganadero_username": "FAKECOBRADOR1",
    "qr_ganadero_password": "FAKEPASSWORD1",
    "qr_ganadero_account_ref": "FAKE_REF",
    "qr_ganadero_token_cache": False,
    "qr_ganadero_token_expires": 0.0,
}
BANK_REPLIES = {
    "access": {"result": "COD000", "message": "Resultado satisfactorio", "token": "fake-bank-jwt"},
    "collections": {"result": "COD002", "message": "Parámetros fuera del formato establecido"},
}


def _fake_bank_post(url, **_kwargs):
    """Answer like the bank: token on /access, rejection on /collections."""
    response = MagicMock()
    response.content = b"{}"
    response.json.return_value = BANK_REPLIES[url.rstrip("/").rsplit("/", 1)[-1]]
    return response


@tagged("post_install", "-at_install")
class TestCheckoutQrPayment(HttpCase):
    """What the customer sees on Step 3 when paying with the bank QR."""

    def setUp(self):
        super().setUp()
        self.provider = self.env["payment.provider"].sudo().search([("code", "=", "qr_ganadero")], limit=1)
        if not self.provider:
            self.skipTest("payment_qr_ganadero is not installed")
        self.authenticate("admin", "admin")

    def _step3(self):
        response = self.url_open(STEP3)
        self.assertEqual(response.status_code, 200)
        return html.fromstring(response.content)

    def test_step3_offers_a_retry_when_the_bank_rejects_the_qr(self):
        self.provider.write(dict(FAKE_PROVIDER_VALUES, state="enabled"))
        with patch("requests.post", side_effect=_fake_bank_post), mute_logger("odoo.addons.payment_qr_ganadero"):
            tree = self._step3()
        text = " ".join(tree.text_content().split())
        self.assertIn("No pudimos generar el QR", text)
        self.assertFalse(tree.xpath('//img[@alt="Código QR Banco Ganadero"]'))
        self.assertTrue(tree.xpath("//a[@data-aei-qr-retry]"))
        self.assertFalse(tree.xpath("//*[@data-aei-qr-poll]"))

    def test_step3_polls_the_payment_and_knows_where_to_go_when_paid(self):
        self.provider.write({"state": "test"})
        polls = self._step3().xpath("//*[@data-aei-qr-poll]")
        self.assertEqual(len(polls), 1)
        poll = polls[0]
        self.assertTrue(poll.get("data-aei-reference"))
        self.assertEqual(poll.get("data-aei-status-url"), "/payment/qr_ganadero/status")
        self.assertTrue(poll.get("data-aei-done-url").startswith("/checkout?"))
        self.assertIn("step=done", poll.get("data-aei-done-url"))
        self.assertGreater(int(poll.get("data-aei-poll-interval")), 0)
