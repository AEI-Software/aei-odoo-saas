# -*- coding: utf-8 -*-
"""Standalone test QR for the joint certification with Banco Ganadero.

The bank's procedure is: we generate a QR and send them the image, they pay it and notify
our /payments endpoint. This wizard creates that QR on its own pending transaction, with
no sale order, so the test never triggers invoicing, subscriptions or tenant provisioning.
"""

import base64
import binascii

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Prefix of the transaction reference, so test payments are easy to spot in Odoo.
TEST_REFERENCE_PREFIX = 'QRTEST'
# Leading bytes of the image formats the bank may return, mapped to a file extension.
IMAGE_SIGNATURES = (
    (b'\x89PNG', 'png'),
    (b'\xff\xd8', 'jpg'),
    (b'<svg', 'svg'),
    (b'<?xml', 'svg'),
)
UNKNOWN_IMAGE_EXTENSION = 'bin'


class PaymentQrGanaderoTestQr(models.TransientModel):
    """Generates one QR against the bank and keeps its image ready to download."""

    _name = 'payment.qr.ganadero.test.qr'
    _description = 'QR Banco Ganadero: QR de prueba'

    provider_id = fields.Many2one(
        'payment.provider', string='Proveedor', required=True, ondelete='cascade',
        domain=[('code', '=', 'qr_ganadero')],
    )
    amount = fields.Float(string='Monto', required=True, digits=(15, 2))
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True,
        default=lambda self: self.env.company.currency_id,
    )
    gloss = fields.Char(string='Glosa', size=60)
    transaction_id = fields.Many2one('payment.transaction', string='Transacción', readonly=True)
    qr_id = fields.Char(related='transaction_id.qr_ganadero_qr_id', string='QR ID')
    transaction_state = fields.Selection(related='transaction_id.state', string='Estado')
    qr_file = fields.Binary(string='Imagen QR', readonly=True, attachment=False)
    qr_filename = fields.Char(readonly=True)

    @api.constrains('amount')
    def _check_amount(self):
        """Reject zero or negative amounts before anything is sent to the bank."""
        for wizard in self:
            if wizard.amount <= 0:
                raise ValidationError(_('El monto del QR de prueba debe ser mayor a cero.'))

    def action_generate(self):
        """Ask the bank for a QR, store it on a new pending transaction and show the result.

        The QR is requested first: if the bank rejects it, the ValidationError reaches the
        user and no transaction is left behind.
        """
        self.ensure_one()
        provider = self.provider_id
        transactions = self.env['payment.transaction'].sudo()
        reference = transactions._compute_reference(provider.code, prefix=TEST_REFERENCE_PREFIX)
        data = provider._qr_ganadero_generate_qr(
            amount=self.amount,
            currency_name=self.currency_id.name,
            gloss=self.gloss or reference,
            reference=reference,
        )
        image_b64 = self._qr_image_base64(data.get('qrImage'))
        tx = transactions.create({
            'provider_id': provider.id,
            'payment_method_id': self._qr_payment_method(provider).id,
            'reference': reference,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'partner_id': provider.company_id.partner_id.id,
            'state': 'pending',
            'qr_ganadero_qr_id': data.get('qrId') or False,
            'qr_ganadero_image': image_b64,
        })
        self.write({
            'transaction_id': tx.id,
            'qr_file': image_b64,
            'qr_filename': f'{reference}.{self._image_extension(image_b64)}',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @staticmethod
    def _qr_payment_method(provider):
        """Return the provider's own QR payment method, or fail with a clear message."""
        method = provider.payment_method_ids.filtered(lambda m: m.code == provider.code)[:1]
        method = method or provider.payment_method_ids[:1]
        if not method:
            raise ValidationError(_('El proveedor no tiene un método de pago configurado.'))
        return method

    @staticmethod
    def _qr_image_base64(raw):
        """Return the bare base64 payload, accepting a 'data:<mime>;base64,' prefix too."""
        value = (raw or '').strip()
        if value.startswith('data:') and ',' in value:
            value = value.split(',', 1)[1]
        return value

    @staticmethod
    def _image_extension(image_b64):
        """Guess the file extension from the image bytes; unknown formats are not renamed."""
        try:
            head = base64.b64decode(image_b64)[:8]
        except (binascii.Error, ValueError):
            return UNKNOWN_IMAGE_EXTENSION
        for signature, extension in IMAGE_SIGNATURES:
            if head.startswith(signature):
                return extension
        return UNKNOWN_IMAGE_EXTENSION
