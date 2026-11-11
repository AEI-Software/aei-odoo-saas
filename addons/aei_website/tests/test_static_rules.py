"""Static rules for the module's front-end code (spec scenarios E7 and E9)."""
import re
from pathlib import Path

from odoo.modules import get_module_path
from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase, tagged

# Bootstrap class names we must not use. Tokens are compared one by one, so
# "aei-btn" is fine and "btn" is not.
BOOTSTRAP_EXACT = {
    "container", "container-fluid", "row", "btn", "alert", "badge", "card", "navbar",
    "collapse", "modal", "dropdown", "visually-hidden", "visually-hidden-focusable",
    "text-center", "text-muted", "w-100", "h-100", "position-absolute", "rounded-0",
    "start-0", "img-fluid", "lead", "display-1", "display-4",
}
BOOTSTRAP_PATTERNS = [
    r"col(-(sm|md|lg|xl|xxl))?(-\d+)?",
    r"btn-.+",
    r"d-(none|block|flex|inline.*|grid)(-.+)?",
    r"[mp][trblxy]?-(auto|\d)",
    r"g[xy]?-\d",
    r"gap-\d",
    r"align-(items|self|content)-.+",
    r"justify-content-.+",
    r"text-(start|end|center|muted|white|primary|secondary|uppercase|bold)",
    r"fw-.+",
    r"fs-\d",
    r"bg-(primary|secondary|light|dark|white|success|danger|info|warning)",
    r"flex-.+",
    r"rounded(-.+)?",
    r"shadow(-.+)?",
    r"border(-.+)?",
]
# Odoo ships the icon font, so "fa" is allowed. oe_structure is the Odoo hook
# that lets the website editor drop snippets in a block.
ALLOWED_FOREIGN = [r"fa", r"fa-.*", r"oe_structure"]
FORBIDDEN_DOM = re.compile(r"\b(innerHTML|outerHTML|insertAdjacentHTML|document\.write)\b")


def _module_dir():
    return Path(get_module_path("aei_website"))


def _files(pattern):
    return sorted(p for p in _module_dir().glob(pattern) if p.is_file())


def _class_tokens_in_templates():
    for path in _files("views/**/*.xml"):
        for value in re.findall(r'\bclass="([^"]*)"', path.read_text(encoding="utf-8")):
            value = re.sub(r"#\{.*?\}", " ", value)  # drop QWeb expressions, keep literal classes
            for token in value.split():
                yield path.name, token


def _is_bootstrap(token):
    return token in BOOTSTRAP_EXACT or any(re.fullmatch(p, token) for p in BOOTSTRAP_PATTERNS)


def _strip_js_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$|\s//[^\n]*$", "", text)


@tagged("post_install", "-at_install")
class TestStaticRules(TransactionCase):

    def test_templates_use_no_bootstrap_class(self):
        found = {(n, t) for n, t in _class_tokens_in_templates() if _is_bootstrap(t)}
        self.assertFalse(found, "Bootstrap classes in templates: %s" % sorted(found))

    def test_template_classes_are_prefixed(self):
        foreign = {
            (n, t) for n, t in _class_tokens_in_templates()
            if not t.startswith("aei-") and not any(re.fullmatch(p, t) for p in ALLOWED_FOREIGN)
        }
        self.assertFalse(foreign, "classes without the aei- prefix: %s" % sorted(foreign))

    def test_stylesheets_define_only_prefixed_classes(self):
        selector = re.compile(r"\.([A-Za-z_][\w-]*)")
        offenders = set()
        for path in _files("static/src/css/**/*.css"):
            text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
            text = re.sub(r"url\([^)]*\)", "", text)
            for name in selector.findall(text):
                if re.fullmatch(r"\d+", name):
                    continue
                if name.startswith("aei-") or any(re.fullmatch(p, name) for p in ALLOWED_FOREIGN):
                    continue
                offenders.add((path.name, name))
        self.assertFalse(offenders, "CSS classes without the aei- prefix: %s" % sorted(offenders))

    def test_stylesheets_have_no_bare_global_rules(self):
        bare = re.compile(r"(^|})\s*(html|body|\*|h[1-6]|p|a|ul|ol|li|img|button|input)\b[^{]*\{")
        offenders = []
        for path in _files("static/src/css/**/*.css"):
            text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
            if bare.search(text):
                offenders.append(path.name)
        self.assertFalse(offenders, "global element rules in: %s" % offenders)

    def test_every_stylesheet_is_loaded_and_refinements_come_after_foundation(self):
        loaded = get_manifest("aei_website")["assets"]["web.assets_frontend"]
        prefix = "aei_website/static/src/css/"
        loaded_css = [path[len(prefix):] for path in loaded if path.startswith(prefix)]
        on_disk = {p.relative_to(_module_dir() / "static/src/css").as_posix() for p in _files("static/src/css/**/*.css")}
        self.assertEqual(set(loaded_css), on_disk, "a stylesheet is not listed in the manifest (or the reverse)")
        last_foundation = max(i for i, n in enumerate(loaded_css) if n.startswith("foundation/"))
        first_refinement = min(i for i, n in enumerate(loaded_css) if n.startswith("refinements/"))
        self.assertLess(last_foundation, first_refinement)

    def test_javascript_uses_no_unsafe_dom_calls(self):
        offenders = [
            p.name for p in _files("static/src/js/**/*.js")
            if FORBIDDEN_DOM.search(_strip_js_comments(p.read_text(encoding="utf-8")))
        ]
        self.assertFalse(offenders, "unsafe DOM calls in: %s" % offenders)
