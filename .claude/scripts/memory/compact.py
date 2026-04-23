"""
compact.py — Weekly and monthly rollup summarization using Anthropic API.

Produces concise summaries of daily logs (weekly) and weekly summaries (monthly)
using claude-haiku-4-5-20251001 for cost efficiency.

CLI usage:
  python compact.py weekly [--vault PATH] [--date YYYY-MM-DD]
  python compact.py monthly [--vault PATH] [--date YYYY-MM-DD]

Default behavior:
  - weekly: summarizes last week (7 days ago to today)
  - monthly: summarizes last month
"""

import argparse
import sys
import warnings
from pathlib import Path
from datetime import date, timedelta, datetime

# Allow running as a script directly (not only as a module)
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    __package__ = "scripts.memory"

import anthropic


# ---------------------------------------------------------------------------
# ISO Week & Month Helpers
# ---------------------------------------------------------------------------

def _week_dates(d: date) -> list[date]:
    """Return Mon-Sun for the ISO week containing d."""
    monday = d - timedelta(days=d.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def _iso_week_label(d: date) -> str:
    """Return 'YYYY-Www' for ISO week containing d. E.g. '2026-W16'"""
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def _weeks_in_month(year: int, month: int) -> list[date]:
    """Return list of Mondays for all weeks overlapping target month.

    A week overlaps with the month if any day of the week falls in that month.
    """
    # First day of target month
    first_of_month = date(year, month, 1)

    # Last day of target month
    if month == 12:
        last_of_month = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_of_month = date(year, month + 1, 1) - timedelta(days=1)

    # Get Monday of the week containing the first day
    monday = first_of_month - timedelta(days=first_of_month.weekday())

    mondays = []
    current_monday = monday

    while current_monday <= last_of_month:
        # Check if any day of this week overlaps with the month
        week_end = current_monday + timedelta(days=6)
        if week_end >= first_of_month and current_monday <= last_of_month:
            mondays.append(current_monday)
        current_monday += timedelta(days=7)

    return mondays


# ---------------------------------------------------------------------------
# Weekly Rollup
# ---------------------------------------------------------------------------

def weekly_rollup(vault_root: Path, target_date: date | None = None) -> Path | None:
    """Generate weekly rollup for the ISO week containing target_date.

    Default: last week (today - 7 days).

    1. Collect daily logs: vault/daily/YYYY-MM-DD.md for each day Mon-Sun of target week
    2. Skip missing files gracefully (warn to stderr)
    3. If NO files found, print warning and return None
    4. Call Haiku to summarize
    5. Write to vault/weekly/YYYY-Www.md
    6. Return path to written file
    """
    vault_root = Path(vault_root)

    if target_date is None:
        target_date = date.today() - timedelta(days=7)

    # Get the week containing target_date
    week_dates = _week_dates(target_date)
    week_label = _iso_week_label(target_date)

    # Collect daily log files for the week
    combined_content = ""
    found_any = False

    for day in week_dates:
        daily_file = vault_root / "daily" / f"{day.isoformat()}.md"
        if daily_file.exists():
            try:
                with open(daily_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    combined_content += f"\n## {day.isoformat()}\n{content}\n"
                    found_any = True
            except Exception as e:
                warnings.warn(f"Failed to read {daily_file}: {e}", stacklevel=2)
        else:
            # Warn but don't fail
            warnings.warn(f"Daily log not found: {daily_file}", stacklevel=2)

    if not found_any:
        print(f"No daily logs found for week {week_label}", file=sys.stderr)
        return None

    # Call Haiku to summarize
    client = anthropic.Anthropic()

    system_prompt = "You are a personal knowledge assistant summarizing a week of activity logs."
    user_prompt = f"""Summarize this week's daily logs into bullet points organized by category:
- Coding & Projects
- Job Hunt & Networking
- Learning & AI Study
- Habits & Wellness
- Other

Daily logs:
{combined_content}

Keep each bullet concise. Output markdown."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        summary = response.content[0].text
    except Exception as e:
        print(f"Error calling Anthropic API: {e}", file=sys.stderr)
        return None

    # Write to vault/weekly/YYYY-Www.md
    weekly_dir = vault_root / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)

    output_file = weekly_dir / f"{week_label}.md"

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# Week {week_label}\n\n")
            f.write(summary)
        return output_file
    except Exception as e:
        print(f"Error writing to {output_file}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Monthly Rollup
# ---------------------------------------------------------------------------

def monthly_rollup(vault_root: Path, target_month: date | None = None) -> Path | None:
    """Generate monthly rollup for target_month.

    Default: last month (first day of current month - 1 day = last month).

    1. Collect weekly files: vault/weekly/YYYY-Www.md files for weeks overlapping target month
    2. Skip missing files gracefully
    3. If NO files found, print warning and return None
    4. Call Haiku to synthesize
    5. Write to vault/monthly/YYYY-MM.md
    6. Return path to written file
    """
    vault_root = Path(vault_root)

    if target_month is None:
        today = date.today()
        # Last month = first day of this month - 1 day
        first_of_this_month = date(today.year, today.month, 1)
        last_day_of_prev_month = first_of_this_month - timedelta(days=1)
        target_month = last_day_of_prev_month

    year = target_month.year
    month = target_month.month
    month_label = f"{year}-{month:02d}"

    # Get all weeks overlapping this month
    week_mondays = _weeks_in_month(year, month)

    # Collect weekly files
    combined_content = ""
    found_any = False

    for monday in week_mondays:
        week_label = _iso_week_label(monday)
        weekly_file = vault_root / "weekly" / f"{week_label}.md"

        if weekly_file.exists():
            try:
                with open(weekly_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    combined_content += f"\n## {week_label}\n{content}\n"
                    found_any = True
            except Exception as e:
                warnings.warn(f"Failed to read {weekly_file}: {e}", stacklevel=2)
        else:
            # Warn but don't fail
            warnings.warn(f"Weekly summary not found: {weekly_file}", stacklevel=2)

    if not found_any:
        print(f"No weekly summaries found for month {month_label}", file=sys.stderr)
        return None

    # Call Haiku to synthesize
    client = anthropic.Anthropic()

    system_prompt = "You are a personal knowledge assistant synthesizing monthly retrospectives."
    user_prompt = f"""Synthesize these weekly summaries into a monthly retrospective with:
## Wins
## Struggles
## Trends & Insights
## Next Month Focus

Weekly summaries:
{combined_content}

Output markdown."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        summary = response.content[0].text
    except Exception as e:
        print(f"Error calling Anthropic API: {e}", file=sys.stderr)
        return None

    # Write to vault/monthly/YYYY-MM.md
    monthly_dir = vault_root / "monthly"
    monthly_dir.mkdir(parents=True, exist_ok=True)

    output_file = monthly_dir / f"{month_label}.md"

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# Month {month_label}\n\n")
            f.write(summary)
        return output_file
    except Exception as e:
        print(f"Error writing to {output_file}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate weekly and monthly rollup summaries using Anthropic API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python compact.py weekly
  python compact.py weekly --date 2026-04-15
  python compact.py monthly
  python compact.py monthly --vault /path/to/vault
"""
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Weekly subcommand
    weekly_parser = subparsers.add_parser("weekly", help="Generate weekly rollup")
    weekly_parser.add_argument(
        "--vault",
        type=Path,
        default=Path.cwd() / "vault",
        help="Path to vault root (default: ./vault)"
    )
    weekly_parser.add_argument(
        "--date",
        type=str,
        help="Target date in YYYY-MM-DD format (default: 7 days ago)"
    )

    # Monthly subcommand
    monthly_parser = subparsers.add_parser("monthly", help="Generate monthly rollup")
    monthly_parser.add_argument(
        "--vault",
        type=Path,
        default=Path.cwd() / "vault",
        help="Path to vault root (default: ./vault)"
    )
    monthly_parser.add_argument(
        "--date",
        type=str,
        help="Target month in YYYY-MM-DD format (default: last month)"
    )

    args = parser.parse_args()

    # Parse target date if provided
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD.", file=sys.stderr)
            sys.exit(1)

    # Run the appropriate command
    if args.command == "weekly":
        result = weekly_rollup(args.vault, target_date)
        if result:
            print(f"Weekly rollup written to: {result}")
        sys.exit(0 if result else 1)

    elif args.command == "monthly":
        result = monthly_rollup(args.vault, target_date)
        if result:
            print(f"Monthly rollup written to: {result}")
        sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
