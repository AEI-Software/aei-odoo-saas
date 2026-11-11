# -*- coding: utf-8 -*-
"""Inbound authentication, HS256 JWT signing/verification, and payment processing (Points 6, 7, 8)."""

import base64
from datetime import datetime
import hashlib
import hmac
import json
import logging
import re
import secrets
import time

from odoo import models

_logger = logging.getLogger(__name__)

_ALPHANUM_RE = re.compile(r'^[A-Za-z0-9]{1,50}$')
_QR_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,20}$')
_TX_ID_RE = re.compile(r'^[A-Za-z0-9]{1,12}$')


def _b64url_encode(raw_bytes):
    """Encode bytes using URL-safe Base64 without padding per RFC 7515."""
    return base64.urlsafe_b64encode(raw_bytes).rstrip(b'=').decode('ascii')


def _b64url_decode(segment):
    """Decode a URL-safe Base64 segment with RFC 7515 padding restoration."""
    padded = segment + '=' * (-len(segment) % 4)
    return base64.urlsafe_b64decode(padded.encode('ascii'))


class PaymentProviderGanaderoInboundJwt(models.Model):
    """Implement Point 6 (/login) and Point 7 (/payments) business logic and JWT security."""

    _inherit = 'payment.provider'

    def _qr_ganadero_ensure_jwt_secret(self):
        """Ensure a cryptographically strong random JWT secret exists on the provider record."""
        for provider in self:
            if not provider.qr_ganadero_inbound_jwt_secret:
                provider.sudo().write({
                    'qr_ganadero_inbound_jwt_secret': secrets.token_hex(32),
                })

    def _qr_ganadero_issue_inbound_jwt(self, subject_user):
        """Issue an HS256-signed JWT with exp claim for Banco Ganadero (Point 6)."""
        self.ensure_one()
        self._qr_ganadero_ensure_jwt_secret()
        now = int(time.time())
        ttl = max(int(self.qr_ganadero_inbound_jwt_ttl or 3600), 60)
        header = {'alg': 'HS256', 'typ': 'JWT'}
        payload = {
            'sub': subject_user,
            'iat': now,
            'exp': now + ttl,
            'jti': secrets.token_hex(8),
        }
        signing_input = (
            f"{_b64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))}."
            f"{_b64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))}"
        )
        secret_bytes = self.qr_ganadero_inbound_jwt_secret.encode('utf-8')
        sig = hmac.new(secret_bytes, signing_input.encode('ascii'), hashlib.sha256).digest()
        return f'{signing_input}.{_b64url_encode(sig)}'

    def _qr_ganadero_verify_inbound_jwt(self, token):
        """Verify an HS256 JWT issued to Banco Ganadero; reject alg!=HS256 or expired tokens."""
        self.ensure_one()
        if not token or not isinstance(token, str) or not self.qr_ganadero_inbound_jwt_secret:
            return False
        parts = token.strip().split('.')
        if len(parts) != 3:
            return False
        try:
            header = json.loads(_b64url_decode(parts[0]).decode('utf-8'))
            payload = json.loads(_b64url_decode(parts[1]).decode('utf-8'))
            provided_sig = _b64url_decode(parts[2])
        except Exception:
            return False

        if header.get('alg') != 'HS256':
            return False
        signing_input = f'{parts[0]}.{parts[1]}'.encode('ascii')
        secret_bytes = self.qr_ganadero_inbound_jwt_secret.encode('utf-8')
        expected_sig = hmac.new(secret_bytes, signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(provided_sig, expected_sig):
            return False

        exp = payload.get('exp')
        if not isinstance(exp, (int, float)) or time.time() >= exp:
            return False
        return True

    def _qr_ganadero_authenticate_bank(self, body):
        """Validate Point 6 (/login) credentials and return Point 8 response dict."""
        self.ensure_one()
        if not isinstance(body, dict):
            return {'result': 'COD001', 'message': 'Parámetros de entrada insuficientes', 'token': ''}

        user_name = body.get('userName')
        password = body.get('password')
        if not user_name or not password:
            return {'result': 'COD001', 'message': 'Parámetros de entrada insuficientes', 'token': ''}

        if not isinstance(user_name, str) or not isinstance(password, str):
            return {'result': 'COD002', 'message': 'Parámetros fuera del formato establecido', 'token': ''}

        # Point 8: alphanumeric only, max 50 chars, no special characters
        if not _ALPHANUM_RE.match(user_name) or not _ALPHANUM_RE.match(password):
            return {'result': 'COD002', 'message': 'Parámetros fuera del formato establecido', 'token': ''}

        expected_user = (self.qr_ganadero_bank_user or '').strip()
        expected_pass = (self.qr_ganadero_bank_password or '').strip()
        if not expected_user or not expected_pass:
            return {'result': 'COD003', 'message': 'Problemas de procesamiento, vuelva a intentar', 'token': ''}

        user_ok = hmac.compare_digest(user_name.encode('utf-8'), expected_user.encode('utf-8'))
        pass_ok = hmac.compare_digest(password.encode('utf-8'), expected_pass.encode('utf-8'))
        if not (user_ok and pass_ok):
            return {'result': 'COD002', 'message': 'Parámetros fuera del formato establecido', 'token': ''}

        token = self._qr_ganadero_issue_inbound_jwt(user_name)
        return {
            'result': 'COD000',
            'message': 'Resultado satisfactorio',
            'token': token,
        }

    def _qr_ganadero_process_bank_payment(self, auth_header, body):
        """Validate Point 7 (/payments) JWT and payload, confirm tx idempotently, and return (dict, status)."""
        self.ensure_one()
        bearer = (auth_header or '').strip()
        if not bearer.startswith('Bearer '):
            return {'result': 'COD002', 'message': 'Parámetros fuera del formato establecido'}, 401

        raw_token = bearer[7:].strip()
        if not self._qr_ganadero_verify_inbound_jwt(raw_token):
            return {'result': 'COD002', 'message': 'Parámetros fuera del formato establecido'}, 401

        if not isinstance(body, dict):
            return {'result': 'COD001', 'message': 'Parámetros de entrada insuficientes'}, 200

        qr_id = body.get('qrId')
        transaction_id = body.get('transactionId')
        pay_date = body.get('payDate')
        if not qr_id or not transaction_id or not pay_date:
            return {'result': 'COD001', 'message': 'Parámetros de entrada insuficientes'}, 200

        qr_id_str = str(qr_id).strip()
        tx_id_str = str(transaction_id).strip()
        pay_date_str = str(pay_date).strip()

        if not _QR_ID_RE.match(qr_id_str) or not _TX_ID_RE.match(tx_id_str) or not self._is_valid_ddmmyyyy(pay_date_str):
            return {'result': 'COD002', 'message': 'Parámetros fuera del formato establecido'}, 200

        tx = self.env['payment.transaction'].sudo().search([
            ('qr_ganadero_qr_id', '=', qr_id_str),
            ('provider_code', '=', 'qr_ganadero'),
        ], limit=1)
        if not tx:
            return {'result': 'COD002', 'message': 'Parámetros fuera del formato establecido'}, 200

        # Idempotency: if already confirmed, return COD000 without re-confirming
        if tx.state == 'done':
            return {'result': 'COD000', 'message': 'Resultado satisfactorio'}, 200

        try:
            tx._handle_notification_data('qr_ganadero', {
                'qrId': qr_id_str,
                'transactionId': tx_id_str,
                'payDate': pay_date_str,
            })
        except Exception:
            _logger.exception('QR Banco Ganadero: error al procesar pago qrId=%s', qr_id_str)
            return {'result': 'COD003', 'message': 'Problemas de procesamiento, vuelva a intentar'}, 200

        return {'result': 'COD000', 'message': 'Resultado satisfactorio'}, 200

    @staticmethod
    def _is_valid_ddmmyyyy(date_str):
        """Return True if date_str is a valid 8-digit calendar date in ddmmyyyy format."""
        if not isinstance(date_str, str) or len(date_str) != 8 or not date_str.isdigit():
            return False
        try:
            datetime.strptime(date_str, '%d%m%Y')
            return True
        except ValueError:
            return False

