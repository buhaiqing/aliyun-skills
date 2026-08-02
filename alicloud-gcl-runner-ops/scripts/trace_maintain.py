#!/usr/bin/env python3
"""
trace_maintain.py — P1b: Trace lifecycle management (hot/warm/cold archival).

GCL trace files accumulate indefinitely under .runtime/audit/gcl-runner-ops/.
This script enforces retention policies:

  - HOT  (0–7d):   Keep as-is (fast access for debugging)
  - WARM (7–30d):  Compress to .gz (saves ~90% disk)
  - COLD (>30d):   Delete (or archive to cold storage if --cold-dir given)

Idempotent: repeated runs produce the same end-state.

USAGE
-----
    # Dry-run: show what would happen
    python3 scripts/trace_maintain.py --dry-run

    # Apply retention (compress >7d, delete >30d)
    python3 scripts/trace_maintain.py --apply

    # Custom retention windows
    python3 scripts/trace_maintain.py --apply --hot-days 14 --warm-days 60

    # Archive cold traces instead of deleting
    python3 scripts/trace_maintain.py --apply --cold-dir /archive/traces/

EXIT CODES
----------
    0  Success
    1  Error (e.g. trace dir not found)
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_HOT_DAYS = int(os.environ.get("TRACE_MAINTAIN_HOT_DAYS", "7"))
DEFAULT_WARM_DAYS = int(os.environ.get("TRACE_MAINTAIN_WARM_DAYS", "30"))


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] [TRACE-MAINTAIN] {msg}", file=sys.stderr)


def _filename_timestamp(path: Path) -> datetime | None:
    """Extract timestamp from trace filename (gcl-trace-YYYYMMDD-HHMMSS-*.json)."""
    m = re.match(r"gcl-trace-(\d{8})-(\d{6})-", path.name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def classify_trace(path: Path, hot_cutoff: datetime, warm_cutoff: datetime) -> str:
    """Classify a trace file into hot/warm/cold tier based on filename timestamp."""
    ts = _filename_timestamp(path)
    if ts is None:
        # Fall back to mtime
        ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    if ts >= hot_cutoff:
        return "hot"
    if ts >= warm_cutoff:
        return "warm"
    return "cold"


def compress_trace(path: Path, dry_run: bool = False) -> Path | None:
    """Compress a trace JSON file to .gz. Returns the .gz path or None on dry-run."""
    gz_path = path.with_suffix(".json.gz")
    if gz_path.exists():
        # Already compressed; remove the uncompressed original
        if not dry_run:
            path.unlink()
        return gz_path
    if dry_run:
        return None
    try:
        data = path.read_bytes()
        gz_path.write_bytes(gzip.compress(data, compresslevel=6))
        path.unlink()
        return gz_path
    except OSError as exc:
        _log(f"event=compress result=error path={path.name} exception={exc}")
        return None


def maintain_traces(
    trace_dir: Path,
    hot_days: int = DEFAULT_HOT_DAYS,
    warm_days: int = DEFAULT_WARM_DAYS,
    cold_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply retention policy to trace files.

    Returns summary dict with counts per action.
    """
    if not trace_dir.is_dir():
        _log(f"event=maintain result=error reason=dir_not_found path={trace_dir}")
        return {"error": f"trace dir not found: {trace_dir}"}

    now = datetime.now(timezone.utc)
    hot_cutoff = now - timedelta(days=hot_days)
    warm_cutoff = now - timedelta(days=warm_days)

    stats: dict[str, int] = {"hot": 0, "compressed": 0, "deleted": 0, "archived": 0, "skipped": 0}

    # Process .json files
    for path in sorted(trace_dir.glob("gcl-trace-*.json")):
        tier = classify_trace(path, hot_cutoff, warm_cutoff)
        if tier == "hot":
            stats["hot"] += 1
        elif tier == "warm":
            result = compress_trace(path, dry_run=dry_run)
            if result or dry_run:
                stats["compressed"] += 1
            else:
                stats["skipped"] += 1
        else:  # cold
            if cold_dir:
                if not dry_run:
                    cold_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(path), str(cold_dir / path.name))
                stats["archived"] += 1
            else:
                if not dry_run:
                    path.unlink()
                stats["deleted"] += 1

    # Also handle already-compressed .gz files that are now cold
    for path in sorted(trace_dir.glob("gcl-trace-*.json.gz")):
        tier = classify_trace(path, hot_cutoff, warm_cutoff)
        if tier == "cold":
            if cold_dir:
                if not dry_run:
                    cold_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(path), str(cold_dir / path.name))
                stats["archived"] += 1
            else:
                if not dry_run:
                    path.unlink()
                stats["deleted"] += 1

    mode = "dry_run" if dry_run else "applied"
    _log(
        f"event=maintain result=success mode={mode} "
        f"hot={stats['hot']} compressed={stats['compressed']} "
        f"deleted={stats['deleted']} archived={stats['archived']}"
    )

    return {
        "mode": mode,
        "trace_dir": str(trace_dir),
        "hot_days": hot_days,
        "warm_days": warm_days,
        "stats": stats,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trace_maintain.py",
        description="P1b: Trace lifecycle management — hot/warm/cold archival for GCL traces.",
    )
    parser.add_argument(
        "--trace-dir", type=Path,
        default=Path(os.environ.get(
            "ALIYUN_SKILLS_RUNTIME_ROOT",
            Path(__file__).resolve().parent.parent.parent / ".runtime",
        )) / "audit" / "gcl-runner-ops",
        help="Directory containing gcl-trace-*.json files",
    )
    parser.add_argument("--hot-days", type=int, default=DEFAULT_HOT_DAYS,
                        help=f"Days to keep traces uncompressed (default: {DEFAULT_HOT_DAYS})")
    parser.add_argument("--warm-days", type=int, default=DEFAULT_WARM_DAYS,
                        help=f"Days to keep traces compressed before cold (default: {DEFAULT_WARM_DAYS})")
    parser.add_argument("--cold-dir", type=Path, default=None,
                        help="Archive cold traces here instead of deleting")
    parser.add_argument("--apply", action="store_true",
                        help="Actually perform operations (default: dry-run)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without making changes")

    args = parser.parse_args(argv)

    # --apply and --dry-run: --dry-run wins if both given
    dry_run = args.dry_run or not args.apply

    result = maintain_traces(
        trace_dir=args.trace_dir,
        hot_days=args.hot_days,
        warm_days=args.warm_days,
        cold_dir=args.cold_dir,
        dry_run=dry_run,
    )

    if "error" in result:
        print(json.dumps(result, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
