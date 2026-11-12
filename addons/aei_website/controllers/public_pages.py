"""Public HTTP routes for the friendly /account alias and CSRF-protected /contactus form."""
from urllib.parse import urlencode

from odoo import http
from odoo.http import request

GENERIC_CONTACT_ERROR = "Revisa los datos ingresados e inténtalo nuevamente."


class AeiPublicPagesController(http.Controller):
    """Serves the /account redirect and processes public contact inquiries."""

    @http.route("/account", type="http", auth="public", website=True, methods=["GET"])
    def account_redirect(self, **kwargs):
        """Redirect /account to Odoo's /web/login (or /my when already signed in)."""
        if not request.env.user._is_public():
            return request.redirect("/my", code=303)
        query = urlencode(kwargs) if kwargs else ""
        target = f"/web/login?{query}" if query else "/web/login"
        return request.redirect(target, code=303)

    @http.route("/contactus/submit", type="http", auth="public", website=True, methods=["POST"])
    def submit_contact_form(self, **post):
        """Validate and submit the public contact form with Odoo's built-in CSRF check."""
        # TODO(security): Per-IP rate limiting is enforced at the Traefik ingress middleware
        # layer in K8s; keep application-level validation fail-closed here.
        ok, cleaned = request.website.submit_aei_contact_form(post)
        if not ok:
            return request.render(
                "website.contactus",
                {
                    "aei_contact_error": GENERIC_CONTACT_ERROR,
                    "aei_contact_values": cleaned,
                },
            )
        return request.redirect("/contactus-thank-you", code=303)

    @http.route("/contactus-thank-you", type="http", auth="public", website=True, methods=["GET"])
    def contact_thank_you(self, **_kwargs):
        """Render the AEI-styled confirmation page after a valid contact submission."""
        return request.render("aei_website.contactus_thanks_page")
