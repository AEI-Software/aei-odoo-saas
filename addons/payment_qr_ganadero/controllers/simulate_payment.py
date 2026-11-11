# -*- coding: utf-8 -*-
"""Demo mode payment simulation controller for Banco Ganadero QR."""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class QrGanaderoSimulateController(http.Controller):
    """Allow simulating QR payment completion strictly when provider.state == 'test'."""

    @http.route(
        '/payment/qr_ganadero/simulate',
        type='json',
        auth='public',
        methods=['POST'],
    )
    def simulate_payment(self, reference=None, **kwargs):
        """Mark a pending QR Ganadero transaction as done when provider is in test mode."""
        if not reference:
            return {'status': 'error', 'message': 'missing reference'}

        tx = request.env['payment.transaction'].sudo().search(
            [('reference', '=', reference), ('provider_code', '=', 'qr_ganadero')],
            limit=1,
        )
        if not tx:
            return {'status': 'error', 'message': 'transaction not found'}

        if tx.provider_id.state != 'test':
            _logger.warning(
                'QR Banco Ganadero: intento de simulación con proveedor fuera de modo test (ref=%s)',
                reference,
            )
            return {'status': 'error', 'message': 'test mode not enabled'}

        if tx.state in ('done', 'cancel', 'error'):
            return {
                'status': 'already_done',
                'state': tx.state,
                'landing_route': tx.landing_route or '/payment/status',
            }

        try:
            tx._set_done()
            tx._post_process()
        except Exception:
            _logger.exception('QR Banco Ganadero [DEMO]: fallo al simular pago ref=%s', reference)
            return {'status': 'error', 'message': 'simulation failed'}

        tx.invalidate_recordset()
        return {
            'status': 'ok',
            'state': tx.state,
            'landing_route': tx.landing_route or '/payment/status',
        }

