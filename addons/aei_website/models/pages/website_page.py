"""Public page chrome: hide Odoo's default header and footer where AEI renders its own."""
from odoo import api, models

AEI_PUBLIC_PAGE_URLS = ("/", "/contactus", "/contactus-thank-you")


class WebsitePage(models.Model):
    """Configures public website pages that carry AEI's custom header and footer."""

    _inherit = "website.page"

    @api.model
    def aei_use_own_chrome_on_homepage(self):
        """Hide Odoo's header and footer on every homepage record.

        A website gets its own copy of a generic page when edited or configured,
        so every record with ``url == '/'`` is updated, generic or per-website.
        """
        homepages = self.with_context(active_test=False).search([("url", "=", "/")])
        homepages.write({"header_visible": False, "footer_visible": False})
        return homepages.ids

    @api.model
    def aei_use_own_chrome_on_public_pages(self):
        """Hide Odoo's header and footer on all AEI-styled public pages and enable public signup."""
        pages = self.with_context(active_test=False).search(
            [("url", "in", list(AEI_PUBLIC_PAGE_URLS))]
        )
        pages.write({"header_visible": False, "footer_visible": False})
        websites = self.env["website"].with_context(active_test=False).search([])
        if "auth_signup_uninvited" in self.env["website"]._fields:
            websites.filtered(lambda w: w.auth_signup_uninvited != "b2c").write(
                {"auth_signup_uninvited": "b2c"}
            )
        params = self.env["ir.config_parameter"].sudo()
        if params.get_param("auth_signup.invitation_scope", "b2b") != "b2c":
            params.set_param("auth_signup.invitation_scope", "b2c")
        return pages.ids
