"""Multi-step AEI SaaS checkout: context, Boliviano pricing, and company profile persistence."""
from datetime import datetime, timedelta
from decimal import Decimal
import re
from urllib.parse import urlencode

from odoo import models

from ..plans.plan_pricing import annual_amounts, format_money

COUPON_CODE = "AEI10"
COUPON_RATE = Decimal("0.10")
INDUSTRY_LABELS = {
    "commerce": "Comercial",
    "industry": "Industrial",
    "services": "Servicios",
}


class WebsiteCheckout(models.Model):
    """Extends website with context and company persistence for the 3-step AEI checkout."""

    _inherit = "website"

    def aei_checkout_context(self, params, session):
        """Build the template rendering dictionary for GET /checkout."""
        self.ensure_one()
        plans = self.env["product.template"].website_saas_plans()
        raw_key = (params.get("plan") or "starter").strip().lower()
        plan_key = "enterprise" if raw_key in ("advanced", "enterprise") else raw_key
        plan = next((p for p in plans if p["key"] == plan_key), plans[0] if plans else False)
        cycle = "annual" if params.get("cycle") == "annual" else "monthly"
        mode = "trial" if params.get("mode") == "trial" else "paid"
        coupon = COUPON_CODE if (params.get("coupon") or "").strip().upper() == COUPON_CODE else ""
        is_public = self.env.user._is_public()
        auth_tab = "login" if params.get("auth") == "login" else "register"

        company = dict(session.get("aei_checkout_company") or {})
        if not is_public:
            partner = self.env.user.partner_id.sudo()
            company.setdefault("kind", "company")
            company.setdefault("industry", "services")
            company.setdefault("name", partner.company_name or partner.name or "")
            company.setdefault("nit", partner.vat or "")
            company.setdefault("phone", partner.phone or "")
            company.setdefault("city", partner.city or "Santa Cruz de la Sierra")

        req_step = (params.get("step") or "").strip()
        if is_public:
            step = "1"
        elif req_step in ("1", "2", "3", "done"):
            step = req_step
        else:
            step = "2"

        pricing = self._aei_checkout_pricing(plan["price"] if plan else 349, cycle, mode, coupon)
        now = datetime.utcnow()
        end_dt = now + (timedelta(days=15) if mode == "trial" else timedelta(days=365 if cycle == "annual" else 30))
        qr_info = {}
        done_info = {}
        if not is_public and plan and step == "3" and mode == "paid":
            qr_info = self._aei_prepare_qr_transaction(plan, pricing["total_amount"], company)
        elif not is_public and plan and step == "done":
            done_info = self._aei_build_done_summary(mode, company)

        base_q = {"plan": "advanced" if plan_key == "enterprise" else plan_key, "cycle": cycle, "mode": mode}
        if coupon:
            base_q["coupon"] = coupon
        return {
            "aei_plan": plan,
            "aei_plan_param": base_q["plan"],
            "aei_cycle": cycle,
            "aei_mode": mode,
            "aei_coupon": coupon,
            "aei_step": step,
            "aei_auth_tab": auth_tab,
            "aei_is_public": is_public,
            "aei_user": self.env.user,
            "aei_company": company,
            "aei_pricing": pricing,
            "aei_qr": qr_info,
            "aei_done": done_info,
            "aei_start_date": now.strftime("%d %b %Y"),
            "aei_end_date": end_dt.strftime("%d %b %Y"),
            "aei_step1_url": "/checkout?" + urlencode({**base_q, "step": "1"}),
            "aei_step2_url": "/checkout?" + urlencode({**base_q, "step": "2"}),
            "aei_step2_redirect": "/checkout?" + urlencode({**base_q, "step": "2"}),
            "aei_url_monthly": "/checkout?" + urlencode({**base_q, "cycle": "monthly", "step": step}),
            "aei_url_annual": "/checkout?" + urlencode({**base_q, "cycle": "annual", "step": step}),
            "aei_url_trial": "/checkout?" + urlencode({**base_q, "mode": "trial", "step": step}),
            "aei_url_paid": "/checkout?" + urlencode({**base_q, "mode": "paid", "step": step}),
            "aei_step_done_url": "/checkout?" + urlencode({**base_q, "step": "done"}),
        }

    def _aei_checkout_pricing(self, monthly_price, cycle, mode, coupon):
        """Compute Boliviano amounts for the right-hand TU SELECCIÓN summary card."""
        if cycle == "annual":
            ann = annual_amounts(monthly_price)
            base = ann["total"] + ann["saving"]
            annual_discount = ann["saving"]
            subtotal = ann["total"]
        else:
            base = Decimal(str(monthly_price))
            annual_discount = Decimal("0.00")
            subtotal = base
        coupon_discount = (subtotal * COUPON_RATE).quantize(Decimal("0.01")) if coupon == COUPON_CODE else Decimal("0.00")
        net_total = subtotal - coupon_discount
        payable = Decimal("0.00") if mode == "trial" else net_total
        return {
            "period_label": "12 mensualidades" if cycle == "annual" else "1 mensualidad",
            "base_label": format_money(base),
            "annual_discount_label": ("−" + format_money(annual_discount)) if annual_discount else False,
            "annual_saving_raw": format_money(annual_discount) if annual_discount else False,
            "coupon_discount_label": ("−" + format_money(coupon_discount)) if coupon_discount else False,
            "subtotal_label": format_money(net_total),
            "trial_discount_label": ("−" + format_money(net_total)) if mode == "trial" else False,
            "total_label": format_money(payable),
            "total_amount": float(net_total),
        }

    def aei_save_checkout_company(self, post, session):
        """Save Step 2 company details to session and the authenticated user's res.partner."""
        name = (post.get("name") or "").strip()[:120]
        city = (post.get("city") or "Santa Cruz de la Sierra").strip()[:100]
        nit = (post.get("nit") or "").strip()[:30]
        phone = (post.get("phone") or "").strip()[:30]
        kind = "person" if post.get("kind") == "person" else "company"
        industry = post.get("industry") if post.get("industry") in INDUSTRY_LABELS else "services"
        if not name or not city:
            return False
        company_data = {
            "kind": kind,
            "industry": industry,
            "name": name,
            "nit": nit,
            "phone": phone,
            "city": city,
        }
        session["aei_checkout_company"] = company_data
        session["saas_instance_name"] = name
        if not self.env.user._is_public():
            bolivia = self.env.ref("base.bo", raise_if_not_found=False)
            partner = self.env.user.partner_id.sudo()
            vals = {
                "company_name": name,
                "city": city,
                "street": partner.street or city,
                "zip": partner.zip or "0000",
            }
            if nit:
                vals["vat"] = nit
            if phone:
                vals["phone"] = phone
            if bolivia:
                vals["country_id"] = bolivia.id
            partner.write(vals)
        return True

    def _aei_build_done_summary(self, mode, company):
        """Build the confirmation summary shown on Step Done (.aei-success)."""
        raw_name = company.get("name") or self.env.user.name or "mi-empresa"
        slug = re.sub(r"[^a-z0-9]+", "-", raw_name.lower()).strip("-")[:32] or "mi-empresa"
        partner = self.env.user.partner_id.sudo()
        inst = self.env["saas.instance"].sudo().search(
            [("partner_id", "=", partner.id)], order="id desc", limit=1
        )
        tenant_slug = (inst.tenant_id if inst and inst.tenant_id else slug)
        if inst and inst.url:
            domain = re.sub(r"^https?://", "", inst.url).rstrip("/")
        else:
            domain = f"{tenant_slug}.aeisoftware.com"
        provider = self.env["payment.provider"].sudo().search([("code", "=", "qr_ganadero")], limit=1)
        # Demo only: with no SMTP the customer cannot receive the credentials e-mail, so the
        # generated password is shown here. Never shown when the provider is enabled (production).
        is_demo = not provider or provider.state == "test"
        login_url = f"http://{tenant_slug}.localhost:8080/web/login" if is_demo else f"https://{domain}/web/login"
        return {
            "status_label": "En prueba" if mode == "trial" else "Activa",
            "domain": domain,
            "login_url": login_url,
            "tenant_login": "admin",
            "demo_password": (inst.admin_password or "") if (inst and is_demo) else "",
            "email": self.env.user.email or self.env.user.login,
            "user_first_name": (self.env.user.name or "Cliente").split()[0],
        }
