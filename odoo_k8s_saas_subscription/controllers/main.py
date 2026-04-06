from odoo.addons.website_sale.controllers.main import WebsiteSale

class CustomWebsiteSale(WebsiteSale):

    def _get_mandatory_billing_fields(self, country_id=False):
        """
        Override core website_sale logic to only require name and email
        for checkout and registration, speeding up the funnel.
        """
        return ['name', 'email']

    def _get_mandatory_shipping_fields(self, country_id=False):
        """
        Same constraint for shipping address just in case it's used.
        """
        return ['name', 'email']
