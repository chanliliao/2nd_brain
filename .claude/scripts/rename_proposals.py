"""One-time script: assign IDs to existing proposals and rename to YYYY-MM-DD_type_NNN.md."""
from __future__ import annotations
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
VAULT = ROOT / "vault"


def _parse_fm(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return {}, raw
    end = raw.index("---", 3)
    return yaml.safe_load(raw[3:end]) or {}, raw[end + 3:].strip()


def _inject_id(path: Path, new_id: int) -> None:
    raw = path.read_text(encoding="utf-8")
    # Insert after opening ---
    raw = re.sub(r"^---\n", f"---\nid: {new_id}\n", raw, count=1)
    path.write_text(raw, encoding="utf-8")


def main() -> None:
    # Collect all proposal files
    files = []
    for folder in ("proposals", "approved", "rejected"):
        d = VAULT / "drafts" / folder
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            try:
                fm, _ = _parse_fm(f)
            except Exception:
                continue
            fid = fm.get("id")
            ftype = fm.get("type", "unknown")
            proposed_at = str(fm.get("proposed_at", ""))
            try:
                dt = datetime.fromisoformat(proposed_at.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = f.name[:10]
            files.append({"path": f, "id": fid, "type": ftype, "date": date_str})

    # Sort so id assignment is deterministic (by date + original name)
    files.sort(key=lambda x: (x["date"], x["path"].name))

    # Find max existing id
    max_id = max((x["id"] for x in files if x["id"] is not None), default=0)

    # Assign missing ids
    for f in files:
        if f["id"] is None:
            max_id += 1
            f["id"] = max_id
            _inject_id(f["path"], max_id)
            print(f"  Assigned id {max_id}: {f['path'].name}")

    # Rename to YYYY-MM-DD_type_NNN.md
    for f in files:
        new_name = f"{f['date']}_{f['type']}_{f['id']:03d}.md"
        new_path = f["path"].parent / new_name
        if new_path == f["path"]:
            print(f"  OK (already named): {new_name}")
            continue
        if new_path.exists():
            print(f"  SKIP (collision): {new_name}")
            continue
        f["path"].rename(new_path)
        print(f"  Renamed: {f['path'].name} -> {new_name}")

    print("Done.")


if __name__ == "__main__":
    main()
