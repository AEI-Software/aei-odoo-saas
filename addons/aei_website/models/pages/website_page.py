"""Homepage chrome: hide Odoo's own header and footer where AEI brings its own."""
from odoo import api, models


class WebsitePage(models.Model):
    """Adds the switch that hands the homepage header and footer over to AEI."""

    _inherit = "website.page"

    @api.model
    def aei_use_own_chrome_on_homepage(self):
        """Hide Odoo's header and footer on every homepage record.

        A website gets its own copy of a generic page (when the website is configured or
        the page is edited), and the copy is the one a visitor sees. Setting the flags
        only on the generic record leaves the header visible there, so every record with
        the homepage URL is updated, generic or not.
        """
        homepages = self.with_context(active_test=False).search([("url", "=", "/")])
        homepages.write({"header_visible": False, "footer_visible": False})
        return homepages.ids

