# -*- coding: utf-8 -*-
"""Shared test fixtures: a configured provider and a fake Banco Ganadero HTTP API.

All credentials below are fake values used only by the test suite.
"""

from unittest.mock import MagicMock

FAKE_CREDENTIALS = {
    'qr_ganadero_base_url': 'https://bank.example.test/qa',
    'qr_ganadero_api_key': 'FAKEAPIKEY0001',
    'qr_ganadero_api_key_header': 'XApi--Key',
    'qr_ganadero_username': 'FAKECOBRADOR1',
    'qr_ganadero_password': 'FAKEPASSWORD1',
    'qr_ganadero_account_ref': 'FAKE_REF',
    'qr_ganadero_bank_user': 'FAKEBANKUSER1',
    'qr_ganadero_bank_password': 'FAKEBANKPASS1',
}
ACCESS_OK = {'result': 'COD000', 'message': 'Resultado satisfactorio', 'token': 'fake-bank-jwt-0001'}
REJECTED_QR = {'result': 'COD002', 'message': 'Parámetros fuera del formato establecido'}


def bank_reply(payload):
    """Build a fake requests.Response that returns the given JSON payload."""
    response = MagicMock()
    response.status_code = 200
    response.content = b'{}'
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def fake_bank(**replies):
    """Return a requests.post side effect keyed by the endpoint name (access, collections...)."""
    def _post(url, **_kwargs):
        endpoint = url.rstrip('/').rsplit('/', 1)[-1]
        return bank_reply(replies[endpoint])
    return _post


class GanaderoProviderMixin:
    """Helpers to configure the QR Ganadero provider and create transactions in tests."""

    @classmethod
    def _configure_provider(cls, state='enabled'):
        """Return the module provider in the given state with fake credentials and no cached token."""
        provider = cls.env.ref('payment_qr_ganadero.payment_provider_qr_ganadero')
        provider.write(dict(
            FAKE_CREDENTIALS,
            state=state,
            qr_ganadero_token_cache=False,
            qr_ganadero_token_expires=0.0,
        ))
        provider._qr_ganadero_ensure_jwt_secret()
        return provider

    @classmethod
    def _bank_currency(cls):
        """Return BOB when it exists, else the company currency."""
        return (
            cls.env['res.currency'].with_context(active_test=False).search([('name', '=', 'BOB')], limit=1)
            or cls.env.company.currency_id
        )

    def _create_pending_tx(self, provider, reference, qr_id=False, amount=349.00):
        """Create a pending QR Ganadero transaction for the current user."""
        return self.env['payment.transaction'].create({
            'provider_id': provider.id,
            'payment_method_id': self.env.ref('payment_qr_ganadero.payment_method_qr_ganadero').id,
            'reference': reference,
            'amount': amount,
            'currency_id': self._bank_currency().id,
            'partner_id': self.env.user.partner_id.id,
            'state': 'pending',
            'qr_ganadero_qr_id': qr_id,
        })

    def _bank_jwt(self, provider):
        """Log in as the bank (Point 6) and return the issued JWT."""
        return provider._qr_ganadero_authenticate_bank({
            'userName': FAKE_CREDENTIALS['qr_ganadero_bank_user'],
            'password': FAKE_CREDENTIALS['qr_ganadero_bank_password'],
        })['token']
