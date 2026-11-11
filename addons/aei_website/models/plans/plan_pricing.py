"""Pricing rules and number formats of the public plan cards.

Pure functions with no database access, so they are easy to test. The rules are the
ones of the published design: the annual period is twelve monthly payments with a
20% discount, and amounts use the Bolivian format (dot for thousands, comma for
decimals).
"""
from decimal import ROUND_HALF_UP, Decimal

# Rule of the published design. The internal wiring (later) should read it from settings.
ANNUAL_DISCOUNT = Decimal("0.20")
MONTHS_PER_YEAR = 12
CENTS = Decimal("0.01")


def _cents(value):
    """Round a Decimal to two decimals, half up (what a shopper expects on a price)."""
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def annual_amounts(monthly_price):
    """Return the annual amounts of a plan as Decimals.

    Keys: ``total`` (billed per year), ``saving`` (discount against twelve monthly
    payments) and ``monthly_equivalent`` (the total spread over twelve months).
    """
    base = _cents(Decimal(str(monthly_price)) * MONTHS_PER_YEAR)
    saving = _cents(base * ANNUAL_DISCOUNT)
    total = _cents(base - saving)
    return {
        "total": total,
        "saving": saving,
        "monthly_equivalent": _cents(total / MONTHS_PER_YEAR),
    }


def _bolivian(text):
    """Swap the separators of an English formatted number: 1,234.50 -> 1.234,50."""
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def format_money(amount):
    """Format an amount as Bolivianos with two decimals: Bs 3.350,40."""
    return "Bs " + _bolivian("{:,.2f}".format(amount))


def format_number(amount):
    """Format a number without decimals when it is whole, with two otherwise."""
    decimals = 2 if amount % 1 else 0
    return _bolivian("{:,.{}f}".format(amount, decimals))

