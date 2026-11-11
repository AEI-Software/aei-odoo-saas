# -*- coding: utf-8 -*-
"""Frontend status polling controller with PostgreSQL SKIP LOCKED throttle."""

import logging
import time

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_BANK_POLL_INTERVAL = 10


class QrGanaderoStatusPollingController(http.Controller):
    """Return transaction state to the browser and poll Point 5 (/status) as fallback."""

    @http.route(
        '/payment/qr_ganadero/status',
        type='json',
        auth='public',
        methods=['POST'],
    )
    def check_status(self, reference=None, **kwargs):
        """Return current transaction state; query Banco Ganadero at most once every 10s."""
        if not reference:
            return {'state': 'error', 'message': 'missing reference'}

        tx = request.env['payment.transaction'].sudo().search(
            [('reference', '=', reference), ('provider_code', '=', 'qr_ganadero')],
            limit=1,
        )
        if not tx:
            return {'state': 'error', 'message': 'transaction not found'}

        if tx.state in ('done', 'cancel', 'error'):
            return {
                'state': tx.state,
                'reference': tx.reference,
                'landing_route': tx.landing_route or '/payment/status',
            }

        if tx.provider_id.state == 'test':
            return {
                'state': tx.state,
                'reference': tx.reference,
                'is_demo': True,
                'landing_route': tx.landing_route or '/payment/status',
            }

        self._poll_bank_if_due(tx)
        tx.invalidate_recordset()
        return {
            'state': tx.state,
            'reference': tx.reference,
            'landing_route': tx.landing_route or '/payment/status',
        }

    def _poll_bank_if_due(self, tx):
        """Acquire advisory row lock with SKIP LOCKED and poll Point 5 (/qrcode/status)."""
        if not tx.qr_ganadero_qr_id:
            return
        try:
            cr = request.env.cr
            cr.execute(
                'SELECT id, qr_ganadero_last_polled '
                'FROM payment_transaction WHERE id = %s FOR UPDATE SKIP LOCKED',
                (tx.id,),
            )
            locked_row = cr.fetchone()
            if locked_row is None:
                return

            last_polled_dt = locked_row[1]
            now_epoch = time.time()
            last_epoch = (
                last_polled_dt.timestamp()
                if last_polled_dt is not None and hasattr(last_polled_dt, 'timestamp')
                else 0
            )
            if now_epoch - last_epoch < _BANK_POLL_INTERVAL:
                return

            cr.execute(
                'UPDATE payment_transaction SET qr_ganadero_last_polled = NOW() WHERE id = %s',
                (tx.id,),
            )
            status_data = tx.provider_id._qr_ganadero_get_status(tx.qr_ganadero_qr_id)
            is_paid, is_cancelled, tx_num, payday = tx._qr_ganadero_is_status_paid(status_data)
            if is_paid:
                tx._handle_notification_data('qr_ganadero', {
                    'qrId': tx.qr_ganadero_qr_id,
                    'transactionId': tx_num or 'POLL',
                    'payDate': payday,
                })
            elif is_cancelled:
                tx._set_canceled()
        except Exception:
            _logger.exception('QR Banco Ganadero: error en polling de estado ref=%s', tx.reference)

