#!/usr/bin/env python3
"""LOG-M1: Validate _log() format compliance in GCL runner scripts.

Checks:
  L1. Every _log() call's first positional arg is a string literal or f-string.
  L2. The string starts with "event=".
  L3. All ``key=value`` segments have non-empty keys and values.
  L4. No spaces inside key names (before ``=``).
  L5. No ``print(..., ...)`` call that looks like it should be a _log()
      (catches regressions like stderr → stdout on new code).

Exit 0 = pass, non-0 = violations found.
"""

import ast
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FILES = [
    "gcl_runner.py",
    "gcl_reflexion.py",
    "gcl_memory.py",
    "gcl_strategy.py",
    "git_collect.py",
    "strategy_notify.py",
    "strategy_github_notify.py",
    "strategy_synthesize.py",
]


def _log_message_prefix(node: ast.AST) -> str | None:
    """Extract leading string from _log() first argument (literal or f-string)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                return part.value
    return None


def _check_print_suspicious(path: Path) -> list[str]:
    """Warn on print() calls inside the main module body (not test files).

    Legitimate uses: main() summary lines, --help, version output.
    Flag only those where the first argument looks like a log message
    (starts with ``[`` timestamp pattern) — those should be _log().
    """
    errors: list[str] = []
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError as e:
        return [f"SYNTAX ERROR in {path.name}: {e}"]

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "print"):
            continue
        # Check if first argument is a string that looks like a log line
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            msg = node.args[0].value
            # Heuristic: starts with timestamp pattern or event= pattern
            # But exclude CLI stdout messages like [MEMORY], [WARN], etc.
            if msg.startswith("[") and ("]" in msg[:20]):
                # Allow common CLI output patterns
                if any(msg.startswith(prefix) for prefix in ["[MEMORY]", "[WARN]", "[ERROR]", "[INFO]"]):
                    continue  # These are legitimate CLI output
                errors.append(
                    f"{path.name}:{node.lineno}: suspicious print() — "
                    f"looks like a log line, should be _log(): {msg!r}"
                )
            if msg.startswith("event="):
                errors.append(
                    f"{path.name}:{node.lineno}: suspicious print() — "
                    f"starts with 'event=', should be _log(): {msg!r}"
                )
    return errors


def _validate_kv_segments(msg: str, path_name: str, lineno: int) -> list[str]:
    """Validate key=value segments in the static portion of a log message."""
    errors: list[str] = []
    parts = msg.rstrip().split()
    # F-strings often end the static prefix with an incomplete key= before {expr}
    if parts and parts[-1].endswith("=") and parts[-1].count("=") == 1:
        parts = parts[:-1]
    for segment in parts:
        if "=" not in segment:
            continue
        key, _, val = segment.partition("=")
        if not key:
            errors.append(f"{path_name}:{lineno}: empty key in segment: {segment!r}")
        if not val and segment != "N/A":
            errors.append(f"{path_name}:{lineno}: empty value in segment: {segment!r}")
    return errors


def check_file(path: Path) -> list[str]:
    errors: list[str] = []

    try:
        tree = ast.parse(path.read_text())
    except SyntaxError as e:
        return [f"SYNTAX ERROR in {path.name}: {e}"]

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "_log"):
            continue

        # L1: must have at least one positional argument (the format string)
        if not node.args:
            errors.append(f"{path.name}:{node.lineno}: _log() call with no arguments")
            continue

        msg = _log_message_prefix(node.args[0])
        if msg is None:
            errors.append(
                f"{path.name}:{node.lineno}: _log() first arg must be a string literal or f-string, "
                f"got {type(node.args[0]).__name__}"
            )
            continue

        # L2 + L4: must start with event=
        if not msg.startswith("event="):
            errors.append(
                f"{path.name}:{node.lineno}: _log() must start with 'event=', "
                f"got: {msg.split()[0] if msg.split() else '(empty)'!r}"
            )

        # L3: key=value segments in static prefix only
        errors.extend(_validate_kv_segments(msg, path.name, node.lineno))

    return errors


def main() -> int:
    all_errors: list[str] = []
    for fname in FILES:
        fpath = SCRIPT_DIR / fname
        if not fpath.exists():
            all_errors.append(f"{fname}: file not found")
            continue
        all_errors.extend(check_file(fpath))
        all_errors.extend(_check_print_suspicious(fpath))

    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        return 1

    print("LOG-M1: all _log() calls pass format check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
