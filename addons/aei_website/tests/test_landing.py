"""HTTP tests for the public landing page (spec: docs/specs/aei-website-landing.md)."""
import importlib.util
from pathlib import Path

from lxml import html

from odoo.modules import get_module_path
from odoo.tests import HttpCase, tagged

PLAN_XMLIDS = {
    "starter": "aei_website.product_saas_plan_starter",
    "pro": "aei_website.product_saas_plan_pro",
    "enterprise": "aei_website.product_saas_plan_enterprise",
}
PLAN_NAMES = {"starter": "Starter", "pro": "Pro", "enterprise": "Advanced"}
SAAS_CATEGORY = "odoo_k8s_saas.product_category_odoo_saas"


def _load_migration():
    path = Path(get_module_path("aei_website")) / "migrations" / "18.0.1.1.0" / "post-migrate.py"
    spec = importlib.util.spec_from_file_location("aei_website_post_migrate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install")
class TestLandingPlans(HttpCase):

    def _home(self):
        response = self.url_open("/")
        self.assertEqual(response.status_code, 200)
        return html.fromstring(response.content)

    def _card(self, tree, plan_key):
        cards = tree.xpath('//*[@data-plan-card="%s"]' % plan_key)
        self.assertEqual(len(cards), 1, "card for %s not rendered once" % plan_key)
        return cards[0]

    def _product(self, plan_key):
        return self.env.ref(PLAN_XMLIDS[plan_key])

    # E1
    def test_home_shows_three_plan_cards_with_design_names(self):
        tree = self._home()
        for key, name in PLAN_NAMES.items():
            title = self._card(tree, key).xpath('.//*[@data-plan-name]')[0].text_content()
            self.assertEqual(title.strip(), name)

    # E1 + E3
    def test_price_is_read_from_the_product(self):
        self._product("pro").list_price = 700
        price = self._card(self._home(), "pro").xpath('.//*[@data-plan-price]')[0]
        self.assertEqual(price.text_content().strip(), "700")

    def test_price_uses_dot_as_thousands_separator(self):
        self._product("enterprise").list_price = 1290
        price = self._card(self._home(), "enterprise").xpath('.//*[@data-plan-price]')[0]
        self.assertEqual(price.text_content().strip(), "1.290")

    # E1: capacities come from the subscription template, not from the template file
    def test_capacities_are_read_from_the_subscription_template(self):
        template = self._product("pro").subscription_template_id
        template.write({"included_users": 12, "storage_gi": 33, "support_hours_included": 7})
        card = self._card(self._home(), "pro")
        self.assertIn("12", card.xpath('.//*[@data-plan-users]')[0].text_content())
        self.assertIn("33", card.xpath('.//*[@data-plan-storage]')[0].text_content())
        self.assertIn("7", card.xpath('.//*[@data-plan-support]')[0].text_content())

    # E4
    def test_unpublished_plan_is_hidden_and_page_still_renders(self):
        self._product("pro").website_published = False
        tree = self._home()
        self.assertFalse(tree.xpath('//*[@data-plan-card="pro"]'))
        self.assertTrue(tree.xpath('//*[@data-plan-card="starter"]'))

    # E2: every plan has a trial form and a purchase form (see test_landing_offers)
    def test_plan_form_posts_to_native_cart_with_csrf(self):
        tree = self._home()
        for key in PLAN_NAMES:
            forms = self._card(tree, key).xpath('.//form[@action="/shop/cart/update"]')
            self.assertEqual(len(forms), 2, key)
            for form in forms:
                self.assertEqual(form.get("method").lower(), "post")
                csrf = form.xpath('.//input[@name="csrf_token"]/@value')
                self.assertTrue(csrf and csrf[0], "missing csrf token for %s" % key)
                product_id = form.xpath('.//input[@name="product_id"]/@value')[0]
                self.assertEqual(int(product_id), self._product(key).product_variant_id.id)

    # E8
    def test_plan_products_keep_the_provisioning_link(self):
        category = self.env.ref(SAAS_CATEGORY)
        for key in PLAN_NAMES:
            product = self._product(key)
            self.assertEqual(product.categ_id, category, key)
            self.assertTrue(product.subscribable, key)
            self.assertTrue(product.subscription_template_id, key)

    # D3: our own header and footer replace Odoo's on the homepage only
    def test_homepage_uses_own_header_and_footer(self):
        page = self.env.ref("website.homepage_page")
        self.assertFalse(page.header_visible)
        self.assertFalse(page.footer_visible)
        tree = self._home()
        self.assertTrue(tree.xpath('//header[contains(@class, "aei-site-header")]'))
        self.assertTrue(tree.xpath('//footer[contains(@class, "aei-footer")]'))

    # D3: Odoo's own header must be hidden in the rendered page, not only flagged
    def test_odoo_header_is_hidden_on_the_homepage(self):
        tree = self._home()
        odoo_header = tree.xpath('//header[@id="top"]')
        self.assertTrue(odoo_header)
        self.assertIn("d-none", odoo_header[0].get("class"))

    # D3: a website gets its own copy of the generic page; every '/' record is switched
    def test_every_homepage_record_is_switched_to_own_chrome(self):
        pages = self.env["website.page"].with_context(active_test=False).search([("url", "=", "/")])
        pages.write({"header_visible": True, "footer_visible": True})
        returned_ids = self.env["website.page"].aei_use_own_chrome_on_homepage()
        self.assertEqual(set(returned_ids), set(pages.ids))
        self.assertFalse(any(pages.mapped("header_visible")))
        self.assertFalse(any(pages.mapped("footer_visible")))

    # E1: the eight sections of the design that this phase ports
    def test_home_has_the_ported_sections(self):
        tree = self._home()
        for anchor in ("clientes", "procesos", "tu-empresa", "planes"):
            self.assertTrue(tree.xpath('//section[@id="%s"]' % anchor), anchor)
        self.assertTrue(tree.xpath('//section[contains(@class, "aei-hero")]'))
        self.assertTrue(tree.xpath('//section[contains(@class, "aei-final-cta")]'))
        self.assertEqual(len(tree.xpath("//details[not(ancestor::dialog)]")), 8)

    # Profile tabs: three tabs, three panels, only the first one visible
    def test_profile_tabs_render_all_panels_with_one_visible(self):
        tree = self._home()
        tabs = tree.xpath('//*[@role="tab"][@data-aei-profile]')
        panels = tree.xpath('//*[@role="tabpanel"]')
        self.assertEqual((len(tabs), len(panels)), (3, 3))
        self.assertEqual([t.get("aria-selected") for t in tabs], ["true", "false", "false"])
        self.assertEqual([p.get("hidden") is None for p in panels], [True, False, False])

    # Migration: placeholder plans become the approved ones; edited ones are left alone
    def test_migration_updates_only_placeholder_plans(self):
        migration = _load_migration()
        starter = self._product("starter")
        starter.write({"name": "Plan Inicial — Odoo 18 SaaS", "list_price": 199})
        pro = self._product("pro")
        pro.write({"name": "Mi plan propio", "list_price": 500})
        migration.apply_plan_updates(self.env)
        self.assertEqual((starter.name, starter.list_price), ("Starter", 349.0))
        self.assertEqual((pro.name, pro.list_price), ("Mi plan propio", 500.0))
