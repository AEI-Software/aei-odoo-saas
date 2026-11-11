"""Plan and module detail dialogs of the home page, and the catalog behind them."""
from lxml import html

from odoo.tests import HttpCase, tagged, TransactionCase

PLAN_LEVELS = {"starter": 0, "pro": 1, "enterprise": 2}
FEATURE_MODULES = ("sales", "banking", "inventory", "projects", "manufacturing", "continuity")


@tagged("post_install", "-at_install")
class TestModuleCatalog(TransactionCase):
    """The module catalog loaded from data/catalog/modules.json."""

    def setUp(self):
        super().setUp()
        self.catalog = self.env["aei.website.catalog"]

    def test_catalog_has_the_fifteen_modules_of_the_design(self):
        modules = self.catalog.modules()
        self.assertEqual(len(modules), 15)
        self.assertEqual({m["level"] for m in modules}, {0, 1, 2})

    def test_report_count_grows_with_the_plan_level(self):
        self.assertEqual(self.catalog.report_count(0), 7)
        self.assertEqual(self.catalog.report_count(1), 15)
        self.assertEqual(self.catalog.report_count(2), 15)

    def test_scope_label_names_the_first_plan_that_has_it(self):
        self.assertEqual(self.catalog.scope_label(0), "En todos los planes")
        self.assertEqual(self.catalog.scope_label(1), "Desde Pro")
        self.assertEqual(self.catalog.scope_label(2), "En Advanced")

    def test_extras_are_filtered_by_level(self):
        sales = self.catalog.module("sales")
        self.assertEqual(self.catalog.visible_extras(sales, 0), [])
        self.assertEqual(len(self.catalog.visible_extras(sales, 1)), 1)
        self.assertEqual(len(self.catalog.visible_extras(sales, None)), 1)


@tagged("post_install", "-at_install")
class TestLandingDialogs(HttpCase):
    """Detail dialogs rendered by the server; JavaScript only opens and closes them."""

    def _home(self):
        return html.fromstring(self.url_open("/").content)

    def _dialog(self, tree, dialog_id):
        found = tree.xpath('//dialog[@id="%s"]' % dialog_id)
        self.assertEqual(len(found), 1, dialog_id)
        return found[0]

    def test_plan_dialog_lists_the_modules_up_to_its_level(self):
        modules = self.env["aei.website.catalog"].modules()
        tree = self._home()
        for key, level in PLAN_LEVELS.items():
            dialog = self._dialog(tree, "aei-plan-dialog-" + key)
            expected = len([m for m in modules if m["level"] <= level])
            self.assertEqual(len(dialog.xpath(".//details")), expected, key)

    def test_manufacturing_is_only_in_the_advanced_dialog(self):
        tree = self._home()
        self.assertNotIn("Fabricación básica", self._dialog(tree, "aei-plan-dialog-pro").text_content())
        self.assertIn("Fabricación básica", self._dialog(tree, "aei-plan-dialog-enterprise").text_content())

    def test_plan_dialog_summarizes_price_and_capacities(self):
        text = " ".join(self._dialog(self._home(), "aei-plan-dialog-starter").text_content().split())
        self.assertIn("Alcance de Starter", text)
        self.assertIn("Bs 349 / mes", text)
        self.assertIn("3 usuarios", text)
        self.assertIn("Una empresa por suscripción.", text)

    def test_every_feature_card_opens_its_module_dialog(self):
        tree = self._home()
        for module_id in FEATURE_MODULES:
            self.assertTrue(tree.xpath('//button[@data-aei-module-details="%s"]' % module_id), module_id)
            self._dialog(tree, "aei-module-dialog-" + module_id)

    def test_sales_dialog_shows_the_invoice_badge_and_all_processes(self):
        dialog = self._dialog(self._home(), "aei-module-dialog-sales")
        self.assertTrue(dialog.xpath('.//*[contains(@class, "aei-invoice-badge")]'))
        self.assertEqual(len(dialog.xpath('.//ul[contains(@class, "aei-processes")]/li')), 5)

    def test_dialogs_are_closed_and_labelled(self):
        for dialog in self._home().xpath("//dialog"):
            self.assertIsNone(dialog.get("open"))
            self.assertTrue(dialog.get("aria-labelledby"))
            self.assertTrue(dialog.xpath('.//button[@data-aei-dialog-close]'))

