# -*- coding: utf-8 -*-
"""'Test connection' action: verifies the outbound credentials against Point 2 (/qrcode/access)."""

from odoo import _, models
from odoo.exceptions import ValidationError


class PaymentProviderGanaderoConnectionCheck(models.Model):
    """Adds the connection check used from the provider form before a real test with the bank."""

    _inherit = 'payment.provider'

    def action_qr_ganadero_test_connection(self):
        """Ask the bank for a fresh token and report the outcome as a notification.

        The cached token is discarded first so the stored credentials are really verified.
        The message carries the bank result code and text, never a credential or the token.
        """
        self.ensure_one()
        if self.state == 'test':
            return self._qr_ganadero_notification(
                'warning',
                _('El proveedor está en modo prueba (demo): no se conecta al banco. '
                  'Cámbialo a "Habilitado" para verificar las credenciales.'),
            )
        self.write({'qr_ganadero_token_cache': False, 'qr_ganadero_token_expires': 0.0})
        try:
            self._qr_ganadero_get_token()
        except ValidationError as exc:
            return self._qr_ganadero_notification('danger', str(exc))
        return self._qr_ganadero_notification(
            'success', _('Conexión exitosa: el Banco Ganadero aceptó las credenciales.')
        )

    def _qr_ganadero_notification(self, kind, message):
        """Build a client notification action; failures stay on screen until closed."""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('QR Banco Ganadero'),
                'message': message,
                'type': kind,
                'sticky': kind != 'success',
            },
        }
