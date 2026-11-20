"""HTTP tests for the public /pricing page (spec scenario E5)."""
from lxml import html

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestPricingPage(HttpCase):
    """Verify the dedicated /pricing page structure, plan checkmarks, matrix, and reports."""

    def _pricing(self):
        """Fetch /pricing and parse its HTML tree."""
        response = self.url_open("/pricing")
        self.assertEqual(response.status_code, 200)
        return html.fromstring(response.content)

    def test_pricing_page_uses_own_chrome_and_renders_heading(self):
        """GET /pricing hides Odoo's default chrome and renders the AEI pricing heading."""
        tree = self._pricing()
        odoo_header = tree.xpath('//header[@id="top"]')
        self.assertTrue(odoo_header)
        self.assertIn("d-none", odoo_header[0].get("class", ""))
        self.assertTrue(tree.xpath('//header[contains(@class, "aei-site-header")]'))
        self.assertTrue(tree.xpath('//footer[contains(@class, "aei-footer")]'))

        heading = tree.xpath('//section[contains(@class, "aei-page-heading")]')
        self.assertEqual(len(heading), 1)
        heading_text = " ".join(heading[0].text_content().split())
        self.assertIn("PLANES DE SUSCRIPCIÓN", heading_text)
        self.assertIn("Elige por lo que necesitas hacer.", heading_text)
        self.assertTrue(heading[0].xpath('.//*[contains(@class, "aei-invoice-hero")]'))
        self.assertTrue(heading[0].xpath('.//a[@href="#modulos"]'))

    def test_pricing_page_renders_plans_and_four_common_checkmarks(self):
        """The #planes section on /pricing shows the 3 cards, 4 checkmarks, and 2-line fineprint."""
        tree = self._pricing()
        plans_sec = tree.xpath('//section[@id="planes"]')[0]
        self.assertTrue(plans_sec.xpath('.//*[contains(@class, "aei-billing-bar")]'))
        for key in ("starter", "pro", "enterprise"):
            self.assertEqual(len(plans_sec.xpath('.//*[@data-plan-card="%s"]' % key)), 1, key)
            self.assertEqual(len(tree.xpath('//dialog[@id="aei-plan-dialog-%s"]' % key)), 1, key)

        common = plans_sec.xpath('.//*[contains(@class, "aei-plans-common")]')
        self.assertEqual(len(common), 1)
        common_text = " ".join(common[0].text_content().split())
        for check in (
            "Instancia privada",
            "Facturación SIAT*",
            "Roles y contador",
            "Respaldos y exportación",
        ):
            self.assertIn(check, common_text)

        fineprint = " ".join(plans_sec.text_content().split())
        self.assertIn("Los cupos incluyen los usuarios contratados", fineprint)
        self.assertIn("*La emisión fiscal requiere habilitación del emisor", fineprint)

    def test_pricing_page_renders_comparison_matrix_and_filters(self):
        """The #modulos section renders the 4 filter buttons and all 16 module comparison rows."""
        tree = self._pricing()
        modulos = tree.xpath('//section[@id="modulos"]')[0]
        filters = modulos.xpath('.//button[@data-module-filter]')
        self.assertEqual(
            [b.get("data-module-filter") for b in filters],
            ["all", "finance", "operation", "platform"],
        )
        self.assertIn("aei-is-active", filters[0].get("class", ""))
        self.assertEqual(filters[0].get("aria-pressed"), "true")
        count = modulos.xpath('.//*[@data-module-count]')[0].text_content().strip()
        self.assertEqual(count, "16 alcances")

        rows = modulos.xpath('.//table[contains(@class, "aei-comparison")]/tbody/tr[@data-module-row]')
        self.assertEqual(len(rows), 16)
        row_ids = [r.get("data-module-row") for r in rows]
        self.assertIn("analytics", row_ids)
        self.assertIn("reports", row_ids)

        reports_row = modulos.xpath('.//tr[@data-module-row="reports"]')[0].text_content()
        for phrase in ("7", "Reportes base", "15", "Base + adicionales", "Todo Pro"):
            self.assertIn(phrase, reports_row)

    def test_pricing_page_renders_reports_faq_and_cta(self):
        """The /pricing page includes #reportes, the 8 FAQ items, and the final advisory CTA."""
        tree = self._pricing()
        reportes = tree.xpath('//section[@id="reportes"]')[0]
        rep_text = " ".join(reportes.text_content().split())
        self.assertIn("STARTER · 7 REPORTES", rep_text)
        self.assertIn("PRO Y ADVANCED · 15 REPORTES", rep_text)
        self.assertIn("Libro de ventas de Bolivia", rep_text)
        self.assertIn("Balance de Comprobación (Sumas y Saldos)", rep_text)

        faq_details = tree.xpath('//div[contains(@class, "aei-faq")]/details')
        self.assertEqual(len(faq_details), 8)

        cta = tree.xpath('//section[contains(@class, "aei-final-cta")]')[0]
        self.assertIn("El plan correcto empieza por tus procesos.", cta.text_content())
        self.assertTrue(cta.xpath('.//a[@href="/contactus"]'))

    def test_header_and_footer_link_to_pricing_and_modulos(self):
        """Header and footer navigation links point to /pricing and /pricing#modulos."""
        tree = self._pricing()
        nav = tree.xpath('//nav[@id="aei-site-nav"]')[0]
        self.assertTrue(nav.xpath('.//a[@href="/pricing"]'))
        self.assertTrue(nav.xpath('.//a[@href="/pricing#modulos"]'))
        footer = tree.xpath('//footer[contains(@class, "aei-footer")]')[0]
        self.assertTrue(footer.xpath('.//a[@href="/pricing"]'))
        self.assertTrue(footer.xpath('.//a[@href="/pricing#modulos"]'))

    def test_checkout_summary_shows_the_plan_capacities_from_the_template(self):
        """HU-06: users, storage and support hours come from the subscription template."""
        template = self.env.ref("aei_website.product_saas_plan_starter").subscription_template_id
        template.write({"included_users": 4, "storage_gi": 12, "support_hours_included": 6})
        tree = html.fromstring(self.url_open("/checkout?plan=starter").content)
        summary = " ".join(tree.xpath('string(//*[contains(@class, "aei-order-plan")])').split())
        self.assertIn("1 empresa · 4 usuarios · 12 GB · 6 h soporte/mes", summary)

    def test_checkout_trial_step_shows_the_plan_capacities_from_the_template(self):
        """HU-06: the trial activation step lists the same capacities, support included."""
        template = self.env.ref("aei_website.product_saas_plan_starter").subscription_template_id
        template.write({"included_users": 4, "storage_gi": 12, "support_hours_included": 6})
        self.authenticate("admin", "admin")
        tree = html.fromstring(self.url_open("/checkout?plan=starter&mode=trial&step=3").content)
        features = " ".join(tree.xpath('string(//*[contains(@class, "aei-trial-features")])').split())
        self.assertIn("4 usuarios · 12 GB · 6 h soporte/mes", features)

    def test_checkout_page_renders_three_step_wizard_and_summary(self):
        """GET /checkout renders the 3-step AEI onboarding wizard and TU SELECCIÓN summary in Bs."""
        response = self.url_open("/checkout?plan=starter&cycle=annual&mode=trial")
        self.assertEqual(response.status_code, 200)
        tree = html.fromstring(response.content)
        self.assertTrue(tree.xpath('//section[contains(@class, "aei-checkout-section")]'))
        text = " ".join(tree.text_content().split())
        for phrase in (
            "TU NUEVO ESPACIO DE TRABAJO",
            "Ya casi es tuyo.",
            "01 / TU CUENTA",
            "TU SELECCIÓN",
            "Plan Starter",
            "Bs 0,00",
        ):
            self.assertIn(phrase, text)
        self.assertEqual(len(tree.xpath('//button[@data-aei-password-toggle]')), 2)


