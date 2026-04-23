"""Stdlib-only date-range parser for natural language time queries."""

import re
import calendar
import datetime


def parse_date_range(expr: str) -> tuple[float, float]:
    """Parse a date expression and return (start_ts, end_ts) as Unix timestamps.

    Supported expressions (case-insensitive):
    - "today" → start of today (00:00:00 UTC) to now
    - "yesterday" → start/end of yesterday (full day, UTC)
    - "this week" → Monday of current week (00:00:00) to now
    - "last week" → Monday–Sunday of previous week (full week)
    - "this month" → 1st of current month (00:00:00) to now
    - "last month" → full previous calendar month
    - "last N days" / "past N days" → N days ago to now (N is integer 1-365)
    - ISO date "YYYY-MM-DD" → that full day (00:00:00 to 23:59:59)
    - ISO range "YYYY-MM-DD to YYYY-MM-DD" → inclusive range

    Returns (0.0, float('inf')) for unrecognized expressions — no filter.
    All times in UTC.
    """
    expr = expr.strip().lower()
    now = datetime.datetime.utcnow()

    # Handle "last N days" / "past N days"
    match = re.match(r'^(?:last|past)\s+(\d+)\s+days?$', expr)
    if match:
        n = int(match.group(1))
        if 1 <= n <= 365:
            start = now - datetime.timedelta(days=n)
            start_ts = _to_timestamp(start.replace(hour=0, minute=0, second=0, microsecond=0))
            end_ts = _to_timestamp(now)
            return (start_ts, end_ts)

    # Handle ISO range "YYYY-MM-DD to YYYY-MM-DD"
    match = re.match(r'^(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})$', expr)
    if match:
        try:
            start_date = datetime.datetime.strptime(match.group(1), "%Y-%m-%d")
            end_date = datetime.datetime.strptime(match.group(2), "%Y-%m-%d")
            start_ts = _to_timestamp(start_date)
            # End of day is 23:59:59
            end_ts = _to_timestamp(end_date.replace(hour=23, minute=59, second=59))
            return (start_ts, end_ts)
        except ValueError:
            return (0.0, float('inf'))

    # Handle ISO date "YYYY-MM-DD"
    if re.match(r'^\d{4}-\d{2}-\d{2}$', expr):
        try:
            dt = datetime.datetime.strptime(expr, "%Y-%m-%d")
            start_ts = _to_timestamp(dt)
            end_ts = _to_timestamp(dt.replace(hour=23, minute=59, second=59))
            return (start_ts, end_ts)
        except ValueError:
            return (0.0, float('inf'))

    # Handle "today"
    if expr == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_ts = _to_timestamp(start)
        end_ts = _to_timestamp(now)
        return (start_ts, end_ts)

    # Handle "yesterday"
    if expr == "yesterday":
        yesterday = now - datetime.timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = yesterday.replace(hour=23, minute=59, second=59)
        start_ts = _to_timestamp(start)
        end_ts = _to_timestamp(end)
        return (start_ts, end_ts)

    # Handle "this week" (Monday of current week to now)
    if expr == "this week":
        # Monday is weekday 0
        days_since_monday = now.weekday()
        monday = now - datetime.timedelta(days=days_since_monday)
        start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        start_ts = _to_timestamp(start)
        end_ts = _to_timestamp(now)
        return (start_ts, end_ts)

    # Handle "last week" (full previous week, Monday to Sunday)
    if expr == "last week":
        # Current Monday
        days_since_monday = now.weekday()
        this_monday = now - datetime.timedelta(days=days_since_monday)
        # Previous Monday
        last_monday = this_monday - datetime.timedelta(days=7)
        start = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        # Last Sunday (end of day)
        last_sunday = last_monday + datetime.timedelta(days=6)
        end = last_sunday.replace(hour=23, minute=59, second=59)
        start_ts = _to_timestamp(start)
        end_ts = _to_timestamp(end)
        return (start_ts, end_ts)

    # Handle "this month"
    if expr == "this month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_ts = _to_timestamp(start)
        end_ts = _to_timestamp(now)
        return (start_ts, end_ts)

    # Handle "last month"
    if expr == "last month":
        # First day of this month
        first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Last day of previous month (one day before first of this month)
        last_day_prev = first_of_this_month - datetime.timedelta(days=1)
        # First day of previous month
        first_of_prev = last_day_prev.replace(day=1)
        start_ts = _to_timestamp(first_of_prev)
        # End of last day of previous month
        end = last_day_prev.replace(hour=23, minute=59, second=59)
        end_ts = _to_timestamp(end)
        return (start_ts, end_ts)

    # Unknown expression
    return (0.0, float('inf'))


def _to_timestamp(dt: datetime.datetime) -> float:
    """Convert a UTC datetime to Unix timestamp."""
    return calendar.timegm(dt.timetuple()) + dt.microsecond / 1e6


def apply_temporal_filter(chunks: list[dict], start_ts: float, end_ts: float) -> list[dict]:
    """Filter chunk dicts by created_at timestamp.

    Includes chunks where created_at is between start_ts and end_ts inclusive.
    """
    filtered = []
    for chunk in chunks:
        created_at = chunk.get("created_at")
        if created_at is not None:
            if start_ts <= created_at <= end_ts:
                filtered.append(chunk)
    return filtered


if __name__ == "__main__":
    for expr in ["today", "yesterday", "this week", "last week", "this month", "last month",
                 "last 7 days", "past 3 days", "2026-04-01 to 2026-04-10", "2026-04-15", "unknown stuff"]:
        start, end = parse_date_range(expr)
        start_s = datetime.datetime.utcfromtimestamp(start).isoformat() if start > 0 else "0"
        end_s = datetime.datetime.utcfromtimestamp(end).isoformat() if end < float('inf') else "inf"
        print(f"{expr!r:35} -> {start_s} to {end_s}")
