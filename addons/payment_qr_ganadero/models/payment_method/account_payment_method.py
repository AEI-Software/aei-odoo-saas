# -*- coding: utf-8 -*-
"""Register qr_ganadero in Odoo's accounting payment method layer."""

from odoo import api, models


class AccountPaymentMethod(models.Model):
    """Extend account.payment.method so bank journals recognize qr_ganadero."""

    _inherit = 'account.payment.method'

    @api.model
    def _get_payment_method_information(self):
        """Register qr_ganadero as an electronic inbound payment method on bank journals."""
        res = super()._get_payment_method_information()
        res['qr_ganadero'] = {
            'mode': 'electronic',
            'type': ('bank',),
        }
        return res

