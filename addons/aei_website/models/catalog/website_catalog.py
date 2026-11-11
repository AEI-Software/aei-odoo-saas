"""Module catalog of the public site, read from data/catalog/modules.json.

The home page dialogs and the pricing comparison draw from this one source, so a
process is written once. Plan levels order the plans: a plan includes every module
whose level is lower than or equal to its own.
"""
import json

from odoo import api, models, tools
from odoo.tools import file_open

CATALOG_PATH = "aei_website/data/catalog/modules.json"
# Technical plan key -> level. "enterprise" is the plan the site shows as "Advanced".
PLAN_LEVELS = {"starter": 0, "pro": 1, "enterprise": 2}
# Label of the first plan that includes something of a given level.
SCOPE_LABELS = ("En todos los planes", "Desde Pro", "En Advanced")
REPORTS_MODULE_ID = "reports"


class WebsiteCatalog(models.AbstractModel):
    """Read-only access to the module catalog. It has no table."""

    _name = "aei.website.catalog"
    _description = "Public website module catalog"

    @api.model
    @tools.ormcache()
    def modules(self):
        """Return every module of the catalog, in display order."""
        with file_open(CATALOG_PATH, "rb") as catalog_file:
            return json.load(catalog_file)

    @api.model
    def module(self, module_id):
        """Return one module by its id, or False when the id is unknown."""
        return next((m for m in self.modules() if m["id"] == module_id), False)

    @api.model
    def modules_up_to(self, level):
        """Return the modules a plan of the given level includes."""
        return [m for m in self.modules() if m["level"] <= level]

    @api.model
    def visible_extras(self, module, level):
        """Return the extra processes of a module that apply at a level.

        With level None every extra is returned, so a module dialog can show all
        of them together with the plan each one starts in.
        """
        return [x for x in module["extra"] if level is None or x["level"] <= level]

    @api.model
    def scope_label(self, level):
        """Return the label of the first plan that includes the given level."""
        return SCOPE_LABELS[level]

    @api.model
    def plan_level(self, plan_key):
        """Return the level of a plan from its technical key (0 when unknown)."""
        return PLAN_LEVELS.get(plan_key, 0)

    @api.model
    def report_count(self, level):
        """Count the reports a plan of the given level includes."""
        reports = self.module(REPORTS_MODULE_ID)
        return len(reports["processes"]) + len(self.visible_extras(reports, level))

