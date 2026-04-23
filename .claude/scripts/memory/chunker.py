"""
chunker.py — Split markdown files into overlapping token-approximate chunks.

Token estimation: 1 token ≈ 4 chars
Target chunk size : ~400 tokens → 1600 chars
Overlap           : ~50 tokens  → 200 chars
"""

from pathlib import Path

TARGET_CHARS = 1600
OVERLAP_CHARS = 200

_HEADING_PREFIX = ("#",)


def _is_heading(line: str) -> bool:
    stripped = line.lstrip()
    if not stripped.startswith("#"):
        return False
    # Must be #, ##, or ### (not ####+ which we ignore for context tracking)
    rest = stripped.lstrip("#")
    return len(stripped) - len(rest) <= 3 and (rest == "" or rest.startswith(" "))


def _extract_heading_text(line: str) -> str:
    return line.lstrip().lstrip("#").strip()


def _buffer_char_count(lines: list) -> int:
    return sum(len(l) for l in lines)


def _trim_to_overlap(lines: list) -> list:
    """Return the trailing slice of lines whose total length <= OVERLAP_CHARS."""
    kept = []
    total = 0
    for line in reversed(lines):
        if total + len(line) > OVERLAP_CHARS:
            break
        kept.append(line)
        total += len(line)
    return list(reversed(kept))


def chunk_file(path: Path) -> list[dict]:
    """Chunk a markdown file. Returns list of {chunk_idx, content, heading} dicts."""
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        return []

    lines = text.splitlines(keepends=True)

    chunks: list[dict] = []
    buffer: list[str] = []
    current_heading: str = ""
    chunk_idx: int = 0

    def emit_chunk(buf: list[str], heading: str) -> list[str]:
        nonlocal chunk_idx
        content = "".join(buf)
        if content.strip():
            chunks.append(
                {
                    "chunk_idx": chunk_idx,
                    "content": content,
                    "heading": heading,
                }
            )
            chunk_idx += 1
        return _trim_to_overlap(buf)

    for line in lines:
        # Update heading context before deciding to emit
        if _is_heading(line):
            # If buffer is non-empty and we're at a heading boundary, emit first
            if buffer and _buffer_char_count(buffer) > 0:
                buffer = emit_chunk(buffer, current_heading)
            current_heading = _extract_heading_text(line)

        buffer.append(line)

        # Emit when buffer exceeds target
        if _buffer_char_count(buffer) >= TARGET_CHARS:
            buffer = emit_chunk(buffer, current_heading)

    # Emit whatever remains
    if buffer:
        emit_chunk(buffer, current_heading)

    return chunks
