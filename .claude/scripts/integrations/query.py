"""Unified CLI entrypoint for all integrations.

Usage:
  python query.py gmail unread [--since YYYY-MM-DD]
  python query.py gmail thread THREAD_ID
  python query.py gmail auth
  python query.py github prs
  python query.py github issues
  python query.py github diff OWNER/REPO PR_NUMBER
  python query.py calendar upcoming [--hours N]
  python query.py calendar today
  python query.py help
"""
import sys
from integrations.registry import get, list_registered


def main(args: list[str]) -> None:
    """Dispatch to the correct integration CLI based on args[0].

    args[0]: integration name ("gmail", "github", "calendar")
    args[1:]: passed through to that integration's cli_dispatch()

    "calendar" maps to the "gcal" registry entry.
    "help" prints usage listing all registered integrations.
    No args: print usage.

    On unknown integration name: print error + usage, exit code 1.
    """
    if not args:
        _print_usage()
        return

    command = args[0]

    if command == "help":
        _print_usage()
        return

    # Map "calendar" CLI name to "gcal" registry entry
    registry_name = "gcal" if command == "calendar" else command

    # Get the integration module from registry
    integration = get(registry_name)
    if integration is None:
        print(f"Error: Unknown integration '{command}'")
        print()
        _print_usage()
        sys.exit(1)

    # Dispatch to the integration's cli_dispatch function with remaining args
    try:
        integration.cli_dispatch(args[1:])
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _print_usage() -> None:
    """Print the module docstring and list registered integrations."""
    print(__doc__)
    print("\nRegistered integrations:")
    registered = list_registered()
    for name in registered:
        alias = "calendar" if name == "gcal" else name
        print(f"  {alias}")


if __name__ == "__main__":
    main(sys.argv[1:])
