# -*- coding: utf-8 -*-
"""Outbound QR generation, status check, and daily transactions (Points 3, 4, and 5)."""

import base64
from datetime import datetime, timedelta
import logging
import requests

from odoo import _, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

_MAX_AMOUNT_BOB = 69000.00
_BASE_SERVICE_PATH = '/ws-servicio-codigo-qr-empresas/service/v1/qrcode'

_DEMO_QR_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
  <rect width="200" height="200" fill="white" stroke="#ccc" stroke-width="1"/>
  <rect x="10" y="10" width="50" height="50" fill="none" stroke="#1a5235" stroke-width="6"/>
  <rect x="22" y="22" width="26" height="26" fill="#1a5235"/>
  <rect x="140" y="10" width="50" height="50" fill="none" stroke="#1a5235" stroke-width="6"/>
  <rect x="152" y="22" width="26" height="26" fill="#1a5235"/>
  <rect x="10" y="140" width="50" height="50" fill="none" stroke="#1a5235" stroke-width="6"/>
  <rect x="22" y="152" width="26" height="26" fill="#1a5235"/>
  <rect x="45" y="80" width="110" height="40" rx="4" fill="#1a5235"/>
  <text x="100" y="106" font-family="Arial,sans-serif" font-size="15" font-weight="bold"
        fill="white" text-anchor="middle">DEMO GANADERO</text>
</svg>"""
_DEMO_QR_B64 = base64.b64encode(_DEMO_QR_SVG.encode()).decode()


class PaymentProviderGanaderoQrRequests(models.Model):
    """Implement Points 3 (/collections), 4 (/transactions), and 5 (/status)."""

    _inherit = 'payment.provider'

    def _qr_ganadero_generate_qr(
        self, amount, currency_name, gloss, reference='', expiration_date=None, single_use=1
    ):
        """Generate a payment QR via Point 3 (/qrcode/collections) or return demo SVG in test mode."""
        self.ensure_one()
        numeric_amount = round(float(amount), 2)
        if currency_name == 'BOB' and numeric_amount > _MAX_AMOUNT_BOB:
            raise ValidationError(
                _('QR Banco Ganadero: el monto (%.2f Bs) supera el máximo permitido de 69.000,00 Bs.')
                % numeric_amount
            )
        if currency_name not in ('BOB', 'USD'):
            raise ValidationError(
                _('QR Banco Ganadero: moneda %s no soportada (solo BOB o USD).') % currency_name
            )

        if self.state == 'test':
            suffix = reference or datetime.now().strftime('%H%M%S')
            return {
                'result': 'COD000',
                'message': 'Modo Demo Banco Ganadero',
                'qrId': f'TEST-{suffix}'[:20],
                'qrImage': _DEMO_QR_B64,
            }

        token = self._qr_ganadero_get_token()
        if not expiration_date:
            expiration_date = (datetime.now() + timedelta(days=1)).strftime('%d%m%Y')

        # Point 8 requires all keys to be present in the JSON payload even if optional.
        payload = {
            'accountReference': (self.qr_ganadero_account_ref or '')[:20],
            'amount': numeric_amount,
            'currency': currency_name,
            'gloss': (gloss or '')[:60],
            'expirationDate': expiration_date,
            'singleUse': int(single_use),
            'userName': (self.qr_ganadero_username or '')[:50],
            'apiKey': self.qr_ganadero_api_key or '',
        }
        return self._qr_ganadero_post_with_jwt('/collections', token, payload)

    def _qr_ganadero_get_status(self, qr_id):
        """Query order status by qrId via Point 5 (/qrcode/status)."""
        self.ensure_one()
        if self.state == 'test':
            return {
                'result': 'COD000',
                'message': 'Modo Demo',
                'orderState': 1,
                'payday': '',
                'payHour': '',
                'transactionNumber': 0,
            }
        token = self._qr_ganadero_get_token()
        payload = {
            'qrId': (qr_id or '')[:20],
            'userName': (self.qr_ganadero_username or '')[:50],
            'apiKey': self.qr_ganadero_api_key or '',
        }
        return self._qr_ganadero_post_with_jwt('/status', token, payload, raise_on_error=False)

    def _qr_ganadero_list_daily_transactions(self, start_date, end_date):
        """Query daily orders summary via Point 4 (/qrcode/transactions)."""
        self.ensure_one()
        if self.state == 'test':
            return {'result': 'COD000', 'message': 'Modo Demo', 'orders': []}
        token = self._qr_ganadero_get_token()
        payload = {
            'userName': (self.qr_ganadero_username or '')[:50],
            'startDate': start_date,
            'endDate': end_date,
            'apiKey': self.qr_ganadero_api_key or '',
        }
        return self._qr_ganadero_post_with_jwt('/transactions', token, payload)

    def _qr_ganadero_post_with_jwt(self, sub_path, token, payload, raise_on_error=True):
        """Send an authenticated POST request to Banco Ganadero QR endpoints."""
        self.ensure_one()
        base_url = (self.qr_ganadero_base_url or '').rstrip('/')
        url = f'{base_url}{_BASE_SERVICE_PATH}{sub_path}'
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=15,
                verify=bool(self.qr_ganadero_ssl_verify),
            )
            resp.raise_for_status()
            data = resp.json() if resp.content else {}
        except requests.exceptions.RequestException as exc:
            _logger.error('QR Banco Ganadero: error HTTP en %s: %s', sub_path, type(exc).__name__)
            if raise_on_error:
                raise ValidationError(
                    _('Error de comunicación con Banco Ganadero en %s.') % sub_path
                ) from exc
            return {}

        if raise_on_error and (data.get('result') or '').strip() != 'COD000':
            raise ValidationError(
                _('QR Banco Ganadero (%s): %s')
                % (data.get('result', 'ERR'), data.get('message', 'Error en servicio QR'))
            )
        return data

