# -*- coding: utf-8 -*-
"""Q6 (status polling finishes the payment) and Q7 (simulation blocked) on the public routes."""

from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from .provider_fixtures import GanaderoProviderMixin


@tagged('post_install', '-at_install')
class TestGanaderoPublicRoutes(GanaderoProviderMixin, HttpCase):
    """JSON routes called by the browser during checkout."""

    def setUp(self):
        """Configure an enabled provider with fake credentials."""
        super().setUp()
        self.provider = self._configure_provider()
        self.tx_model = type(self.env['payment.transaction'])

    def test_q6_polling_post_processes_a_confirmed_transaction(self):
        tx = self._create_pending_tx(self.provider, 'GAN-Q6-001', qr_id='QRQ6000001')
        tx._set_done()
        with patch.object(self.tx_model, '_post_process') as post_process:
            result = self.make_jsonrpc_request('/payment/qr_ganadero/status', {'reference': tx.reference})
        self.assertEqual(result['state'], 'done')
        post_process.assert_called_once()

    def test_q6_polling_does_not_post_process_twice(self):
        tx = self._create_pending_tx(self.provider, 'GAN-Q6-002', qr_id='QRQ6000002')
        tx._set_done()
        tx.is_post_processed = True
        with patch.object(self.tx_model, '_post_process') as post_process:
            self.make_jsonrpc_request('/payment/qr_ganadero/status', {'reference': tx.reference})
        post_process.assert_not_called()

    def test_q7_simulation_is_rejected_when_the_provider_is_enabled(self):
        tx = self._create_pending_tx(self.provider, 'GAN-Q7-001', qr_id='QRQ7000001')
        result = self.make_jsonrpc_request('/payment/qr_ganadero/simulate', {'reference': tx.reference})
        self.assertEqual(result['status'], 'error')
        self.assertEqual(tx.state, 'pending')
