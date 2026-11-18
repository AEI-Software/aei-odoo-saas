"""Order creation, Banco Ganadero v1.17.4 QR transaction setup, and checkout confirmation."""
import logging
from datetime import datetime, timedelta

from odoo import fields, models

_logger = logging.getLogger(__name__)


class WebsiteCheckoutOrder(models.Model):
    """Handles sale.order and payment.transaction wiring for the AEI 3-step checkout."""

    _inherit = "website"

    def _aei_prepare_qr_transaction(self, plan, total_amount, company):
        """Create or update the sale.order and payment.transaction for Banco Ganadero QR."""
        partner = self.env.user.partner_id.sudo()
        order = self._aei_get_or_create_checkout_order(partner, plan, total_amount, company.get("name"))
        provider = self.env["payment.provider"].sudo().search([("code", "=", "qr_ganadero")], limit=1)
        if not provider:
            return {"reference": order.name, "qr_image": "", "qr_id": "", "is_demo": True}
        tx = self.env["payment.transaction"].sudo().search(
            [
                ("sale_order_ids", "in", order.ids),
                ("provider_code", "=", "qr_ganadero"),
                ("state", "in", ["draft", "pending"]),
            ],
            order="id desc",
            limit=1,
        )
        if not tx:
            pm = self.env["payment.method"].sudo().search([("code", "=", "qr_ganadero")], limit=1)
            if not pm and provider.payment_method_ids:
                pm = provider.payment_method_ids[0]
            ref = self.env["payment.transaction"].sudo()._compute_reference("qr_ganadero", prefix=order.name)
            tx = self.env["payment.transaction"].sudo().create({
                "provider_id": provider.id,
                "payment_method_id": pm.id if pm else False,
                "reference": ref,
                "amount": order.amount_total,
                "currency_id": order.currency_id.id,
                "partner_id": partner.id,
                "sale_order_ids": [(6, 0, [order.id])],
                "state": "pending",
            })
        elif tx.amount != order.amount_total:
            tx.write({"amount": order.amount_total, "qr_ganadero_qr_id": False})
        if not tx.qr_ganadero_qr_id:
            tx._get_specific_rendering_values({"reference": tx.reference, "amount": tx.amount})
        return {
            "tx_id": tx.id,
            "reference": tx.reference,
            "qr_id": tx.qr_ganadero_qr_id or tx.reference,
            "qr_image": tx.qr_ganadero_image or "",
            "is_demo": provider.state == "test",
        }

    def _aei_get_or_create_checkout_order(self, partner, plan, total_amount, instance_name):
        """Ensure a draft sale.order exists for the partner and selected SaaS plan."""
        SaleOrder = self.env["sale.order"].sudo()
        order = SaleOrder.search(
            [("partner_id", "=", partner.id), ("state", "=", "draft")],
            order="id desc",
            limit=1,
        )
        bob = self.env["res.currency"].sudo().search([("name", "=", "BOB")], limit=1)
        if not order:
            order = SaleOrder.create({"partner_id": partner.id})
        if bob and order.pricelist_id.currency_id != bob:
            pl = self.env["product.pricelist"].sudo().search([("currency_id", "=", bob.id)], limit=1)
            if pl:
                order.pricelist_id = pl.id
        line_vals = {
            "product_id": plan["variant_id"],
            "product_uom_qty": 1.0,
            "price_unit": total_amount,
            "tax_id": [(5, 0, 0)],
        }
        if "saas_instance_name" in self.env["sale.order.line"]._fields and instance_name:
            line_vals["saas_instance_name"] = instance_name
        if len(order.order_line) == 1 and order.order_line.product_id.id == plan["variant_id"]:
            order.order_line.sudo().write(line_vals)
        else:
            order.order_line.unlink()
            line_vals["order_id"] = order.id
            self.env["sale.order.line"].sudo().create(line_vals)
        return order

    def aei_confirm_checkout(self, plan_key, cycle, mode, coupon, session):
        """Confirm either the QR payment (in test/demo mode) or the 15-day free trial."""
        if self.env.user._is_public():
            return False
        clean_ctx = {k: v for k, v in self.env.context.items() if k != "company_id"}
        clean_self = self.with_context(clean_ctx)
        plans = clean_self.env["product.template"].website_saas_plans()
        norm_key = "enterprise" if plan_key in ("advanced", "enterprise") else plan_key
        plan = next((p for p in plans if p["key"] == norm_key), plans[0] if plans else False)
        if not plan:
            return False
        company = session.get("aei_checkout_company") or {}
        pricing = clean_self._aei_checkout_pricing(plan["price"], cycle, mode, coupon)
        partner = clean_self.env.user.partner_id.sudo()
        if mode == "paid":
            qr_info = clean_self._aei_prepare_qr_transaction(plan, pricing["total_amount"], company)
            if not qr_info.get("is_demo"):
                # Real provider: only the bank (Point 7 webhook) may mark the payment as done.
                return False
            tx = clean_self.env["payment.transaction"].sudo().browse(qr_info.get("tx_id"))
            if tx and tx.exists() and tx.state != "done":
                tx._process_notification_data({
                    "qrId": tx.qr_ganadero_qr_id or tx.reference,
                    "transactionId": f"GAN-{tx.id:08d}",
                    "payDate": datetime.utcnow().strftime("%d%m%Y"),
                })
                try:
                    tx._post_process()
                except Exception:  # noqa: BLE001
                    # The invoice e-mail PDF cannot render inside a website request (the
                    # website qweb context overrides company_id with an int). The order is
                    # already confirmed and invoiced; the "Payment: Post-process transactions"
                    # cron re-sends the invoice later from a request-less context.
                    _logger.exception("AEI checkout: invoice e-mail deferred to cron for %s", tx.reference)
            order = tx.sale_order_ids[:1]
        else:
            order = clean_self._aei_get_or_create_checkout_order(partner, plan, 0.0, company.get("name"))
            if order.state == "draft":
                order.action_confirm()
            sub = clean_self.env["sale.subscription"].sudo().search(
                [("sale_order_id", "=", order.id)], order="id desc", limit=1
            )
            stage = clean_self.env.ref(
                "subscription_oca.subscription_stage_in_progress", raise_if_not_found=False
            )
            if sub and stage:
                sub.write({
                    "stage_id": stage.id,
                    "recurring_next_date": fields.Date.today() + timedelta(days=15),
                })
        return order.id if order else False

