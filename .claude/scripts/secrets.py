from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _find_project_root(start: Path) -> Path:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return start.resolve()


_PROJECT_ROOT = _find_project_root(Path(__file__))
_SECRETS_DIR = _PROJECT_ROOT / ".claude" / "data" / "secrets"


def _secrets_dir(project_root: Path | None) -> Path:
    root = project_root or _PROJECT_ROOT
    return root / ".claude" / "data" / "secrets"


def load_env(project_root: Path | None = None) -> dict[str, str]:
    """Load .env and return all key-value pairs. Never logs values."""
    root = project_root or _PROJECT_ROOT
    env_path = root / ".env"
    try:
        from dotenv import dotenv_values
        return dict(dotenv_values(env_path))
    except ImportError:
        pass
    # Fallback: manual parse
    result: dict[str, str] = {}
    if not env_path.exists():
        return result
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        result[key.strip()] = val.strip().strip('"').strip("'")
    return result


def get_secret(key: str, project_root: Path | None = None) -> str | None:
    """Return env var by key. Returns None if missing."""
    return load_env(project_root).get(key)


def token_path(service: str, project_root: Path | None = None) -> Path:
    """Return path to cached OAuth token file for service (e.g. 'gmail', 'gcal')."""
    return _secrets_dir(project_root) / f"{service}_token.json"


def secure_write_token(service: str, data: dict, project_root: Path | None = None) -> Path:
    """Write OAuth token JSON to .claude/data/secrets/<service>_token.json.

    On Windows, sets file to owner-only via icacls. Returns the path.
    """
    path = token_path(service, project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if sys.platform == "win32":
        try:
            import os
            username = os.environ.get("USERNAME", "")
            if username:
                # Remove inherited permissions, grant current user full control only
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:F"],
                    capture_output=True,
                    check=False,
                )
        except Exception:
            pass
    return path


def secure_read_token(service: str, project_root: Path | None = None) -> dict | None:
    """Read cached OAuth token JSON. Returns None if not found."""
    path = token_path(service, project_root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
