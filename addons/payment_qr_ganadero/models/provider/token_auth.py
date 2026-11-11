# -*- coding: utf-8 -*-
"""Outbound JWT authentication and database token cache (Point 2: /qrcode/access)."""

import logging
import threading
import time
import requests

from odoo import _, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

_TOKEN_LOCK = threading.Lock()
_TOKEN_REFRESH_MARGIN_S = 300
_TOKEN_TTL_S = 55 * 60
_ACCESS_PATH = '/ws-servicio-codigo-qr-empresas/service/v1/qrcode/access'


class PaymentProviderGanaderoTokenAuth(models.Model):
    """Implement Point 2 (/qrcode/access) with thread-safe PostgreSQL token caching."""

    _inherit = 'payment.provider'

    def _qr_ganadero_get_token(self):
        """Return a valid outbound JWT from DB cache or fetch a fresh one from Banco Ganadero."""
        self.ensure_one()
        if self.state == 'test':
            raise ValidationError(
                _('QR Banco Ganadero [TEST]: _qr_ganadero_get_token() no debe invocarse en modo test.')
            )
        now = time.time()
        cached_token, cached_expires = self._qr_ganadero_read_cached_token()
        if cached_token and cached_expires and now < (cached_expires - _TOKEN_REFRESH_MARGIN_S):
            return cached_token

        with _TOKEN_LOCK:
            cached_token, cached_expires = self._qr_ganadero_read_cached_token()
            now = time.time()
            if cached_token and cached_expires and now < (cached_expires - _TOKEN_REFRESH_MARGIN_S):
                return cached_token

            token = self._qr_ganadero_fetch_token()
            expires_at = now + _TOKEN_TTL_S
            self.env.cr.execute(
                'UPDATE payment_provider '
                'SET qr_ganadero_token_cache = %s, qr_ganadero_token_expires = %s '
                'WHERE id = %s',
                (token, expires_at, self.id),
            )
            self.invalidate_recordset(['qr_ganadero_token_cache', 'qr_ganadero_token_expires'])
            return token

    def _qr_ganadero_read_cached_token(self):
        """Read cached token and expiry directly from PostgreSQL after flushing ORM writes."""
        self.ensure_one()
        self.flush_recordset(['qr_ganadero_token_cache', 'qr_ganadero_token_expires'])
        self.env.cr.execute(
            'SELECT qr_ganadero_token_cache, qr_ganadero_token_expires '
            'FROM payment_provider WHERE id = %s',
            (self.id,),
        )
        row = self.env.cr.fetchone()
        if not row:
            return None, 0.0
        return row[0], row[1] or 0.0

    def _qr_ganadero_fetch_token(self):
        """Execute POST /qrcode/access (Point 2) against Banco Ganadero and validate COD000."""
        self.ensure_one()
        base_url = (self.qr_ganadero_base_url or '').rstrip('/')
        url = f'{base_url}{_ACCESS_PATH}'
        header_name = (self.qr_ganadero_api_key_header or 'XApi--Key').strip()
        headers = {
            header_name: self.qr_ganadero_api_key or '',
            'Content-Type': 'application/json',
        }
        payload = {
            'userName': self.qr_ganadero_username or '',
            'password': self.qr_ganadero_password or '',
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
            _logger.error('QR Banco Ganadero: fallo HTTP en /qrcode/access: %s', type(exc).__name__)
            raise ValidationError(
                _('No se pudo conectar al servicio de autenticación de Banco Ganadero.')
            ) from exc

        result_code = (data.get('result') or '').strip()
        if result_code != 'COD000':
            msg = data.get('message') or 'Respuesta no satisfactoria'
            raise ValidationError(
                _('QR Banco Ganadero: autenticación rechazada (%s): %s') % (result_code, msg)
            )
        token = (data.get('token') or '').strip()
        if not token:
            raise ValidationError(
                _('QR Banco Ganadero: el servicio /qrcode/access respondió COD000 sin token.')
            )
        return token

