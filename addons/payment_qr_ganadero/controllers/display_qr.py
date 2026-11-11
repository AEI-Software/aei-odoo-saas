# -*- coding: utf-8 -*-
"""Public QR display controller for Banco Ganadero checkout redirect."""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class QrGanaderoDisplayController(http.Controller):
    """Render the QR payment screen after the customer submits checkout."""

    @http.route(
        '/payment/qr_ganadero/display',
        type='http',
        auth='public',
        website=True,
        methods=['GET'],
        sitemap=False,
    )
    def display_qr(self, reference=None, **kwargs):
        """Show the generated QR code page and start frontend status polling."""
        if not reference:
            return request.redirect('/payment/status')

        tx = request.env['payment.transaction'].sudo().search(
            [('reference', '=', reference), ('provider_code', '=', 'qr_ganadero')],
            limit=1,
        )
        if not tx:
            _logger.warning('QR Banco Ganadero: transacción no encontrada ref=%s', reference)
            return request.redirect('/payment/status')

        base_url = request.httprequest.host_url.rstrip('/')
        is_demo = tx.provider_id.state == 'test'

        return request.render('payment_qr_ganadero.qr_ganadero_display', {
            'reference': reference,
            'qr_image': tx.qr_ganadero_image or '',
            'qr_id': tx.qr_ganadero_qr_id or '',
            'amount': tx.amount,
            'currency': tx.currency_id.name if tx.currency_id else 'BOB',
            'landing_route': tx.landing_route or '/payment/status',
            'is_demo': is_demo,
            'simulate_url': f'{base_url}/payment/qr_ganadero/simulate',
        })

