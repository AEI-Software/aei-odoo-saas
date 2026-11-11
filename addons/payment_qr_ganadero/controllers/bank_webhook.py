# -*- coding: utf-8 -*-
"""Inbound endpoints exposed to Banco Ganadero (Point 6 /login and Point 7 /payments)."""

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class QrGanaderoBankWebhookController(http.Controller):
    """Implement server-to-server endpoints required by Banco Ganadero QR v1.17.4."""

    @staticmethod
    def _json_response(payload, status=200):
        """Return a raw application/json HTTP response without Odoo JSON-RPC wrapping."""
        return request.make_response(
            json.dumps(payload),
            status=status,
            headers=[('Content-Type', 'application/json')],
        )

    @staticmethod
    def _find_provider():
        """Return the active or test QR Banco Ganadero payment.provider record."""
        return request.env['payment.provider'].sudo().search(
            [('code', '=', 'qr_ganadero'), ('state', 'in', ['enabled', 'test'])],
            limit=1,
        )

    @http.route(
        '/payment/qr_ganadero/login',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def bank_login(self, **kwargs):
        """Point 6: Authenticate Banco Ganadero and return an HS256 JWT token."""
        provider = self._find_provider()
        if not provider:
            return self._json_response(
                {'result': 'COD003', 'message': 'Problemas de procesamiento, vuelva a intentar', 'token': ''},
                status=200,
            )
        try:
            body = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except ValueError:
            return self._json_response(
                {'result': 'COD002', 'message': 'Parámetros fuera del formato establecido', 'token': ''},
                status=200,
            )

        res = provider._qr_ganadero_authenticate_bank(body)
        return self._json_response(res, status=200)

    @http.route(
        '/payment/qr_ganadero/payments',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def bank_payments(self, **kwargs):
        """Point 7: Receive payment confirmation from Banco Ganadero with Bearer JWT."""
        provider = self._find_provider()
        if not provider:
            return self._json_response(
                {'result': 'COD003', 'message': 'Problemas de procesamiento, vuelva a intentar'},
                status=200,
            )
        try:
            body = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except ValueError:
            return self._json_response(
                {'result': 'COD002', 'message': 'Parámetros fuera del formato establecido'},
                status=200,
            )

        auth_header = request.httprequest.headers.get('Authorization', '')
        res, status_code = provider._qr_ganadero_process_bank_payment(auth_header, body)
        return self._json_response(res, status=status_code)

