"""Offers shown on the published design: billing period, trial, FAQ and fine print.

At this stage they are UI only (owner decision, 2026-11-05): the internal wiring to
trial, annual billing and coupons comes later. These tests pin what the visitor sees.
"""
from lxml import html

from odoo.tests import HttpCase, tagged

PLAN_KEYS = ("starter", "pro", "enterprise")
PLAN_LABELS = {"starter": "Starter", "pro": "Pro", "enterprise": "Advanced"}


@tagged("post_install", "-at_install")
class TestLandingOffers(HttpCase):
    """Billing bar, plan actions, FAQ and fine print of the home page."""

    def _home(self):
        response = self.url_open("/")
        self.assertEqual(response.status_code, 200)
        return html.fromstring(response.content)

    def _card(self, tree, key):
        return tree.xpath('//*[@data-plan-card="%s"]' % key)[0]

    def _cycle_texts(self, card, cycle):
        nodes = card.xpath('.//*[@data-aei-cycle="%s"]' % cycle)
        return {n.get("data-aei-field"): n.text_content().strip() for n in nodes}

    def test_billing_bar_offers_monthly_and_annual(self):
        tree = self._home()
        buttons = tree.xpath("//*[@data-billing]")
        self.assertEqual([b.get("data-billing") for b in buttons], ["monthly", "annual"])
        self.assertEqual([b.get("aria-pressed") for b in buttons], ["true", "false"])
        bar = tree.xpath('//*[contains(@class, "aei-billing-bar")]')[0].text_content()
        for phrase in ("A TU RITMO", "15 días para conocer tu próximo sistema.",
                       "Sin tarjeta para empezar", "−20%"):
            self.assertIn(phrase, bar)

    def test_monthly_amounts_are_visible_and_annual_ones_hidden(self):
        card = self._card(self._home(), "starter")
        monthly = card.xpath('.//*[@data-aei-cycle="monthly"]')
        annual = card.xpath('.//*[@data-aei-cycle="annual"]')
        self.assertTrue(monthly and annual)
        self.assertTrue(all(n.get("hidden") is None for n in monthly))
        self.assertTrue(all(n.get("hidden") is not None for n in annual))
        self.assertEqual(self._cycle_texts(card, "monthly")["detail"], "Facturado mensualmente")

    def test_annual_amounts_follow_the_design_rules(self):
        # 349/month -> 4.188 a year, 20% off = 837,60, billed 3.350,40, 279,20 a month
        starter = self._cycle_texts(self._card(self._home(), "starter"), "annual")
        self.assertEqual(starter["price"], "279,20")
        self.assertEqual(starter["detail"], "Bs 3.350,40 facturados al año")
        self.assertEqual(starter["saving"], "Ahorras Bs 837,60 al año")

    def test_annual_amounts_follow_the_product_price(self):
        self.env.ref("aei_website.product_saas_plan_enterprise").list_price = 1290
        advanced = self._cycle_texts(self._card(self._home(), "enterprise"), "annual")
        self.assertEqual(advanced["detail"], "Bs 12.384,00 facturados al año")
        self.assertEqual(advanced["saving"], "Ahorras Bs 3.096,00 al año")

    def test_each_plan_has_trial_and_purchase_forms(self):
        tree = self._home()
        for key in PLAN_KEYS:
            forms = self._card(tree, key).xpath('.//form[@action="/shop/cart/update"]')
            self.assertEqual(len(forms), 2, key)
            modes = [f.xpath('.//input[@name="aei_mode"]/@value')[0] for f in forms]
            self.assertEqual(modes, ["trial", "paid"], key)
            for form in forms:
                self.assertTrue(form.xpath('.//input[@name="csrf_token"]/@value')[0], key)
                self.assertTrue(form.xpath('.//input[@name="aei_cycle"]'), key)
            labels = [f.xpath(".//button")[0].text_content() for f in forms]
            self.assertIn("Probar 15 días gratis", labels[0])
            self.assertIn("Elegir " + PLAN_LABELS[key], labels[1])

    def test_report_counts_come_from_the_catalog(self):
        tree = self._home()
        expected = {"starter": "7", "pro": "15", "enterprise": "15"}
        for key, count in expected.items():
            text = self._card(tree, key).text_content()
            self.assertIn(count + " reportes financieros y fiscales", text, key)

    def test_faq_has_the_eight_questions_of_the_design(self):
        tree = self._home()
        self.assertEqual(len(tree.xpath("//details[not(ancestor::dialog)]")), 8)
        text = tree.text_content()
        self.assertIn("¿Cómo funciona la prueba gratuita?", text)
        self.assertIn("¿Cuánto ahorro con el plan anual?", text)

    def test_fine_print_and_header_call_to_action(self):
        tree = self._home()
        text = " ".join(tree.text_content().split())
        self.assertIn("Plan anual con 20% de descuento; prueba gratuita de 15 días sin tarjeta.", text)
        header = tree.xpath('//header[contains(@class, "aei-site-header")]')[0].text_content()
        self.assertIn("Pruébalo gratis", header)
        self.assertTrue(tree.xpath('//a[contains(., "Comparar todos los módulos")]'))

