# -*- coding: utf-8 -*-
"""PaymentTransaction extension for Banco Ganadero QR generation and confirmation."""

import logging

from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentTransactionGanadero(models.Model):
    """Extend payment.transaction with Banco Ganadero QR fields and Odoo 18 flow hooks."""

    _inherit = 'payment.transaction'

    qr_ganadero_qr_id = fields.Char(
        string='QR ID (Banco Ganadero)',
        index=True,
        copy=False,
        help='Identificador qrId (hasta 20 caracteres) devuelto por /qrcode/collections.',
    )
    qr_ganadero_image = fields.Text(
        string='Imagen QR (base64)',
        copy=False,
        help='Imagen del QR en base64 devuelta por /qrcode/collections.',
    )
    qr_ganadero_transaction_id = fields.Char(
        string='Nro. Transacción Banco',
        copy=False,
        help='Identificador único de pago (transactionId / transactionNumber) reportado por el banco.',
    )
    qr_ganadero_pay_date = fields.Char(
        string='Fecha de Pago (ddmmyyyy)',
        copy=False,
        help='Fecha de pago reportada por el banco en formato ddmmyyyy.',
    )
    qr_ganadero_last_polled = fields.Datetime(
        string='Último polling Banco Ganadero',
        copy=False,
        help='Timestamp del último polling de estado para throttle entre workers.',
    )

    def _get_specific_rendering_values(self, processing_values):
        """Generate QR in Banco Ganadero and return values for the redirect form."""
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'qr_ganadero':
            return res

        provider = self.provider_id
        reference = processing_values.get('reference') or self.reference
        amount = processing_values.get('amount') or self.amount
        currency_name = self.currency_id.name if self.currency_id else 'BOB'
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')

        qr_image = ''
        qr_id = ''
        try:
            qr_data = provider._qr_ganadero_generate_qr(
                amount=amount,
                currency_name=currency_name,
                gloss=f'Pedido {reference}'[:60],
                reference=reference,
            )
            qr_image = qr_data.get('qrImage') or ''
            qr_id = qr_data.get('qrId') or ''
        except Exception:
            _logger.exception('QR Banco Ganadero: fallo al generar QR para ref=%s', reference)

        self.sudo().write({
            'qr_ganadero_qr_id': qr_id,
            'qr_ganadero_image': qr_image,
        })

        return {
            'reference': reference,
            'qr_image': qr_image,
            'qr_id': qr_id,
            'amount': amount,
            'currency': currency_name,
            'is_demo': provider.state == 'test',
            'status_url': f'{base_url}/payment/qr_ganadero/status',
            'simulate_url': f'{base_url}/payment/qr_ganadero/simulate',
            'landing_route': processing_values.get('landing_route', '/payment/status'),
        }

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Find the payment.transaction matching the qrId from Banco Ganadero."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'qr_ganadero' or len(tx) == 1:
            return tx

        qr_id = (notification_data or {}).get('qrId')
        if not qr_id:
            raise ValidationError(_("QR Banco Ganadero: falta el campo 'qrId' en la notificación."))

        tx = self.search([
            ('qr_ganadero_qr_id', '=', str(qr_id).strip()),
            ('provider_code', '=', 'qr_ganadero'),
        ], limit=1)
        if not tx:
            raise ValidationError(
                _("QR Banco Ganadero: no existe transacción para qrId='%s'.") % qr_id
            )
        return tx

    def _process_notification_data(self, notification_data):
        """Record transactionId and payDate and mark the transaction as done."""
        super()._process_notification_data(notification_data)
        if self.provider_code != 'qr_ganadero':
            return

        tx_id = str(notification_data.get('transactionId') or '').strip()
        pay_date = str(notification_data.get('payDate') or '').strip()
        vals = {}
        if tx_id:
            vals['qr_ganadero_transaction_id'] = tx_id
        if pay_date:
            vals['qr_ganadero_pay_date'] = pay_date
        if vals:
            self.write(vals)

        if self.state != 'done':
            self._set_done()

