from __future__ import annotations

import json
import sys


def main() -> None:
    raw = sys.stdin.read()
    try:
        json.loads(raw)
    except json.JSONDecodeError:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
