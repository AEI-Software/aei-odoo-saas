"""Unit tests of the plan pricing rules and Bolivian number formats (no database)."""
from decimal import Decimal

from odoo.tests import BaseCase, tagged

from odoo.addons.aei_website.models.plans.plan_pricing import (
    annual_amounts,
    format_money,
    format_number,
)


@tagged("post_install", "-at_install")
class TestPlanPricing(BaseCase):
    """Annual discount rule and number formats of the published design."""

    def test_annual_amounts_apply_twenty_percent_to_twelve_months(self):
        amounts = annual_amounts(349)
        self.assertEqual(amounts["saving"], Decimal("837.60"))
        self.assertEqual(amounts["total"], Decimal("3350.40"))
        self.assertEqual(amounts["monthly_equivalent"], Decimal("279.20"))

    def test_annual_amounts_for_the_top_plan(self):
        amounts = annual_amounts(1290)
        self.assertEqual(amounts["saving"], Decimal("3096.00"))
        self.assertEqual(amounts["total"], Decimal("12384.00"))

    def test_rounding_is_half_up(self):
        # 0.05 * 12 = 0.60; 20% = 0.12; total 0.48; per month 0.04
        self.assertEqual(annual_amounts("0.05")["monthly_equivalent"], Decimal("0.04"))

    def test_money_uses_dot_for_thousands_and_comma_for_decimals(self):
        self.assertEqual(format_money(Decimal("3350.4")), "Bs 3.350,40")
        self.assertEqual(format_money(Decimal("12384")), "Bs 12.384,00")
        self.assertEqual(format_money(Decimal("837.6")), "Bs 837,60")

    def test_number_drops_decimals_only_when_whole(self):
        self.assertEqual(format_number(Decimal("279.20")), "279,20")
        self.assertEqual(format_number(Decimal("1032.00")), "1.032")
        self.assertEqual(format_number(Decimal("349")), "349")

