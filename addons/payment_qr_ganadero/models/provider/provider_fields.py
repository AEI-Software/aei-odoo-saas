# -*- coding: utf-8 -*-
"""Configuration and credential fields on payment.provider for Banco Ganadero."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_REQUIRED_ENABLED_FIELDS = (
    ('qr_ganadero_base_url', 'URL Base API (Ganadero)'),
    ('qr_ganadero_api_key', 'API Key (Ganadero)'),
    ('qr_ganadero_api_key_header', 'Cabecera API Key (Ganadero)'),
    ('qr_ganadero_username', 'Usuario API (Ganadero)'),
    ('qr_ganadero_password', 'Contraseña API (Ganadero)'),
    ('qr_ganadero_account_ref', 'Referencia de Cuenta (Ganadero)'),
)


class PaymentProviderGanaderoFields(models.Model):
    """Add Banco Ganadero QR Empresarial fields to payment.provider."""

    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('qr_ganadero', 'QR Banco Ganadero')],
        ondelete={'qr_ganadero': 'set default'},
    )

    # ── Outbound API Credentials (stored per environment in DB, never hardcoded) ─
    qr_ganadero_base_url = fields.Char(
        string='URL Base API (Ganadero)',
        help='Host base del servicio QR Empresarial asignado por el Banco Ganadero.',
    )
    qr_ganadero_api_key = fields.Char(
        string='API Key (Ganadero)',
        help='Clave de seguridad asignada a la empresa por el Banco Ganadero.',
    )
    qr_ganadero_api_key_header = fields.Char(
        string='Cabecera API Key (Ganadero)',
        default='X-Api-Key',
        help='Nombre de la cabecera HTTP enviada en el servicio de autenticación.',
    )
    qr_ganadero_username = fields.Char(
        string='Usuario API (Ganadero)',
        help='Código de cliente con rol cobrador de la empresa.',
    )
    qr_ganadero_password = fields.Char(
        string='Contraseña API (Ganadero)',
        help='Clave del cliente con rol cobrador de la empresa.',
    )
    qr_ganadero_account_ref = fields.Char(
        string='Referencia de Cuenta (Ganadero)',
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

    @api.constrains(
        'state',
        'qr_ganadero_base_url',
        'qr_ganadero_api_key',
        'qr_ganadero_api_key_header',
        'qr_ganadero_username',
        'qr_ganadero_password',
        'qr_ganadero_account_ref',
    )
    def _check_qr_ganadero_enabled_credentials(self):
        """Require real bank credentials only when the provider is enabled (not in local demo mode)."""
        for provider in self:
            if provider.code != 'qr_ganadero' or provider.state != 'enabled':
                continue
            missing = [
                label
                for field_name, label in _REQUIRED_ENABLED_FIELDS
                if not (provider[field_name] or '').strip()
            ]
            if missing:
                raise ValidationError(
                    _('QR Banco Ganadero requiere configurar: %s') % ', '.join(missing)
                )
