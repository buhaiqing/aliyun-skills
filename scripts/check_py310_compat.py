#!/usr/bin/env python3
"""
Scan committed Python for APIs that require > Python 3.10.

CI runs on 3.10 (see .github/workflows/ci.yml, pyproject.toml).
Run locally before push:

    python3 scripts/check_py310_compat.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (regex, human-readable fix hint)
FORBIDDEN: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bdatetime\.UTC\b"), "use datetime.timezone.utc"),
    (re.compile(r"\b_dt\.UTC\b"), "use _dt.timezone.utc"),
    (re.compile(r"\bimport\s+tomllib\b"), "tomllib is 3.11+; use tomli or avoid"),
    (re.compile(r"\bfrom\s+tomllib\b"), "tomllib is 3.11+; use tomli or avoid"),
    (re.compile(r"\bExceptionGroup\b"), "ExceptionGroup is 3.11+"),
    (re.compile(r"\btyping\.Self\b"), "typing.Self is 3.11+; use TypeVar or Protocol"),
]

SKIP_DIR_NAMES = {
    ".git",
    ".runtime",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
}

SKIP_REL_PATHS = {
    "scripts/check_py310_compat.py",  # contains pattern literals for documentation
}


def iter_py_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        out.append(path)
    return sorted(out)


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    hits: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        hits.append((0, f"<read error: {exc}>", ""))
        return hits
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for pattern, hint in FORBIDDEN:
            if pattern.search(line):
                hits.append((lineno, line.strip(), hint))
    return hits


def main() -> int:
    violations: list[tuple[Path, int, str, str]] = []
    for path in iter_py_files(REPO_ROOT):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in SKIP_REL_PATHS:
            continue
        for lineno, line, hint in scan_file(path):
            violations.append((path, lineno, line, hint))

    if not violations:
        print(f"OK: Python 3.10 compatibility scan passed ({len(iter_py_files(REPO_ROOT))} files)")
        return 0

    print("Python 3.10 compatibility violations (CI uses 3.10):\n")
    for path, lineno, line, hint in violations:
        rel = path.relative_to(REPO_ROOT)
        print(f"  {rel}:{lineno}: {line}")
        print(f"    → {hint}\n")
    print(f"FAILED: {len(violations)} violation(s). See pyproject.toml [tool.uv] python-version = \"3.10\"")
    return 1


if __name__ == "__main__":
    sys.exit(main())
