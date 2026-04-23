import datetime
import os
import re
import sys
from pathlib import Path

try:
    import anthropic as _anthropic
except ImportError:
    _anthropic = None


def get_project_root() -> Path:
    return Path(__file__).parent.parent.parent.resolve()


def get_vault_path() -> Path:
    vault = get_project_root() / "vault"
    if not vault.exists():
        raise FileNotFoundError(f"Vault directory not found: {vault}")
    return vault


def get_today_daily_path() -> Path:
    date_str = datetime.date.today().isoformat()
    return get_vault_path() / "daily" / f"{date_str}.md"


def get_recent_daily_logs(n: int = 3) -> list[tuple[str, str]]:
    daily_dir = get_vault_path() / "daily"
    if not daily_dir.exists():
        return []

    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
    candidates = sorted(
        (f for f in daily_dir.iterdir() if pattern.match(f.name)),
        key=lambda f: f.name,
        reverse=True,
    )

    results = []
    for f in candidates:
        if len(results) >= n:
            break
        try:
            content = f.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if content:
            results.append((f.stem, content))
    return results


def truncate_to_tokens(text: str, max_chars: int = 8000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "[truncated]"


def extract_facts_with_haiku(text: str, extraction_prompt: str) -> str:
    if _anthropic is None:
        print("Warning: anthropic package is not installed; skipping fact extraction.", file=sys.stderr)
        return ""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("Warning: ANTHROPIC_API_KEY is not set; skipping fact extraction.", file=sys.stderr)
        return ""
    try:
        client = _anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system="You are a precise fact extractor. Extract only concrete facts, decisions, and insights. Be concise.",
            messages=[
                {"role": "user", "content": f"{extraction_prompt}\n\n---\n{text}"},
            ],
        )
        return message.content[0].text
    except Exception as exc:
        print(f"Warning: fact extraction failed: {exc}", file=sys.stderr)
        return ""


def append_to_daily_log(content: str, section_header: str = "## Claude Session Notes") -> None:
    daily_path = get_today_daily_path()
    date_str = datetime.date.today().isoformat()

    if not daily_path.exists():
        daily_path.parent.mkdir(parents=True, exist_ok=True)
        frontmatter = (
            f"---\ndate: {date_str}\ntags: [daily]\n---\n\n"
            f"# Daily Log — {date_str}\n\n"
        )
        daily_path.write_text(frontmatter, encoding="utf-8")

    existing = daily_path.read_text(encoding="utf-8")

    if f"\n{section_header}\n" in existing or existing.startswith(f"{section_header}\n"):
        daily_path.write_text(existing.rstrip() + f"\n\n{content}\n", encoding="utf-8")
    else:
        daily_path.write_text(
            existing.rstrip() + f"\n\n{section_header}\n\n{content}\n",
            encoding="utf-8",
        )


def find_session_jsonl() -> "Path | None":
    project_dir_env = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if project_dir_env:
        project_dir = Path(project_dir_env)
        if project_dir.exists():
            def _mtime_or_zero_local(f: Path) -> float:
                try:
                    return f.stat().st_mtime
                except OSError:
                    return 0.0

            jsonl_files = sorted(
                project_dir.glob("*.jsonl"),
                key=_mtime_or_zero_local,
                reverse=True,
            )
            if jsonl_files:
                return jsonl_files[0]

    claude_projects = Path.home() / ".claude" / "projects"
    if not claude_projects.exists():
        return None

    def _mtime_or_zero(f: Path) -> float:
        try:
            return f.stat().st_mtime
        except OSError:
            return 0.0

    all_jsonl = sorted(
        claude_projects.rglob("*.jsonl"),
        key=_mtime_or_zero,
        reverse=True,
    )
    if all_jsonl:
        return all_jsonl[0]

    return None


if __name__ == "__main__":
    print("project_root:", get_project_root())
    try:
        print("vault_path:  ", get_vault_path())
    except FileNotFoundError as e:
        print(f"vault_path:   ERROR — {e}")
    print("today_daily: ", get_today_daily_path())
    print("session_jsonl:", find_session_jsonl())
