"""HTTP routes for the AEI 3-step SaaS checkout (/checkout) and cart interception."""
from urllib.parse import urlencode

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class AeiCheckoutController(WebsiteSale):
    """Serves /checkout and redirects SaaS plan cart submissions into the AEI 3-step flow."""

    @http.route(["/checkout", "/checkout/"], type="http", auth="public", website=True, methods=["GET"])
    def aei_checkout_page(self, **params):
        """Render the 3-step AEI SaaS checkout screen (Account -> Company -> QR / Trial)."""
        ctx = request.website.aei_checkout_context(params, request.session)
        return request.render("aei_website.checkout_page", ctx)

    @http.route("/checkout/company", type="http", auth="user", website=True, methods=["POST"])
    def aei_checkout_company_submit(self, **post):
        """Persist Step 2 company details to res.partner and advance to Step 3."""
        plan = (post.get("plan") or "starter").strip().lower()
        cycle = "annual" if post.get("cycle") == "annual" else "monthly"
        mode = "trial" if post.get("mode") == "trial" else "paid"
        coupon = (post.get("coupon") or "").strip().upper()
        ok = request.website.aei_save_checkout_company(post, request.session)
        step = "3" if ok else "2"
        query = {"plan": plan, "cycle": cycle, "mode": mode, "step": step}
        if coupon:
            query["coupon"] = coupon
        return request.redirect("/checkout?" + urlencode(query), code=303)

    @http.route("/checkout/coupon", type="http", auth="public", website=True, methods=["POST"])
    def aei_checkout_coupon_submit(self, **post):
        """Apply or remove the AEI10 discount coupon and re-render the current checkout step."""
        plan = (post.get("plan") or "starter").strip().lower()
        cycle = "annual" if post.get("cycle") == "annual" else "monthly"
        mode = "trial" if post.get("mode") == "trial" else "paid"
        step = (post.get("step") or "1").strip()
        action = post.get("coupon_action") or "apply"
        raw_coupon = "" if action == "clear" else (post.get("coupon") or "").strip().upper()
        query = {"plan": plan, "cycle": cycle, "mode": mode, "step": step}
        if raw_coupon:
            query["coupon"] = raw_coupon
        return request.redirect("/checkout?" + urlencode(query), code=303)

    @http.route("/checkout/confirm", type="http", auth="user", website=True, methods=["POST"])
    def aei_checkout_confirm_submit(self, **post):
        """Confirm Step 3 (QR Banco Ganadero demo payment or 15-day trial activation)."""
        plan = (post.get("plan") or "starter").strip().lower()
        cycle = "annual" if post.get("cycle") == "annual" else "monthly"
        mode = "trial" if post.get("mode") == "trial" else "paid"
        coupon = (post.get("coupon") or "").strip().upper()
        if not post.get("accept_terms"):
            query = {"plan": plan, "cycle": cycle, "mode": mode, "step": "3"}
            if coupon:
                query["coupon"] = coupon
            return request.redirect("/checkout?" + urlencode(query), code=303)
        confirmed = request.website.aei_confirm_checkout(plan, cycle, mode, coupon, request.session)
        query = {"plan": plan, "cycle": cycle, "mode": mode, "step": "done" if confirmed else "3"}
        if coupon:
            query["coupon"] = coupon
        return request.redirect("/checkout?" + urlencode(query), code=303)

    @http.route(["/shop/cart/update"], type="http", auth="public", methods=["POST"], website=True)
    def cart_update(self, product_id, add_qty=1, set_qty=0, product_custom_attribute_values=None,
                    no_variant_attribute_value_ids=None, **kw):
        """Redirect SaaS plan buttons from / and /pricing into the AEI /checkout flow."""
        if "aei_mode" in kw or "aei_cycle" in kw:
            plan_key = self._aei_plan_key_from_product(product_id)
            cycle = "annual" if kw.get("aei_cycle") == "annual" else "monthly"
            mode = "trial" if kw.get("aei_mode") == "trial" else "paid"
            return request.redirect(
                "/checkout?" + urlencode({"plan": plan_key, "cycle": cycle, "mode": mode}),
                code=303,
            )
        return super().cart_update(
            product_id,
            add_qty=add_qty,
            set_qty=set_qty,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_value_ids=no_variant_attribute_value_ids,
            **kw,
        )

    @http.route(["/shop/cart"], type="http", auth="public", website=True, sitemap=False)
    def cart(self, access_token=None, revive="", **post):
        """Redirect /shop/cart to /checkout when the cart holds a SaaS plan."""
        order = request.website.sale_get_order()
        if order:
            for line in order.order_line:
                key = self._aei_plan_key_from_product(line.product_id.id)
                if key:
                    return request.redirect(
                        "/checkout?" + urlencode({"plan": key, "cycle": "monthly", "mode": "paid"}),
                        code=303,
                    )
        return super().cart(access_token=access_token, revive=revive, **post)

    def _aei_plan_key_from_product(self, product_id):
        """Return 'starter', 'pro', or 'advanced' if product_id belongs to a SaaS plan."""
        try:
            pid = int(product_id)
        except (TypeError, ValueError):
            return "starter"
        product = request.env["product.product"].sudo().browse(pid)
        if not product.exists():
            return "starter"
        tmpl = product.product_tmpl_id.subscription_template_id
        if tmpl and tmpl.plan:
            return "advanced" if tmpl.plan == "enterprise" else tmpl.plan
        name = (product.name or "").strip().lower()
        if name in ("starter", "pro", "advanced"):
            return name
        return False

