"""HTTP and static tests for Account (/web/login, /web/signup), Contact (/contactus), and Scroll Motion."""
from lxml import html

from odoo.modules import get_module_path
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestAccountAndContact(HttpCase):
    """Verify scenarios E10, E11, E12, and E13 from docs/specs/aei-website-account-contact-motion.md."""

    def _open_loopback(self, path, data=None, allow_redirects=True):
        """Run url_open and allow Secure session cookies over HttpCase loopback HTTP."""
        for cookie in self.opener.cookies:
            cookie.secure = False
        response = self.url_open(path, data=data, allow_redirects=allow_redirects)
        for cookie in self.opener.cookies:
            cookie.secure = False
        return response

    def _parse(self, path):
        """Open a public path, assert HTTP 200, and return its parsed HTML tree."""
        response = self._open_loopback(path)
        self.assertEqual(response.status_code, 200, f"Unexpected status for {path}")
        return html.fromstring(response.content)

    def _assert_aei_chrome_only(self, tree):
        """Assert AEI header/footer are rendered and Odoo's native header is hidden or absent."""
        self.assertTrue(tree.xpath('//header[contains(@class, "aei-site-header")]'))
        self.assertTrue(tree.xpath('//footer[contains(@class, "aei-footer")]'))
        odoo_header = tree.xpath('//header[@id="top"]')
        if odoo_header:
            self.assertIn("d-none", odoo_header[0].get("class", ""))

    def test_e10_login_page_renders_aei_account_design(self):
        """Verify /web/login renders the split AEI account design with real CSRF login form."""
        tree = self._parse("/web/login")
        self._assert_aei_chrome_only(tree)
        self.assertTrue(tree.xpath('//section[contains(@class, "aei-account-section")]'))
        intro_text = tree.xpath('string(//*[contains(@class, "aei-account-intro")])')
        self.assertIn("TU CUENTA AEI", intro_text)
        self.assertIn("Tu empresa.", intro_text)
        panel_text = tree.xpath('string(//*[contains(@class, "aei-auth-panel")])')
        self.assertIn("01 / TU CUENTA", panel_text)
        self.assertIn("Comienza por ti.", panel_text)
        self.assertNotIn("Acceso de demostración", tree.text_content())
        form = tree.xpath('//form[@action="/web/login"]')
        self.assertEqual(len(form), 1)
        self.assertTrue(form[0].xpath('.//input[@name="csrf_token"]/@value'))
        self.assertTrue(form[0].xpath('.//input[@name="login"]'))
        self.assertTrue(form[0].xpath('.//input[@name="password"]'))

    def test_e10_account_route_redirects_to_login(self):
        """Verify /account redirects visitors cleanly to /web/login."""
        resp = self.url_open("/account", allow_redirects=False)
        self.assertIn(resp.status_code, (301, 302, 303))
        self.assertIn("/web/login", resp.headers.get("Location", ""))

    def test_e11_signup_and_reset_password_render_aei_account_design(self):
        """Verify /web/signup and /web/reset_password share the AEI account shell and CSRF."""
        self.env["ir.config_parameter"].sudo().set_param("auth_signup.invitation_scope", "b2c")
        self.env["ir.config_parameter"].sudo().set_param("auth_signup.reset_password", "True")

        signup_tree = self._parse("/web/signup")
        self._assert_aei_chrome_only(signup_tree)
        self.assertTrue(signup_tree.xpath('//section[contains(@class, "aei-account-section")]'))
        self.assertTrue(signup_tree.xpath('//form//input[@name="csrf_token"]/@value'))

        reset_tree = self._parse("/web/reset_password")
        self._assert_aei_chrome_only(reset_tree)
        self.assertTrue(reset_tree.xpath('//section[contains(@class, "aei-account-section")]'))
        self.assertTrue(reset_tree.xpath('//form//input[@name="csrf_token"]/@value'))

    def test_e12_contactus_renders_aei_design_and_submits_with_csrf(self):
        """Verify /contactus renders AEI layout, validates CSRF/inputs, and creates mail.mail."""
        tree = self._parse("/contactus")
        self._assert_aei_chrome_only(tree)
        heading_text = tree.xpath('string(//section[contains(@class, "aei-page-heading")])')
        self.assertIn("CONVERSEMOS", heading_text)
        self.assertIn("Tu siguiente paso empieza aquí.", heading_text)
        aside_text = tree.xpath('string(//aside[contains(@class, "aei-contact-aside")])')
        self.assertIn("Santa Cruz", aside_text)
        self.assertIn("WhatsApp", aside_text)

        forms = tree.xpath('//form[@action="/contactus/submit"]')
        self.assertEqual(len(forms), 1)
        csrf_token = forms[0].xpath('.//input[@name="csrf_token"]/@value')[0]
        self.assertTrue(csrf_token)

        before_count = self.env["mail.mail"].sudo().search_count([])

        # Missing CSRF must be rejected
        no_csrf_resp = self._open_loopback(
            "/contactus/submit",
            data={
                "name": "Ronald Prueba",
                "email_from": "ronald@empresa.bo",
                "subject": "Consulta planes",
                "description": "Necesito información sobre el plan Pro.",
            },
        )
        self.assertIn(no_csrf_resp.status_code, (400, 403))
        self.assertEqual(self.env["mail.mail"].sudo().search_count([]), before_count)

        # Invalid email must return generic error and not create mail.mail
        bad_resp = self._open_loopback(
            "/contactus/submit",
            data={
                "csrf_token": csrf_token,
                "name": "Ronald Prueba",
                "email_from": "correo-invalido",
                "subject": "Consulta",
                "description": "Detalle",
            },
        )
        self.assertEqual(bad_resp.status_code, 200)
        self.assertIn("Revisa los datos ingresados", bad_resp.text)
        self.assertEqual(self.env["mail.mail"].sudo().search_count([]), before_count)

        # Valid submission creates mail.mail and lands on AEI-styled thank-you page
        ok_resp = self._open_loopback(
            "/contactus/submit",
            data={
                "csrf_token": csrf_token,
                "name": "Ronald Prueba",
                "phone": "+59170000000",
                "email_from": "ronald@empresa.bo",
                "company": "Empresa Demo SRL",
                "subject": "Consulta Plan Pro",
                "description": "Quisiera agendar una demostración para 10 usuarios.",
            },
        )
        self.assertEqual(ok_resp.status_code, 200)
        self.assertEqual(self.env["mail.mail"].sudo().search_count([]), before_count + 1)
        thanks_tree = html.fromstring(ok_resp.content)
        self._assert_aei_chrome_only(thanks_tree)
        self.assertIn("Recibimos tu mensaje", thanks_tree.text_content())

    def test_e13_bidirectional_scroll_motion_configured(self):
        """Verify bidirectional entrance/exit scroll classes exist across JS and public pages."""
        js_path = f"{get_module_path('aei_website')}/static/src/js/landing.js"
        with open(js_path, encoding="utf-8") as fh:
            js_source = fh.read()
        self.assertIn("aei-is-exiting", js_source)
        self.assertNotIn("unobserve(entry.target)", js_source)

        for route in ("/", "/web/login", "/contactus"):
            tree = self._parse(route)
            self.assertTrue(
                tree.xpath('//*[contains(@class, "aei-reveal")]'),
                f"Expected .aei-reveal elements on {route}",
            )

