#!/usr/bin/env python3
"""
scan_repair_coverage.py — Phase 1 of case-table self-evolution.

Scans the Layer-2 reflexion store for failure patterns whose ``error_code`` is
not handled by the product's ``skillopt_repair_error()`` case table, and emits:

  - One ``.sh.patch`` file per (skill, error_code) over the threshold.
  - A ``summary.json`` listing every suggestion for downstream consumers.

Phase 1 is **suggest-only**: nothing is written to any product overlay. A human
must review each ``*.sh.patch`` and copy the placeholder branch into the
matching ``harness-lib.sh`` by hand. Phase 2 (GitHub Issue dry-run) and
Phase 3 (weekly workflow) are out of scope.

USAGE
-----
    # Scan with default threshold 5 and write suggestions
    python3 scan_repair_coverage.py --threshold 5

    # Custom reflexion root / output dir
    python3 scan_repair_coverage.py \
        --reflexion-root .runtime/reflexion \
        --output-dir .runtime/suggestions \
        --threshold 10

    # Dry-run (preview to stdout, no files written)
    python3 scan_repair_coverage.py --dry-run

    # Show a single suggestion by its hash
    python3 scan_repair_coverage.py --show <hash>

EXIT CODES
----------
    0  CLEAN          no unmapped patterns above threshold
    1  EMITTED        at least one suggestion emitted
    2  ERROR          I/O or parse failure
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# Resolve sibling gcl_reflexion.py without requiring pip install.
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from gcl_reflexion import (  # noqa: E402
    REFLEXION_ROOT_DEFAULT,
    REFLEXION_STORE,
    _load_store,
    is_mapped_in_repair_table,
)

DEFAULT_THRESHOLD = 5
DEFAULT_OUTPUT_DIR = ".runtime/suggestions"


def _safe_filename(skill: str, code: str) -> str:
    raw = f"{skill}__{code}"
    return "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in raw)


def _pattern_hash(skill: str, code: str, command: str) -> str:
    h = hashlib.sha1()
    h.update(skill.encode())
    h.update(b"\x00")
    h.update(code.encode())
    h.update(b"\x00")
    h.update(command.encode())
    return h.hexdigest()[:12]


def _suggested_branch_block(skill: str, code: str, pattern: dict[str, Any]) -> str:
    """Build the placeholder case-branch snippet humans paste into harness-lib.sh."""
    message = (pattern.get("error") or code).split(":", 1)[-1].strip()[:120]
    command = pattern.get("command", "")[:200]
    count = pattern.get("count", 1)
    last_seen = pattern.get("last_seen", pattern.get("first_seen", "unknown"))
    first_seen = pattern.get("first_seen", "unknown")

    sample_cmd = command
    sample_line = ""
    if sample_cmd:
        sample_line = f"# Sample:     {sample_cmd}\n"

    return (
        f"# Suggested case-branch for skillopt_repair_error\n"
        f"# Skill:      {skill}\n"
        f"# Error code: {code}\n"
        f"# Message:    {message or '(none)'}\n"
        f"# First seen: {first_seen}\n"
        f"# Last seen:  {last_seen}\n"
        f"# Occurrences: {count}\n"
        f"{sample_line}"
        f"# Author hint (auto): no canonical repair strategy known —\n"
        f"#   choose from: retry-with-jitter (类比 Throttling),\n"
        f"#                 region-switch (类比 ResourceNotFound),\n"
        f"#                 quota-cleanup (类比 QuotaExceeded).\n"
        f"#\n"
        f"# 在 {skill}/scripts/harness-lib.sh 的 case \"$error_code\" in ... esac 之间追加:\n"
        f"#   {code})\n"
        f"#       # TODO: replace with real repair logic\n"
        f"#       sleep 5\n"
        f"#       skillopt_run_aliyun \"$product\" \"$action\" \"${{params[@]}}\"\n"
        f"#       ;;\n"
        f"#\n"
        f"# ★ Reviewer:请人工实现真实修复,不要直接合并 placeholder。\n"
    )


def collect_unmapped_patterns(
    reflexion_root: Path,
    threshold: int,
    skills_root: Path,
) -> list[dict[str, Any]]:
    """Return a list of summary dicts ready for emission.

    Each dict has: ``skill``, ``code``, ``count``, ``first_seen``,
    ``last_seen``, ``command``, ``hash``, ``pattern`` (full original entry).
    """
    store = _load_store(reflexion_root)
    out: list[dict[str, Any]] = []
    for pattern in store.get("cli_parameter", []):
        if not pattern.get("unmapped_in_repair"):
            continue
        if pattern.get("count", 0) < threshold:
            continue
        skill = pattern.get("skill", "")
        # error_code is the canonical key; fall back to parsing "error" if missing
        code = pattern.get("error_code") or (pattern.get("error", "").split(":", 1)[0].strip())
        if not skill or not code:
            continue
        # Re-verify coverage at scan time (in case overlay changed since extract).
        if is_mapped_in_repair_table(skill, code, skills_root=skills_root):
            continue
        h = _pattern_hash(skill, code, pattern.get("command", ""))
        out.append({
            "skill": skill,
            "code": code,
            "count": pattern.get("count", 0),
            "first_seen": pattern.get("first_seen"),
            "last_seen": pattern.get("last_seen"),
            "command": pattern.get("command", "")[:200],
            "hash": h,
            "pattern": pattern,
        })
    out.sort(key=lambda d: (-d["count"], d["skill"], d["code"]))
    return out


def emit_suggestions(
    items: list[dict[str, Any]],
    output_dir: Path,
) -> list[dict[str, Any]]:
    """Write one ``.sh.patch`` per item plus a ``summary.json``.

    Returns the list of summary dicts that were actually written (path included).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, Any]] = []
    for item in items:
        block = _suggested_branch_block(item["skill"], item["code"], item["pattern"])
        fname = f"repair-case-{_safe_filename(item['skill'], item['code'])}-{item['hash']}.sh.patch"
        path = output_dir / fname
        path.write_text(block, encoding="utf-8")
        written.append({**item, "patch_path": str(path)})
    summary_path = output_dir / "summary.json"
    serializable = [
        {k: v for k, v in item.items() if k != "pattern"} for item in written
    ]
    summary_path.write_text(
        json.dumps(serializable, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return written


def cmd_scan(args: argparse.Namespace) -> int:
    reflexion_root = Path(args.reflexion_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    skills_root = Path(args.skills_root).resolve() if args.skills_root else reflexion_root.parent

    if not (reflexion_root / REFLEXION_STORE).is_file():
        print(
            f"[ERROR] reflexion store not found at {reflexion_root / REFLEXION_STORE}",
            file=sys.stderr,
        )
        return 2

    items = collect_unmapped_patterns(reflexion_root, args.threshold, skills_root)
    if args.dry_run:
        print(f"[DRY-RUN] {len(items)} suggestions would be emitted (threshold={args.threshold})")
        for item in items:
            print(
                f"  - {item['skill']:<24} {item['code']:<32} "
                f"count={item['count']:<3} hash={item['hash']}"
            )
        return 0 if not items else 1

    written = emit_suggestions(items, output_dir)
    print(
        f"[OK] emitted {len(written)} suggestion(s) to {output_dir} "
        f"(threshold={args.threshold})"
    )
    for item in written:
        print(f"  - {item['patch_path']}")
    return 0 if not written else 1


def cmd_show(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    matches = list(output_dir.glob(f"repair-case-*-{args.hash}.sh.patch"))
    if not matches:
        print(f"[ERROR] no patch file with hash={args.hash} in {output_dir}", file=sys.stderr)
        return 2
    for path in matches:
        print(f"=== {path} ===")
        print(path.read_text(encoding="utf-8"))
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scan_repair_coverage.py",
        description="Phase 1 — scan reflexion store for unmapped case-table error codes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command", required=True)

    scan_p = sub.add_parser("scan", help="Scan reflexion store and emit suggestions")
    scan_p.add_argument(
        "--reflexion-root",
        default=str(REFLEXION_ROOT_DEFAULT),
        help="Layer-2 reflexion root (default: .runtime/reflexion)",
    )
    scan_p.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Where to write *.sh.patch + summary.json (default: .runtime/suggestions)",
    )
    scan_p.add_argument(
        "--skills-root",
        default=None,
        help="Repo root for resolving alicloud-<skill>-ops/scripts/harness-lib.sh "
             "(default: parent of reflexion-root)",
    )
    scan_p.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"Minimum pattern count to emit a suggestion (default: {DEFAULT_THRESHOLD})",
    )
    scan_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview suggestions to stdout without writing files",
    )
    scan_p.set_defaults(func=cmd_scan)

    show_p = sub.add_parser("show", help="Print a previously emitted suggestion by hash")
    show_p.add_argument("hash", help="12-char sha1 prefix from summary.json")
    show_p.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Where to look for *.sh.patch (default: .runtime/suggestions)",
    )
    show_p.set_defaults(func=cmd_show)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
