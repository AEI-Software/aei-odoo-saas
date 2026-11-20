# -*- coding: utf-8 -*-
"""Q2, Q4 and Q8: standalone test QR for the joint test with the bank."""

import base64
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from .provider_fixtures import ACCESS_OK, REJECTED_QR, GanaderoProviderMixin, fake_bank

PNG_BYTES = b'\x89PNG\r\n\x1a\n' + b'\x00' * 16
QR_OK = {
    'result': 'COD000',
    'message': 'Resultado satisfactorio',
    'qrId': 'QRTEST0000000001',
    'qrImage': base64.b64encode(PNG_BYTES).decode(),
}
WIZARD = 'payment.qr.ganadero.test.qr'


@tagged('post_install', '-at_install')
class TestGanaderoTestQr(GanaderoProviderMixin, TransactionCase):
    """'Generate test QR' wizard on the provider."""

    @classmethod
    def setUpClass(cls):
        """Configure an enabled provider with fake credentials."""
        super().setUpClass()
        cls.provider = cls._configure_provider()

    def _wizard(self, **values):
        """Create the wizard for the provider with a small amount and a gloss."""
        return self.env[WIZARD].create(dict(
            {'provider_id': self.provider.id, 'amount': 1.0, 'gloss': 'PRUEBA-AEI'}, **values
        ))

    def _generate(self, wizard, collections=QR_OK):
        """Run the wizard against the fake bank; return the mocked requests.post."""
        with patch('requests.post', side_effect=fake_bank(access=ACCESS_OK, collections=collections)) as post:
            wizard.action_generate()
        return post

    def test_q2_creates_a_standalone_transaction_with_the_bank_qr(self):
        wizard = self._wizard()
        post = self._generate(wizard)
        tx = wizard.transaction_id
        self.assertEqual(tx.qr_ganadero_qr_id, QR_OK['qrId'])
        self.assertEqual(tx.amount, 1.0)
        self.assertEqual(tx.state, 'pending')
        self.assertFalse(tx.sale_order_ids)
        body = post.call_args.kwargs['json']
        self.assertEqual(body['accountReference'], self.provider.qr_ganadero_account_ref)
        self.assertEqual(body['gloss'], 'PRUEBA-AEI')
        self.assertEqual(body['amount'], 1.0)
        self.assertEqual(base64.b64decode(wizard.qr_file), PNG_BYTES)
        self.assertTrue(wizard.qr_filename.endswith('.png'))

    def test_q2_demo_mode_does_not_call_the_bank_and_names_the_file_svg(self):
        self.provider.state = 'test'
        wizard = self._wizard()
        with patch('requests.post') as post:
            wizard.action_generate()
        post.assert_not_called()
        self.assertTrue(wizard.qr_filename.endswith('.svg'))

    def test_q2_amount_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._wizard(amount=0.0)

    def test_q2_bank_rejection_creates_no_transaction(self):
        transactions = self.env['payment.transaction']
        before = transactions.search_count([('provider_id', '=', self.provider.id)])
        with self.assertRaises(ValidationError):
            self._generate(self._wizard(), collections=REJECTED_QR)
        self.assertEqual(transactions.search_count([('provider_id', '=', self.provider.id)]), before)

    def test_q4_bank_notification_confirms_the_test_payment_once(self):
        wizard = self._wizard()
        self._generate(wizard)
        tx = wizard.transaction_id
        bearer = f'Bearer {self._bank_jwt(self.provider)}'
        payload = {'qrId': tx.qr_ganadero_qr_id, 'transactionId': '000012345678', 'payDate': '20112026'}
        result, status = self.provider._qr_ganadero_process_bank_payment(bearer, payload)
        self.assertEqual((result['result'], status), ('COD000', 200))
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.qr_ganadero_transaction_id, '000012345678')
        replay, _status = self.provider._qr_ganadero_process_bank_payment(bearer, payload)
        self.assertEqual(replay['result'], 'COD000')
        self.assertFalse(tx.sale_order_ids)

    def test_q8_notification_for_an_unknown_qr_is_rejected(self):
        bearer = f'Bearer {self._bank_jwt(self.provider)}'
        payload = {'qrId': 'QRDESCONOCIDO01', 'transactionId': '000012345679', 'payDate': '20112026'}
        result, _status = self.provider._qr_ganadero_process_bank_payment(bearer, payload)
        self.assertEqual(result['result'], 'COD002')
