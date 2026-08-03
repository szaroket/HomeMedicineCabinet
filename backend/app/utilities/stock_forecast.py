"""Helpers for projecting how long a cabinet entry's stock will last."""

import logging

logger = logging.getLogger("app.utilities.stock_forecast")


def days_of_stock_remaining(quantity_tablets: float, tablets_per_day: float) -> int:
    """Estimate how many whole days of stock remain at the current dosage.

    Args:
        quantity_tablets (float): Tablets currently held for the entry.
        tablets_per_day (float): Tablets consumed per day by the schedule.

    Returns:
        int: Whole days of stock remaining, floored at zero.
    """
    import math

    if tablets_per_day <= 0:
        return 0

    d = quantity_tablets / tablets_per_day
    n = math.floor(d)
    return max(n, 0)
