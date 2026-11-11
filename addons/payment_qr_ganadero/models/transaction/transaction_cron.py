# -*- coding: utf-8 -*-
"""Fallback cron poller for pending Banco Ganadero QR transactions (Point 5: /qrcode/status)."""

from datetime import timedelta
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

_POLL_MAX_AGE_HOURS = 24
_ORDER_STATE_PAID = 2
_ORDER_STATE_CANCELLED = 3


class PaymentTransactionGanaderoCron(models.Model):
    """Poll Banco Ganadero /qrcode/status for recent pending QR transactions."""

    _inherit = 'payment.transaction'

    @staticmethod
    def _qr_ganadero_is_status_paid(status_data):
        """Return (is_paid, is_cancelled, tx_number, payday) from a Point 5 /status response."""
        if not isinstance(status_data, dict):
            return False, False, '', ''
        if (status_data.get('result') or '').strip() != 'COD000':
            return False, False, '', ''
        try:
            order_state = int(status_data.get('orderState') or 0)
        except (TypeError, ValueError):
            order_state = 0
        tx_num = str(status_data.get('transactionNumber') or '').strip()
        payday = str(status_data.get('payday') or '').strip()
        return (
            order_state == _ORDER_STATE_PAID,
            order_state == _ORDER_STATE_CANCELLED,
            tx_num,
            payday,
        )

    @api.model
    def _cron_qr_ganadero_poll_pending(self):
        """Check pending QR Ganadero transactions created in the last 24h against Point 5."""
        limit_dt = fields.Datetime.now() - timedelta(hours=_POLL_MAX_AGE_HOURS)
        pending = self.search([
            ('provider_code', '=', 'qr_ganadero'),
            ('state', 'in', ['draft', 'pending']),
            ('create_date', '>=', limit_dt),
            ('provider_id.state', '!=', 'test'),
            ('qr_ganadero_qr_id', '!=', False),
        ])
        for tx in pending:
            try:
                status_data = tx.provider_id._qr_ganadero_get_status(tx.qr_ganadero_qr_id)
                is_paid, is_cancelled, tx_num, payday = self._qr_ganadero_is_status_paid(status_data)
                if is_paid:
                    tx._handle_notification_data('qr_ganadero', {
                        'qrId': tx.qr_ganadero_qr_id,
                        'transactionId': tx_num or 'POLL',
                        'payDate': payday,
                    })
                elif is_cancelled:
                    tx._set_canceled()
            except Exception:
                _logger.exception('QR Banco Ganadero cron: error al consultar ref=%s', tx.reference)

