"""Single source of truth for FP57 window arithmetic and the prescription charge.

Imported by both scripts/generate_synthetic_data.py and the Decision/Gather
nodes, so synthetic data and live decisions cannot drift apart.
"""
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta

DEFAULT_WINDOW_MONTHS = 3
DEFAULT_WINDOW_DAYS_OFFSET = -1

# Verify against the NHSBSA prescription charge page before publishing.
# £9.90 was the rate from 1 May 2024 and held for 2025/26; if a later uplift
# has landed, this constant is wrong. It is server-side only — never taken
# from request input.
PRESCRIPTION_CHARGE = Decimal("9.90")

# In-scope exemption categories (PPC and HC3 are out of scope by design).
IN_SCOPE_CATEGORIES = ("HC2", "MATERNITY", "AGE", "MEDICAL")


def fp57_window_end(
    charge_paid_date: date,
    window_months: int = DEFAULT_WINDOW_MONTHS,
    window_days_offset: int = DEFAULT_WINDOW_DAYS_OFFSET,
) -> date:
    """Last day a refund claim may be submitted: 3 months less a day by default."""
    return charge_paid_date + relativedelta(months=window_months) + timedelta(days=window_days_offset)
