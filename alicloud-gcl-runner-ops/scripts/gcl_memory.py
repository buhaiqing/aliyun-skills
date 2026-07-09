#!/usr/bin/env python3
"""
gcl_memory.py — Cross-session execution memory index for GCL traces.

Provides three operations:
  - memory_store()    — after a GCL run, index the trace into a JSONL file
  - memory_retrieve() — query recent memory entries for a skill/operation
  - memory_maintain() — TTL-based pruning of stale memory entries

Storage layout (under a configurable memory_root):
  .runtime/memory/
    alicloud-ecs-ops/
      DescribeInstances.jsonl
      DeleteInstance.jsonl
    alicloud-redis-ops/
      FlushInstance.jsonl

Each JSONL file contains one JSON object per line (newest appended last),
following the schema defined in AGENTS.md §16 (Memory Index).

DESIGN RATIONALE
----------------
- JSONL (not SQLite): matches the pure-stdlib constraint of gcl_runner.py.
  Humans can `tail`, `grep`, and `jq` the files without special tooling.
- One file per (skill, operation): enables efficient per-operation retrieval
  without scanning unrelated data.
- Append-only: writers never contend; memory_maintain() runs on a cron-like
  schedule to prune old entries.
- Non-fatal: memory_store() failures are logged as warnings, not errors.
  A transient write failure must not block the GCL runner's exit code.

Python 3.10+ stdlib only. No external dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List

# WT-1 parser (RG/Tags extraction). Defensive import — if the module is
# missing or fails to load, we fall back to a stub returning the empty
# schema. gcl_memory.py must never crash due to a missing parser.
try:
    from _extract_resource_dimensions import extract_from_command as _erd_extract_from_command
except Exception:  # ImportError or any other load failure
    def _erd_extract_from_command(command: str) -> dict[str, Any]:
        return {
            "resource_group_id": None,
            "tags": [],
            "tags_raw": None,
            "missing_dimensions": True,
            "warning": None,
            "suggestion": None,
        }

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MEMORY_ROOT = Path(".runtime") / "memory"
"""Default root directory for memory index (relative to skills root)."""

MEMORY_KEEP_DAYS_DEFAULT = 30
"""Default TTL for memory entries in days."""


# ---------------------------------------------------------------------------
# Core: memory_store
# ---------------------------------------------------------------------------


def _resolve_memory_root(memory_root: str | Path | None) -> Path:
    """Resolve the memory root path.

    Priority:
      1. explicit *memory_root* argument
      2. GCL_MEMORY_ROOT env var (relative to repo root)
      3. DEFAULT_MEMORY_ROOT (relative to repo root)

    Defensive: a literal string ``"None"`` (e.g. from a shell that expanded an
    unset env var) is treated as ``None`` and falls through to the default —
    otherwise the literal ``None/`` directory would be created under cwd.
    """
    if memory_root is not None and str(memory_root) != "None":
        return Path(memory_root)
    env = os.environ.get("GCL_MEMORY_ROOT")
    if env and env != "None":
        return Path(env)
    return DEFAULT_MEMORY_ROOT


def _extract_operation(command: str) -> str:
    """Extract the operation name from a CLI command or data-plane tool.

    Examples:
      "aliyun ecs DescribeInstances --PageSize 10"  → "DescribeInstances"
      "./scripts/ecs-skillopt-wrapper.sh DescribeInstances" → "DescribeInstances"
      "mongosh --host localhost --eval 'db.dropDatabase()'" → "mongosh"
      "redis-cli DEL key" → "redis-cli"
    """
    parts = command.strip().split()
    if not parts:
        return "unknown"

    # aliyun <product> <operation> [...]
    if len(parts) >= 3 and parts[0] == "aliyun":
        return parts[2]

    # *-skillopt-wrapper.sh or *-harness-wrapper.sh <operation> [...]
    if len(parts) >= 2 and ("skillopt-wrapper" in parts[0] or "harness-wrapper" in parts[0]):
        return parts[1]

    # data-plane tools: take the command name itself
    return parts[0]


def _extract_resource_dimensions_from_command(
    command: str,
) -> dict[str, Any]:
    """Extract RG/Tags from a CLI command string via WT-1 parser.

    Returns the full schema (resource_group_id, tags, tags_raw,
    missing_dimensions, warning, suggestion) — same shape as the
    parser's extract() / extract_from_command() output.

    Never raises; on any failure (parser import error, malformed
    command), returns the empty schema with missing_dimensions=True.
    """
    if not command or not command.strip():
        return {
            "resource_group_id": None,
            "tags": [],
            "tags_raw": None,
            "missing_dimensions": True,
            "warning": None,
            "suggestion": None,
        }
    try:
        return _erd_extract_from_command(command)
    except Exception:
        return {
            "resource_group_id": None,
            "tags": [],
            "tags_raw": None,
            "missing_dimensions": True,
            "warning": None,
            "suggestion": None,
        }


def _build_memory_entry(
    trace: dict[str, Any],
    operation: str | None,
    trace_path: str | Path | None,
) -> dict[str, Any]:
    """Extract a compact memory entry from a full GCL trace.

    The entry is intentionally smaller than the full trace — it indexes
    only the fields needed for retrieval and trend analysis.
    """
    final = trace.get("final", {})
    iterations = trace.get("iterations") or []
    last_iter = iterations[-1] if iterations else {}
    gen = last_iter.get("generator", {}) if last_iter else {}
    critic = last_iter.get("critic", {}) if last_iter else {}

    # Resolve operation: explicit parameter > trace field > auto-extraction
    resolved_op = operation
    if resolved_op is None:
        resolved_op = trace.get("operation")
    if resolved_op is None:
        resolved_op = _extract_operation(gen.get("command", ""))

    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "skill": trace.get("skill", "unknown"),
        "operation": resolved_op,
        "command": gen.get("command", ""),
        "exit_code": gen.get("exit_code", -1),
        "execution_path": gen.get("execution_path", "unknown"),
        "duration_ms": gen.get("duration_ms", 0),
        "iterations": len(iterations),
        "rubric_pass": final.get("status") == "PASS",
        "gcl_status": final.get("status", "UNKNOWN"),
        "rubric_version": trace.get("rubric_version", ""),
        "scores": dict(critic.get("scores", {})),
    }

    # Attach failure pattern if present (only on SAFETY_FAIL / failures)
    fp = trace.get("failure_pattern")
    if fp is not None:
        entry["failure_pattern"] = {
            "category": fp.get("category", "unknown"),
            "fix": fp.get("fix", ""),
        }

    # Resource dimensions (RG/Tags) — extracted from generator command.
    # Always present; missing_dimensions=true signals the caller skipped
    # both filters (a soft error observable in retrospect).
    rd = _extract_resource_dimensions_from_command(gen.get("command", ""))
    entry["resource_group_id"] = rd.get("resource_group_id")
    entry["tags"] = rd.get("tags", [])
    entry["missing_dimensions"] = bool(rd.get("missing_dimensions", True))
    if rd.get("tags_raw"):
        entry["tags_raw"] = rd["tags_raw"]
    if rd.get("warning"):
        entry["warning"] = rd["warning"]
    if rd.get("suggestion"):
        entry["suggestion"] = rd["suggestion"]

    # Reference back to the full trace file
    if trace_path:
        entry["trace_path"] = str(trace_path)

    return entry


def _get_memory_file(memory_root: Path, skill: str, operation: str) -> Path:
    """Return the path to the JSONL file for *(skill, operation)*.

    Creates parent directories if they don't exist.
    """
    op_safe = operation.replace("/", "_").replace(" ", "_")
    mem_file = memory_root / skill / f"{op_safe}.jsonl"
    mem_file.parent.mkdir(parents=True, exist_ok=True)
    return mem_file


def memory_store(
    trace: dict[str, Any],
    operation: str | None = None,
    trace_path: str | Path | None = None,
    memory_root: str | Path | None = None,
) -> int:
    """Index a GCL trace into the memory store.

    Writes one JSON line to ``.runtime/memory/{skill}/{operation}.jsonl``.
    The operation is auto-extracted from the command if not provided.

    Args:
        trace: The full GCL trace dict (as produced by run_loop()).
        operation: Explicit operation name (e.g. "DescribeInstances").
                   If None, auto-extracted from the command string.
        trace_path: Path to the persisted trace file (for reference).
        memory_root: Override the memory root directory.

    Returns:
        0 on success, 1 on failure (logged as warning).
    """
    try:
        root = _resolve_memory_root(memory_root)
        entry = _build_memory_entry(trace, operation, trace_path)
        mem_file = _get_memory_file(root, entry["skill"], entry["operation"])
        # Append JSON line with file locking for concurrent safety
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        with open(mem_file, "a", encoding="utf-8") as f:
            try:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Acquire exclusive lock
                try:
                    f.write(line + "\n")
                    f.flush()  # Ensure data is written before releasing lock
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock
            except ImportError:
                # Windows or non-Unix: fallback without locking (acceptable for single-process)
                f.write(line + "\n")
        return 0
    except Exception as exc:
        print(f"[WARN] memory_store failed: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Core: memory_store_lite (for direct wrapper calls — no GCL trace required)
# ---------------------------------------------------------------------------


def memory_store_lite(
    skill: str,
    operation: str,
    command: str,
    exit_code: int = 0,
    duration_ms: int = 0,
    status: str = "success",
    execution_path: str = "wrapper",
    memory_root: str | Path | None = None,
    error_code: str = "",
    resource_group_id: str | None = None,
    tags: list[dict[str, str]] | None = None,
    missing_dimensions: bool | None = None,
) -> int:
    """Lightweight memory append for direct wrapper calls.

    Unlike memory_store() which requires a full GCL trace dict, this accepts
    a flat set of fields and writes a minimal entry. Used by the SkillOpt
    core lib to ensure every aliyun CLI invocation leaves a Layer 1 memory
    trace, even when GCL runner is not in the loop.

    Args:
        skill: Skill name like "alicloud-slb-ops".
        operation: Operation name like "DescribeLoadBalancers".
        command: The full command line that was executed.
        exit_code: Process exit code (0 for success).
        duration_ms: Wall-clock duration of the invocation.
        status: "success" | "failed" | "running".
        execution_path: "wrapper" | "direct_aliyun" | etc.
        memory_root: Override the memory root directory.
        error_code: API or wrapper error code when status is failed (for L2 promote).
        resource_group_id: Optional RG extracted by caller. If None, falls
            back to extracting from ``command`` via WT-1 parser.
        tags: Optional list of ``{"key", "value"}`` dicts. Same fallback.
        missing_dimensions: Optional override for the missing-dimensions
            flag. If None, computed from RG/Tags (True iff both absent).

    Returns:
        0 on success, 1 on failure (logged as warning).
    """
    try:
        root = _resolve_memory_root(memory_root)
        if not operation or operation == "unknown":
            op = _extract_operation(command) or "unknown"
        else:
            op = operation
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "skill": skill,
            "operation": op,
            "command": command,
            "exit_code": exit_code,
            "execution_path": execution_path,
            "duration_ms": duration_ms,
            "iterations": 0,
            "rubric_pass": exit_code == 0,
            "gcl_status": "LIGHTWEIGHT" if status == "success" else status.upper(),
            "rubric_version": "wrapper-lite",
            "scores": {},
            "source": "skillopt-wrapper",
        }
        norm_code = (error_code or "").strip()
        if norm_code and not norm_code.startswith("exit_code_"):
            entry["error_code"] = norm_code

        # Resource dimensions (RG/Tags). When caller did not provide
        # explicit values, fall back to extracting from ``command`` via
        # the WT-1 parser. Always emit at least the boolean — consumers
        # rely on missing_dimensions being present.
        if (resource_group_id is None and tags is None
                and missing_dimensions is None):
            rd = _extract_resource_dimensions_from_command(command)
            entry["resource_group_id"] = rd.get("resource_group_id")
            entry["tags"] = rd.get("tags", [])
            entry["missing_dimensions"] = bool(rd.get("missing_dimensions", True))
            if rd.get("tags_raw"):
                entry["tags_raw"] = rd["tags_raw"]
            if rd.get("warning"):
                entry["warning"] = rd["warning"]
            if rd.get("suggestion"):
                entry["suggestion"] = rd["suggestion"]
        else:
            entry["resource_group_id"] = resource_group_id
            entry["tags"] = tags if tags is not None else []
            # missing_dimensions: prefer explicit override, else derive.
            if missing_dimensions is None:
                missing_dimensions = (
                    entry["resource_group_id"] is None
                    and len(entry["tags"]) == 0
                )
            entry["missing_dimensions"] = bool(missing_dimensions)

        mem_file = _get_memory_file(root, skill, op)
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        with open(mem_file, "a", encoding="utf-8") as f:
            try:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Acquire exclusive lock
                try:
                    f.write(line + "\n")
                    f.flush()  # Ensure data is written before releasing lock
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock
            except ImportError:
                # Windows or non-Unix: fallback without locking (acceptable for single-process)
                f.write(line + "\n")
        return 0
    except Exception as exc:
        print(f"[WARN] memory_store_lite failed: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Core: memory_retrieve
# ---------------------------------------------------------------------------


def _matches_resource_dimensions(
    entry: dict[str, Any],
    resource_group_id: str | None,
    tag_filter: dict[str, str] | None,
) -> bool:
    """Return True iff *entry* satisfies both resource-dimension filters.

    Pure predicate — no side effects. Used by :func:`memory_retrieve` to
    apply WT-4 hard-filter after JSONL read but before sort+slice.

    Rules (both must hold):

    * RG: ``resource_group_id`` is ``None`` ⟹ no filter; otherwise
      ``entry["resource_group_id"]`` must equal it exactly. Legacy entries
      without the field default to ``None`` (via ``.get``).
    * Tags: ``tag_filter`` is ``None`` OR an empty dict ⟹ no filter;
      otherwise every ``(k, v)`` pair in ``tag_filter`` must appear in
      ``entry["tags"]``. Multi-key AND semantics. Entries with empty
      tags fail when any filter key is requested.

    Edge cases (NEVER raise):

    * ``entry`` without ``resource_group_id`` key (legacy) — treated as
      ``None`` via ``.get``. Will fail an explicit RG match.
    * ``entry["tags"]`` may be missing on legacy entries — defaulted to
      ``[]`` via ``.get``.
    """
    # RG filter
    if resource_group_id is not None:
        if entry.get("resource_group_id") != resource_group_id:
            return False

    # Tag filter — empty dict is treated as None (no filtering)
    if tag_filter:
        entry_tags = entry.get("tags") or []
        # Build a lookup of entry tags as {key: value} for O(1) checks.
        # entry_tags is a list of {"key", "value"} dicts (from WT-1 parser).
        tag_map: dict[str, str] = {}
        for t in entry_tags:
            if isinstance(t, dict):
                k = t.get("key")
                v = t.get("value")
                if k is not None and v is not None:
                    tag_map[str(k)] = str(v)
        for k, v in tag_filter.items():
            if tag_map.get(str(k)) != str(v):
                return False

    return True


def memory_retrieve(
    skill: str,
    operation: str | None = None,
    top_k: int = 5,
    memory_root: str | Path | None = None,
    resource_group_id: str | None = None,
    tag_filter: dict[str, str] | None = None,
) -> List[dict[str, Any]]:
    """Query recent memory entries for a skill, optionally filtered by operation.

    Returns the most recent *top_k* entries sorted by timestamp descending.
    Entries are the compact index form (not full GCL traces).

    Args:
        skill: Skill name like "alicloud-ecs-ops".
        operation: Optional operation filter. If None, aggregates all
                   operations for this skill.
        top_k: Maximum number of entries to return.
        memory_root: Override the memory root directory.
        resource_group_id: Optional hard filter on the entry's
                           ``resource_group_id`` field. When provided,
                           only entries with an exact match are returned.
                           Legacy entries without the field are excluded.
                           When ``None`` (default), no RG filtering is
                           applied — existing call-sites are unaffected.
        tag_filter: Optional ``{key: value}`` hard filter on the entry's
                    tags. Multi-key AND semantics: every (k, v) pair
                    must match a tag on the entry. Empty dict is treated
                    as ``None`` (no filtering). Legacy entries with
                    empty tags fail any non-empty filter.

    Returns:
        List of memory entry dicts, newest first. May be shorter than
        *top_k* when RG/Tags filtering excludes entries.
    """
    root = _resolve_memory_root(memory_root)
    skill_dir = root / skill

    if not skill_dir.exists():
        return []

    entries: list[dict[str, Any]] = []

    if operation:
        # Single operation file
        op_safe = operation.replace("/", "_").replace(" ", "_")
        mem_file = skill_dir / f"{op_safe}.jsonl"
        if mem_file.exists():
            entries = _read_jsonl_tail(mem_file, top_k)
    else:
        # Aggregate all operation files for this skill
        for jsonl_path in sorted(skill_dir.glob("*.jsonl")):
            file_entries = _read_jsonl_tail(jsonl_path, top_k)
            entries.extend(file_entries)

    # Apply WT-4 hard filter AFTER JSONL read but BEFORE sort+slice.
    # When BOTH filters are None, this is a no-op (zero regression).
    if resource_group_id is not None or tag_filter:
        entries = [
            e for e in entries
            if _matches_resource_dimensions(e, resource_group_id, tag_filter)
        ]

    # Sort by timestamp descending, return top_k
    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return entries[:top_k]


def _read_jsonl_tail(path: Path, n: int) -> List[dict[str, Any]]:
    """Read the last *n* JSON entries from a JSONL file.

    Uses a bounded single-read strategy: estimates bytes needed based on
    *n* and seeks to a position near the end, then reads one chunk and
    parses entries from the end. Falls back to reading the whole file when
    a single chunk doesn’t contain enough lines.
    """
    try:
        total_size = path.stat().st_size
    except OSError:
        return []

    if total_size == 0:
        return []

    # Estimate: average line ~256 bytes, plus margin
    avg_line_size = 256
    read_size = min(total_size, max(avg_line_size * n * 2, 256 * n))

    with open(path, "rb") as f:
        if read_size < total_size:
            f.seek(total_size - read_size)
            # Discard the first (partial) line
            data = f.read()
            newline_pos = data.find(b"\n")
            if newline_pos != -1 and newline_pos < len(data) - 1:
                data = data[newline_pos + 1 :]
            else:
                data = b""
        else:
            f.seek(0)
            data = f.read()

    lines = data.decode("utf-8").splitlines()

    # Parse from end to beginning, collect up to n valid JSON entries
    entries: list[dict[str, Any]] = []
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entries.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
        if len(entries) >= n:
            break

    # If we didn't get enough entries, fall back to expanded read
    if len(entries) < n and read_size < total_size:
        # Gradually increase read size instead of reading entire file
        expanded_read_size = min(total_size, read_size * 4)  # 4x the original size
        if expanded_read_size < total_size:
            with open(path, "rb") as f:
                f.seek(max(0, total_size - expanded_read_size))
                data = f.read()
                lines = data.decode("utf-8", errors="replace").splitlines()
                entries = []
                for line in reversed(lines):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        entries.append(json.loads(stripped))
                    except json.JSONDecodeError:
                        continue
                    if len(entries) >= n:
                        break
        else:
            # Only read full file as last resort
            with open(path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
            entries = []
            for line in reversed(all_lines):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entries.append(json.loads(stripped))
                except json.JSONDecodeError:
                    continue
                if len(entries) >= n:
                    break

    return entries


# ---------------------------------------------------------------------------
# Core: memory_maintain
# ---------------------------------------------------------------------------


def memory_maintain(
    memory_root: str | Path | None = None,
    keep_days: int = MEMORY_KEEP_DAYS_DEFAULT,
    apply: bool = False,
) -> dict[str, Any]:
    """Prune stale entries from the memory index.

    Scans all JSONL files under *memory_root*, removes entries older than
    *keep_days*, and rewrites the file in-place (or reports what would be
    removed in dry-run mode).

    Args:
        memory_root: Override the memory root directory.
        keep_days: Retention period in days. Entries older than this are pruned.
        apply: If True, actually delete stale entries. If False, dry-run.

    Returns:
        A dict with keys:
          - scanned_files: number of JSONL files examined
          - entries_before: total entry count before pruning
          - entries_after: total entry count after pruning (same as before if dry-run)
          - entries_pruned: number of entries that would be / were removed
          - kept_days: the retention period applied
          - applied: whether pruning was actually executed
    """
    root = _resolve_memory_root(memory_root)
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)

    result: dict[str, Any] = {
        "scanned_files": 0,
        "entries_before": 0,
        "entries_after": 0,
        "entries_pruned": 0,
        "keep_days": keep_days,
        "applied": apply,
    }

    if not root.exists():
        return result

    for jsonl_path in sorted(root.rglob("*.jsonl")):
        result["scanned_files"] += 1
        try:
            before, after, pruned = _prune_jsonl(jsonl_path, cutoff, apply)
            result["entries_before"] += before
            # In dry-run mode, entries_after reflects the unchanged file count
            result["entries_after"] += before if not apply else after
            result["entries_pruned"] += pruned
        except OSError as exc:
            print(f"[WARN] memory_maintain: skipping {jsonl_path}: {exc}", file=sys.stderr)

    return result


def _prune_jsonl(
    path: Path, cutoff: datetime, apply: bool
) -> tuple[int, int, int]:
    """Read a JSONL file, count how many entries are older than *cutoff*.

    Args:
        path: Path to the JSONL file.
        cutoff: Datetime threshold; entries older than this are pruned.
        apply: If True, rewrite the file without stale entries.

    Returns:
        (entries_before, entries_after, entries_pruned)
    """
    if not path.exists():
        return 0, 0, 0

    entries_before = 0
    kept_entries: list[str] = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entries_before += 1
            try:
                entry = json.loads(line)
                ts_str = entry.get("timestamp", "")
                if not ts_str:
                    # No timestamp → keep (conservative)
                    kept_entries.append(line)
                    continue
                # Parse ISO 8601 timestamp (with Z or +00:00)
                ts = _parse_iso_timestamp(ts_str)
                if ts is None or ts >= cutoff:
                    kept_entries.append(line)
            except (json.JSONDecodeError, ValueError):
                # Unparseable line → keep (conservative)
                kept_entries.append(line)

    entries_pruned = entries_before - len(kept_entries)

    if apply and entries_pruned > 0:
        path.write_text("\n".join(kept_entries) + "\n", encoding="utf-8")

    return entries_before, len(kept_entries), entries_pruned


# ---------------------------------------------------------------------------
# Core: memory_purge_unknown
# ---------------------------------------------------------------------------


def memory_purge_unknown(
    memory_root: str | Path | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Remove ``unknown.jsonl`` files from the memory index.

    ``unknown.jsonl`` is created automatically by memory_store() when a trace
    has no extractable operation (empty command). These are typically test or
    development artifacts with no operational value.

    Args:
        memory_root: Override the memory root directory.
        apply: If True, delete unknown.jsonl files. If False, dry-run.

    Returns:
        A dict with keys:
          - scanned_skills: number of skill directories examined
          - files_found: number of unknown.jsonl files found
          - files_removed: number of unknown.jsonl files removed (0 on dry-run)
          - dirs_cleaned: number of empty skill dirs removed
          - applied: whether deletion was actually executed
    """
    root = _resolve_memory_root(memory_root)

    result: dict[str, Any] = {
        "scanned_skills": 0,
        "files_found": 0,
        "files_removed": 0,
        "dirs_cleaned": 0,
        "applied": apply,
    }

    if not root.exists():
        return result

    for skill_dir in sorted(root.iterdir()):
        if not skill_dir.is_dir():
            continue
        result["scanned_skills"] += 1
        unknown_file = skill_dir / "unknown.jsonl"
        if not unknown_file.exists():
            continue
        result["files_found"] += 1

        if apply:
            unknown_file.unlink(missing_ok=True)
            result["files_removed"] += 1
            # Remove empty skill directory
            try:
                skill_dir.rmdir()  # only succeeds if empty
                result["dirs_cleaned"] += 1
            except OSError:
                pass

    return result


def _parse_iso_timestamp(ts_str: str) -> datetime | None:
    """Parse an ISO 8601 timestamp string to datetime.

    Supports: ``2026-06-20T10:30:00Z``, ``2026-06-20T10:30:00+00:00``
    Python 3.10 compatible (no ``datetime.fromisoformat`` with Z suffix).
    """
    try:
        # Handle 'Z' suffix
        normalized = ts_str.replace("Z", "+00:00")
        # Python 3.10's fromisoformat doesn't handle the 'Z' suffix
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gcl_memory.py",
        description="GCL execution memory index — store, retrieve, maintain.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # store
    store_p = sub.add_parser("store", help="Index a GCL trace into memory")
    store_p.add_argument("--trace", required=True, help="Path to the GCL trace JSON file")
    store_p.add_argument("--operation", help="Operation name; auto-extracted if omitted")
    store_p.add_argument("--memory-root", help="Memory root directory")

    # store-lite
    sl_p = sub.add_parser("store-lite", help="Append a lightweight entry from a direct wrapper call")
    sl_p.add_argument("--skill", required=True, help="Skill name (e.g. alicloud-slb-ops)")
    sl_p.add_argument("--operation", required=True, help="Operation name (or 'unknown' for auto-extract)")
    sl_p.add_argument("--command", required=True, help="Full command line that was executed", dest="command_str")
    sl_p.add_argument("--exit-code", type=int, default=0, help="Process exit code (default: 0)")
    sl_p.add_argument("--duration-ms", type=int, default=0, help="Wall-clock duration in ms")
    sl_p.add_argument("--status", default="success", help="success | failed (default: success)")
    sl_p.add_argument("--execution-path", default="wrapper", help="wrapper | direct_aliyun | etc.")
    sl_p.add_argument("--memory-root", help="Memory root directory")
    sl_p.add_argument("--error-code", default="", help="API/wrapper error code when failed")
    sl_p.add_argument("--resource-group-id", default=None,
                      help="Resource group ID; falls back to parsing --command if omitted")
    sl_p.add_argument("--tags-json", default=None,
                      help="Tags as JSON array of {key,value}; falls back to parsing --command if omitted")
    sl_p.add_argument("--missing-dimensions", choices=["true", "false"], default=None,
                      help="Override missing_dimensions flag (default: derive from RG/Tags)")

    # retrieve
    ret_p = sub.add_parser("retrieve", help="Query recent memory entries")
    ret_p.add_argument("--skill", required=True, help="Skill name (e.g. alicloud-ecs-ops)")
    ret_p.add_argument("--operation", help="Optional operation filter")
    ret_p.add_argument("--top-k", type=int, default=5, help="Max entries to return (default: 5)")
    ret_p.add_argument("--memory-root", help="Memory root directory")
    ret_p.add_argument("--resource-group-id", default=None,
                      help="Hard filter: only return entries with this ResourceGroupId")
    ret_p.add_argument("--tag-filter", default=None,
                      help=("Hard filter: JSON string of {key:value} pairs to AND-match "
                            "against entry tags (e.g. '{\"env\":\"prod\"}')"))
    ret_p.add_argument("--json", action="store_true", help="Output as JSON (default: human-readable)")

    # maintain
    maint_p = sub.add_parser("maintain", help="Prune stale memory entries")
    maint_p.add_argument("--keep-days", type=int, default=MEMORY_KEEP_DAYS_DEFAULT, help=f"Retention in days (default: {MEMORY_KEEP_DAYS_DEFAULT})")
    maint_p.add_argument("--apply", action="store_true", help="Actually prune (default: dry-run)")
    maint_p.add_argument("--memory-root", help="Memory root directory")

    # purge-unknown
    purge_p = sub.add_parser("purge-unknown", help="Remove unknown.jsonl test artifacts")
    purge_p.add_argument("--apply", action="store_true", help="Actually delete (default: dry-run)")
    purge_p.add_argument("--memory-root", help="Memory root directory")

    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for standalone usage."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "store":
        try:
            trace = json.loads(Path(args.trace).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[ERROR] failed to load trace file: {e}", file=sys.stderr)
            return 1
        rc = memory_store(
            trace,
            operation=args.operation,
            trace_path=args.trace,
            memory_root=args.memory_root,
        )
        if rc == 0:
            print("[MEMORY] stored")
        return rc

    elif args.command == "store-lite":
        # Parse --tags-json (optional, falls back to command parsing).
        tags_value: list[dict[str, str]] | None = None
        if args.tags_json:
            try:
                parsed = json.loads(args.tags_json)
                if isinstance(parsed, list):
                    tags_value = [
                        {"key": str(t.get("key", "")), "value": str(t.get("value", ""))}
                        for t in parsed
                        if isinstance(t, dict)
                    ]
            except (json.JSONDecodeError, TypeError, ValueError):
                tags_value = None  # invalid input → let fallback parser try
        missing_dims: bool | None = None
        if args.missing_dimensions == "true":
            missing_dims = True
        elif args.missing_dimensions == "false":
            missing_dims = False

        rc = memory_store_lite(
            skill=args.skill,
            operation=args.operation,
            command=args.command_str,
            exit_code=args.exit_code,
            duration_ms=args.duration_ms,
            status=args.status,
            execution_path=args.execution_path,
            memory_root=args.memory_root,
            error_code=args.error_code,
            resource_group_id=args.resource_group_id,
            tags=tags_value,
            missing_dimensions=missing_dims,
        )
        if rc == 0:
            print(f"[MEMORY] lite: {args.skill} {args.operation}")
        return rc

    elif args.command == "retrieve":
        # Parse --tag-filter (JSON string → dict). Empty / missing → None.
        tag_filter_value: dict[str, str] | None = None
        if args.tag_filter:
            try:
                parsed_tf = json.loads(args.tag_filter)
                if isinstance(parsed_tf, dict) and parsed_tf:
                    tag_filter_value = {str(k): str(v) for k, v in parsed_tf.items()}
            except (json.JSONDecodeError, TypeError, ValueError):
                tag_filter_value = None  # invalid input → no filter (graceful)

        entries = memory_retrieve(
            args.skill,
            operation=args.operation,
            top_k=args.top_k,
            memory_root=args.memory_root,
            resource_group_id=args.resource_group_id,
            tag_filter=tag_filter_value,
        )
        if args.json:
            print(json.dumps(entries, indent=2, ensure_ascii=False))
        else:
            if not entries:
                print("(no memory entries found)")
                return 0
            print(f"Found {len(entries)} memory entr{'y' if len(entries) == 1 else 'ies'}:")
            for i, entry in enumerate(entries, 1):
                status = "✅" if entry.get("rubric_pass") else "❌"
                ts = entry.get("timestamp", "?")[:19]
                op = entry.get("operation", "?")
                sc = entry.get("exit_code", "?")
                dur = entry.get("duration_ms", 0)
                print(f"  {i}. [{status}] {ts} | {op} | exit={sc} | {dur}ms")
        return 0

    elif args.command == "maintain":
        result = memory_maintain(
            memory_root=args.memory_root,
            keep_days=args.keep_days,
            apply=args.apply,
        )
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"[MEMORY] maintain ({mode}): "
              f"scanned {result['scanned_files']} files, "
              f"{result['entries_before']} → {result['entries_after']} entries "
              f"(pruned {result['entries_pruned']})")
        # Print JSON result on last line for programmatic consumers (cleanup_memory)
        print(json.dumps(result, ensure_ascii=False))
        return 0

    elif args.command == "purge-unknown":
        result = memory_purge_unknown(
            memory_root=args.memory_root,
            apply=args.apply,
        )
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"[MEMORY] purge-unknown ({mode}): "
              f"scanned {result['scanned_skills']} skills, "
              f"found {result['files_found']} unknown.jsonl files")
        if args.apply:
            print(f"         removed {result['files_removed']} files, "
                  f"cleaned {result['dirs_cleaned']} empty dirs")
        print(json.dumps(result, ensure_ascii=False))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
