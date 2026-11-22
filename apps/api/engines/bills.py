"""Pure bill due-date calculation; no I/O and no mutation."""

from datetime import date


def next_due_date(due_day: int, today: date) -> date:
    """Return the next date with day due_day on or after today, rolling into next month if needed."""
    if isinstance(due_day, bool) or not isinstance(due_day, int) or not 1 <= due_day <= 28:
        raise ValueError("due_day must be an int between 1 and 28")

    if due_day >= today.day:
        return date(today.year, today.month, due_day)

    if today.month == 12:
        return date(today.year + 1, 1, due_day)
    return date(today.year, today.month + 1, due_day)
