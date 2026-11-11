# -*- coding: utf-8 -*-
"""TDD tests for Banco Ganadero outbound API (Points 2, 3, 4, and 5)."""

from unittest.mock import MagicMock, patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGanaderoOutboundApi(TransactionCase):
    """Verify outbound authentication, QR generation, status polling, and daily list."""

    @classmethod
    def setUpClass(cls):
        """Set up a configured Banco Ganadero payment provider for unit tests."""
        super().setUpClass()
        cls.provider = cls.env.ref('payment_qr_ganadero.payment_provider_qr_ganadero')
        cls.provider.write({
            'state': 'enabled',
            'qr_ganadero_base_url': 'https://sandbox.bg.com.bo',
            'qr_ganadero_api_key': 'APIKEY123456',
            'qr_ganadero_api_key_header': 'XApi--Key',
            'qr_ganadero_username': 'AEICOBRADOR1',
            'qr_ganadero_password': 'PASS123456',
            'qr_ganadero_account_ref': 'CUENTAAEI01',
            'qr_ganadero_token_cache': False,
            'qr_ganadero_token_expires': 0.0,
        })
        cls.currency_bob = (
            cls.env['res.currency'].search([('name', '=', 'BOB')], limit=1)
            or cls.env.company.currency_id
        )

    def test_s1_outbound_token_fetch_and_cache_reuse(self):
        """S1: Point 2 (/qrcode/access) fetches JWT once and reuses DB cache."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'result': 'COD000',
            'message': 'Resultado satisfactorio',
            'token': 'jwt-banco-ganadero-123',
        }
        with patch('requests.post', return_value=mock_resp) as mocked_post:
            token1 = self.provider._qr_ganadero_get_token()
            token2 = self.provider._qr_ganadero_get_token()
            self.assertEqual(token1, 'jwt-banco-ganadero-123')
            self.assertEqual(token2, 'jwt-banco-ganadero-123')
            self.assertEqual(mocked_post.call_count, 1)
            called_headers = mocked_post.call_args.kwargs['headers']
            self.assertEqual(called_headers.get('XApi--Key'), 'APIKEY123456')

    def test_s2_generate_qr_collections_and_max_amount_guard(self):
        """S2: Point 3 (/qrcode/collections) sends required keys and enforces 69,000 Bs cap."""
        self.provider.write({
            'qr_ganadero_token_cache': 'cached-jwt-token',
            'qr_ganadero_token_expires': 9999999999.0,
        })
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'result': 'COD000',
            'message': 'Resultado satisfactorio',
            'qrId': 'QR9876543210',
            'qrImage': 'iVBORw0KGgoAAAANSUhEUgAAAAUA',
        }
        with patch('requests.post', return_value=mock_resp) as mocked_post:
            res = self.provider._qr_ganadero_generate_qr(
                amount=349.00,
                currency_name='BOB',
                gloss='Pedido S0001',
            )
            self.assertEqual(res['qrId'], 'QR9876543210')
            body = mocked_post.call_args.kwargs['json']
            for required_key in (
                'accountReference', 'amount', 'currency', 'gloss',
                'expirationDate', 'singleUse', 'userName', 'apiKey',
            ):
                self.assertIn(required_key, body)
            self.assertEqual(len(body['expirationDate']), 8)
            self.assertEqual(body['singleUse'], 1)

        with self.assertRaises(ValidationError):
            self.provider._qr_ganadero_generate_qr(
                amount=70000.00,
                currency_name='BOB',
                gloss='Excede tope',
            )

    def test_s3_demo_mode_generates_svg_without_http(self):
        """S3: In test mode, QR generation returns demo SVG without calling the bank."""
        self.provider.write({'state': 'test'})
        with patch('requests.post') as mocked_post:
            data = self.provider._qr_ganadero_generate_qr(
                amount=349.00,
                currency_name='BOB',
                gloss='Demo S0002',
                reference='S0002',
            )
            mocked_post.assert_not_called()
            self.assertEqual(data['qrId'], 'TEST-S0002')
            self.assertTrue(data['qrImage'])

    def test_s7_status_poll_and_fallback_cron_confirms_tx(self):
        """S7: Point 5 (/qrcode/status) with orderState=2 marks pending transaction done."""
        self.provider.write({
            'state': 'enabled',
            'qr_ganadero_token_cache': 'cached-jwt-token',
            'qr_ganadero_token_expires': 9999999999.0,
        })
        payment_method = self.env.ref('payment_qr_ganadero.payment_method_qr_ganadero')
        partner = self.env.user.partner_id
        tx = self.env['payment.transaction'].create({
            'provider_id': self.provider.id,
            'payment_method_id': payment_method.id,
            'reference': 'GAN-CRON-001',
            'amount': 349.00,
            'currency_id': self.currency_bob.id,
            'partner_id': partner.id,
            'state': 'pending',
            'qr_ganadero_qr_id': 'QR-CRON-001',
        })
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'result': 'COD000',
            'message': 'Resultado satisfactorio',
            'orderState': 2,
            'payday': '10112026',
            'payHour': '16:30',
            'transactionNumber': 1234567890,
        }
        with patch('requests.post', return_value=mock_resp):
            self.env['payment.transaction']._cron_qr_ganadero_poll_pending()
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.qr_ganadero_transaction_id, '1234567890')

