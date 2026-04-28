"""Unified CLI entrypoint for all integrations.

Usage:
  python query.py github prs
  python query.py github issues
  python query.py github diff OWNER/REPO PR_NUMBER
  python query.py help
"""
import sys
from integrations.registry import get, is_registered, list_registered


def main(args: list[str]) -> None:
    """Dispatch to the correct integration CLI based on args[0].

    args[0]: integration name ("github")
    args[1:]: passed through to that integration's cli_dispatch()

    "help" prints usage listing all registered integrations.
    No args: print usage.

    On unknown integration name: print error + usage, exit code 1.
    """
    if not args:
        _print_usage()
        return

    command = args[0]
    debug = "--debug" in args

    if command == "help":
        _print_usage()
        return

    if not is_registered(command):
        print(f"Error: Unknown integration '{command}'", file=sys.stderr)
        print()
        _print_usage()
        sys.exit(1)

    integration = get(command)
    if integration is None:
        print(
            f"Error: Integration '{command}' is registered but failed to load. "
            "Check that its dependencies are installed.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        integration.cli_dispatch(args[1:])
    except SystemExit:
        raise
    except Exception as e:
        if debug:
            raise
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _print_usage() -> None:
    """Print the module docstring and list registered integrations."""
    print(__doc__)
    print("\nRegistered integrations:")
    for name in list_registered():
        print(f"  {name}")


if __name__ == "__main__":
    main(sys.argv[1:])
