# -*- coding: utf-8 -*-
"""TDD tests for Banco Ganadero inbound endpoints (Points 6, 7, and 8)."""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGanaderoBankWebhooks(TransactionCase):
    """Verify inbound /login, /payments, COD000..COD003 codes, and idempotency."""

    @classmethod
    def setUpClass(cls):
        """Configure inbound bank credentials and a pending QR transaction."""
        super().setUpClass()
        cls.provider = cls.env.ref('payment_qr_ganadero.payment_provider_qr_ganadero')
        cls.provider.write({
            'state': 'enabled',
            'qr_ganadero_bank_user': 'BANCOGANADERO1',
            'qr_ganadero_bank_password': 'CLAVEBANCO2026',
        })
        cls.provider._qr_ganadero_ensure_jwt_secret()
        cls.payment_method = cls.env.ref('payment_qr_ganadero.payment_method_qr_ganadero')
        cls.currency_bob = (
            cls.env['res.currency'].search([('name', '=', 'BOB')], limit=1)
            or cls.env.company.currency_id
        )

    def _create_pending_tx(self, ref, qr_id, amount=349.00):
        """Create a pending payment.transaction linked to QR Ganadero."""
        return self.env['payment.transaction'].create({
            'provider_id': self.provider.id,
            'payment_method_id': self.payment_method.id,
            'reference': ref,
            'amount': amount,
            'currency_id': self.currency_bob.id,
            'partner_id': self.env.user.partner_id.id,
            'state': 'pending',
            'qr_ganadero_qr_id': qr_id,
        })

    def test_s4_inbound_login_validation_and_jwt_issue(self):
        """S4: Point 6 (/login) returns COD001 on missing fields, COD002 on invalid, COD000 on ok."""
        res_missing = self.provider._qr_ganadero_authenticate_bank({'userName': 'ONLYUSER'})
        self.assertEqual(res_missing['result'], 'COD001')

        res_special = self.provider._qr_ganadero_authenticate_bank({
            'userName': 'BAD_USER!',
            'password': 'CLAVEBANCO2026',
        })
        self.assertEqual(res_special['result'], 'COD002')

        res_wrong = self.provider._qr_ganadero_authenticate_bank({
            'userName': 'BANCOGANADERO1',
            'password': 'WRONGPASSWORD1',
        })
        self.assertEqual(res_wrong['result'], 'COD002')

        res_ok = self.provider._qr_ganadero_authenticate_bank({
            'userName': 'BANCOGANADERO1',
            'password': 'CLAVEBANCO2026',
        })
        self.assertEqual(res_ok['result'], 'COD000')
        self.assertTrue(res_ok.get('token'))
        self.assertTrue(self.provider._qr_ganadero_verify_inbound_jwt(res_ok['token']))

    def test_s5_s6_inbound_payment_confirmation_and_idempotency(self):
        """S5 & S6: Point 7 (/payments) validates JWT, payload formats, and is idempotent."""
        tx = self._create_pending_tx('GAN-WH-001', 'QRID000111222')
        login_res = self.provider._qr_ganadero_authenticate_bank({
            'userName': 'BANCOGANADERO1',
            'password': 'CLAVEBANCO2026',
        })
        jwt_token = login_res['token']

        # Missing parameter -> COD001
        missing_res, status_code = self.provider._qr_ganadero_process_bank_payment(
            f'Bearer {jwt_token}',
            {'qrId': 'QRID000111222', 'transactionId': '000012345678'},
        )
        self.assertEqual(missing_res['result'], 'COD001')

        # Bad payDate format (not ddmmyyyy) -> COD002
        bad_date_res, _ = self.provider._qr_ganadero_process_bank_payment(
            f'Bearer {jwt_token}',
            {'qrId': 'QRID000111222', 'transactionId': '000012345678', 'payDate': '2026-11-10'},
        )
        self.assertEqual(bad_date_res['result'], 'COD002')

        # Invalid Bearer token -> HTTP 401 + COD002
        bad_jwt_res, status_unauth = self.provider._qr_ganadero_process_bank_payment(
            'Bearer invalid.token.here',
            {'qrId': 'QRID000111222', 'transactionId': '000012345678', 'payDate': '10112026'},
        )
        self.assertEqual(status_unauth, 401)
        self.assertEqual(bad_jwt_res['result'], 'COD002')

        # Valid notification -> COD000 and tx state becomes done
        ok_res, status_ok = self.provider._qr_ganadero_process_bank_payment(
            f'Bearer {jwt_token}',
            {'qrId': 'QRID000111222', 'transactionId': '000012345678', 'payDate': '10112026'},
        )
        self.assertEqual(status_ok, 200)
        self.assertEqual(ok_res['result'], 'COD000')
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.qr_ganadero_transaction_id, '000012345678')
        self.assertEqual(tx.qr_ganadero_pay_date, '10112026')

        # Replay of identical notification -> idempotent COD000
        replay_res, status_replay = self.provider._qr_ganadero_process_bank_payment(
            f'Bearer {jwt_token}',
            {'qrId': 'QRID000111222', 'transactionId': '000012345678', 'payDate': '10112026'},
        )
        self.assertEqual(status_replay, 200)
        self.assertEqual(replay_res['result'], 'COD000')
        self.assertEqual(tx.state, 'done')

