"""Glob helpers for directory dataset scanning.

pathlib / fnmatch do not expand bash-style braces like ``**/*.{csv,txt}``.
AutoDetect / LLM profiles frequently emit that form; expand before scanning.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

_BRACE_RE = re.compile(r"\{([^{}]+)\}")


def expand_brace_globs(pattern: str) -> List[str]:
    """Expand one level of ``{a,b,c}`` (recursively) into concrete glob patterns."""
    pattern = (pattern or "**/*").strip() or "**/*"
    if "{" not in pattern:
        return [pattern]
    match = _BRACE_RE.search(pattern)
    if not match:
        return [pattern]
    options = [opt.strip() for opt in match.group(1).split(",") if opt.strip()]
    if not options:
        return [pattern]
    prefix = pattern[: match.start()]
    suffix = pattern[match.end() :]
    out: List[str] = []
    for opt in options:
        out.extend(expand_brace_globs(f"{prefix}{opt}{suffix}"))
    # de-dupe preserve order
    seen: set[str] = set()
    unique: List[str] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def normalize_extensions(extensions: Optional[Sequence[str]]) -> List[str]:
    if not extensions:
        return []
    out: List[str] = []
    for ext in extensions:
        e = str(ext or "").strip().lower()
        if not e:
            continue
        if not e.startswith("."):
            e = f".{e}"
        if e not in out:
            out.append(e)
    return out


def glob_files(
    root_dir: Path,
    pattern: str = "**/*",
    extensions: Optional[Sequence[str]] = None,
    exclude_patterns: Optional[Iterable[str]] = None,
    *,
    files_only: bool = True,
) -> List[Path]:
    """Scan ``root_dir`` with brace-aware globs and optional extension filters."""
    root_dir = Path(root_dir)
    exts = set(normalize_extensions(extensions))
    exclude = list(exclude_patterns or [])
    found: List[Path] = []
    seen: set[str] = set()

    for pat in expand_brace_globs(pattern):
        try:
            matches = root_dir.glob(pat)
        except Exception:
            continue
        for path in matches:
            if files_only and not path.is_file():
                continue
            key = str(path.resolve()) if path.exists() else str(path)
            if key in seen:
                continue
            if exts and path.suffix.lower() not in exts:
                continue
            name = path.name
            if any(re.search(rx, name) for rx in exclude):
                continue
            seen.add(key)
            found.append(path)

    return sorted(found)
