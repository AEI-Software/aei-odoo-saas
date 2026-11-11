# -*- coding: utf-8 -*-
"""Configuration and credential fields on payment.provider for Banco Ganadero."""

from odoo import fields, models

_DEFAULT_BASE_URL = 'https://sandbox.bg.com.bo'


class PaymentProviderGanaderoFields(models.Model):
    """Add Banco Ganadero QR Empresarial fields to payment.provider."""

    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('qr_ganadero', 'QR Banco Ganadero')],
        ondelete={'qr_ganadero': 'set default'},
    )

    # ── Outbound API Credentials ─────────────────────────────────────────────
    qr_ganadero_base_url = fields.Char(
        string='URL Base API (Ganadero)',
        default=_DEFAULT_BASE_URL,
        required_if_provider='qr_ganadero',
        help='Host base del servicio QR Empresarial del Banco Ganadero.',
    )
    qr_ganadero_api_key = fields.Char(
        string='API Key (Ganadero)',
        required_if_provider='qr_ganadero',
        help='Clave de seguridad asignada a la empresa por el Banco Ganadero.',
    )
    qr_ganadero_api_key_header = fields.Char(
        string='Cabecera API Key (Ganadero)',
        default='XApi--Key',
        required_if_provider='qr_ganadero',
        help='Nombre de la cabecera HTTP enviada en el servicio de autenticación.',
    )
    qr_ganadero_username = fields.Char(
        string='Usuario API (Ganadero)',
        required_if_provider='qr_ganadero',
        help='Código de cliente con rol cobrador de la empresa.',
    )
    qr_ganadero_password = fields.Char(
        string='Contraseña API (Ganadero)',
        required_if_provider='qr_ganadero',
        help='Clave del cliente con rol cobrador de la empresa.',
    )
    qr_ganadero_account_ref = fields.Char(
        string='Referencia de Cuenta (Ganadero)',
        required_if_provider='qr_ganadero',
        help='Alias de la cuenta recaudadora parametrizada en GanaNet (máx. 20 caracteres).',
    )
    qr_ganadero_ssl_verify = fields.Boolean(
        string='Verificar SSL (Ganadero)',
        default=True,
        help='Desactivar solo en ambientes de desarrollo con certificados autofirmados.',
    )

    # ── Outbound JWT Cache (shared across workers via PostgreSQL) ────────────
    qr_ganadero_token_cache = fields.Char(
        string='JWT Token cacheado (Ganadero)',
        copy=False,
        help='Caché interno del token JWT del banco. No editar manualmente.',
    )
    qr_ganadero_token_expires = fields.Float(
        string='Token expira epoch (Ganadero)',
        copy=False,
        help='Timestamp UNIX en que el token saliente expira.',
    )

    # ── Inbound Webhook Credentials ──────────────────────────────────────────
    qr_ganadero_bank_user = fields.Char(
        string='Usuario Entrante',
        default='BANCOGANADERO1',
        help='Usuario alfanumérico sin caracteres especiales para que el banco se autentique en /login.',
    )
    qr_ganadero_bank_password = fields.Char(
        string='Contraseña Entrante',
        copy=False,
        help='Contraseña alfanumérica sin caracteres especiales para que el banco se autentique en /login.',
    )
    qr_ganadero_inbound_jwt_secret = fields.Char(
        string='Secreto Firma JWT Entrante',
        copy=False,
        help='Secreto criptográfico con el que Odoo firma el token entregado al banco.',
    )
    qr_ganadero_inbound_jwt_ttl = fields.Integer(
        string='Vigencia Token (segundos)',
        default=3600,
        help='Tiempo de vigencia en segundos del token emitido por Odoo al banco.',
    )
