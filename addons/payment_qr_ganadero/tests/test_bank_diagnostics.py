# -*- coding: utf-8 -*-
"""Q1 (connection check) and Q3 (visible QR failure) of docs/specs/payment-qr-ganadero-bank-testing.md."""

from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from .provider_fixtures import ACCESS_OK, FAKE_CREDENTIALS, REJECTED_QR, GanaderoProviderMixin, bank_reply, fake_bank

LOGGER = 'odoo.addons.payment_qr_ganadero'
SECRETS = (
    FAKE_CREDENTIALS['qr_ganadero_api_key'],
    FAKE_CREDENTIALS['qr_ganadero_password'],
    ACCESS_OK['token'],
)


@tagged('post_install', '-at_install')
class TestGanaderoConnectionCheck(GanaderoProviderMixin, TransactionCase):
    """The 'Test connection' button on the provider form."""

    @classmethod
    def setUpClass(cls):
        """Configure an enabled provider with fake credentials."""
        super().setUpClass()
        cls.provider = cls._configure_provider()

    def _assert_no_secret(self, text):
        """Fail when any credential or token appears in the given text."""
        for secret in SECRETS:
            self.assertNotIn(secret, text)

    def test_q1_success_always_asks_the_bank_and_caches_the_token(self):
        self.provider.write({'qr_ganadero_token_cache': 'stale-token', 'qr_ganadero_token_expires': 9999999999.0})
        with patch('requests.post', side_effect=fake_bank(access=ACCESS_OK)) as post:
            action = self.provider.action_qr_ganadero_test_connection()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(action['params']['type'], 'success')
        self.assertEqual(self.provider.qr_ganadero_token_cache, ACCESS_OK['token'])
        self._assert_no_secret(action['params']['message'])

    def test_q1_bank_rejection_shows_its_code_and_message(self):
        rejection = {'result': 'COD001', 'message': 'API Key inválida', 'token': ''}
        with patch('requests.post', side_effect=fake_bank(access=rejection)):
            action = self.provider.action_qr_ganadero_test_connection()
        message = action['params']['message']
        self.assertEqual(action['params']['type'], 'danger')
        self.assertIn('COD001', message)
        self.assertIn('API Key inválida', message)
        self._assert_no_secret(message)

    def test_q1_non_json_reply_is_reported_instead_of_crashing(self):
        reply = bank_reply({})
        reply.json.side_effect = ValueError('not json')
        with patch('requests.post', return_value=reply), self.assertLogs(LOGGER, level='WARNING'):
            action = self.provider.action_qr_ganadero_test_connection()
        self.assertEqual(action['params']['type'], 'danger')

    def test_q1_demo_mode_never_calls_the_bank(self):
        self.provider.state = 'test'
        with patch('requests.post') as post:
            action = self.provider.action_qr_ganadero_test_connection()
        post.assert_not_called()
        self.assertEqual(action['params']['type'], 'warning')


@tagged('post_install', '-at_install')
class TestGanaderoQrFailure(GanaderoProviderMixin, TransactionCase):
    """A rejected QR generation must be visible and logged without secrets."""

    def test_q3_bank_rejection_marks_the_transaction_as_error(self):
        provider = self._configure_provider()
        tx = self._create_pending_tx(provider, 'GAN-Q3-001')
        bank = fake_bank(access=ACCESS_OK, collections=REJECTED_QR)
        with patch('requests.post', side_effect=bank), self.assertLogs(LOGGER, level='WARNING') as logs:
            values = tx._get_specific_rendering_values({'reference': tx.reference, 'amount': tx.amount})
        self.assertEqual(tx.state, 'error')
        self.assertTrue(tx.state_message)
        self.assertFalse(values['qr_image'])
        joined = '\n'.join(logs.output)
        self.assertIn('COD002', joined)
        for secret in SECRETS:
            self.assertNotIn(secret, joined)


@tagged('post_install', '-at_install')
class TestGanaderoCredentialConfig(GanaderoProviderMixin, TransactionCase):
    """No hardcoded URLs/users as defaults; credentials are enforced only when enabled."""

    def test_fields_have_no_hardcoded_url_or_user_defaults(self):
        defaults = self.env['payment.provider'].default_get([
            'qr_ganadero_base_url',
            'qr_ganadero_bank_user',
        ])
        self.assertFalse(defaults.get('qr_ganadero_base_url'))
        self.assertFalse(defaults.get('qr_ganadero_bank_user'))

    def test_demo_mode_allows_empty_credentials_and_enabled_requires_them(self):
        provider = self._configure_provider(state='disabled')
        provider.write({
            'state': 'test',
            'qr_ganadero_base_url': False,
            'qr_ganadero_api_key': False,
            'qr_ganadero_username': False,
            'qr_ganadero_password': False,
            'qr_ganadero_account_ref': False,
        })
        self.assertEqual(provider.state, 'test')
        with self.assertRaises(ValidationError):
            provider.write({'state': 'enabled'})

