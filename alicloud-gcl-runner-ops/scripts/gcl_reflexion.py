#!/usr/bin/env python3
"""
gcl_reflexion.py — Layer 2: Reflexion Memory (pattern-based cross-session learning).

Extracts structured failure patterns from GCL traces, stores them in
.runtime/reflexion/reflexion.json (deduped by skill+command+error), and
regenerates docs/failure-patterns.md as a human-readable/agent-parseable report.

Layer 2 sits between Layer 1 (Execution Memory — raw trace index) and a future
Layer 3 (Strategy Memory — cross-skill trend analysis per docs/memory-strategy.md).

R4 (success patterns): design at references/success-patterns.md; store in
SUCCESS_PATTERNS_STORE; report at docs/success-patterns.md via success_report().

Design:
  - .runtime/reflexion/reflexion.json       ← failure pattern store
  - .runtime/reflexion/success_patterns.json ← hard-won PASS store (R4)
  - docs/failure-patterns.md                ← failure report (≤ 200 lines)
  - docs/success-patterns.md                ← success report (≤ 150 lines)

Python 3.10+ stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REFLEXION_ROOT_ENV = "GCL_REFLEXION_ROOT"
"""Env var to override reflexion root."""

REFLEXION_ROOT_DEFAULT = Path(".runtime") / "reflexion"
"""Default reflexion root (relative to skills dir or cwd)."""

REFLEXION_STORE = "reflexion.json"
"""Store filename under reflexion root."""

SUCCESS_PATTERNS_STORE = "success_patterns.json"
"""R4: hard-won PASS patterns (separate from failure store). Schema: references/success-patterns.md."""

SUCCESS_PATTERN_VERSION = "1.0.0"
"""Schema version for success_patterns.json."""

SUCCESS_DEDUP_KEYS = ("skill", "operation", "command_hash", "capture_reason")
"""Dedup key fields for success pattern rows (R4 draft)."""

VALID_CAPTURE_REASONS = frozenset({
    "multi_iter",
    "traps_informed",
    "score_recovery",
    "near_miss_resolved",
    "hallucination_recovery",
})

SUCCESS_STORE_REQUIRED_FIELDS = (
    "skill",
    "operation",
    "command_excerpt",
    "command_hash",
    "capture_reason",
    "iterations",
    "scores_summary",
    "scores_min",
    "preflight_had_traps",
    "trap_count",
    "hint",
    "source",
)

FAILURE_PATTERNS_PATH = Path("docs") / "failure-patterns.md"
"""Canonical path for the generated failure markdown report."""

SUCCESS_PATTERNS_PATH = Path("docs") / "success-patterns.md"
"""Canonical path for the generated success markdown report (R4)."""

MAX_REPORT_LINES = 200
"""Hard cap for failure-patterns.md (AGENTS.md §15 token budget)."""

MAX_SUCCESS_REPORT_LINES = 150
"""Hard cap for success-patterns.md (R4 token budget)."""

SUCCESS_REPORT_REASON_ORDER: tuple[str, ...] = (
    "hallucination_recovery",
    "multi_iter",
    "near_miss_resolved",
    "score_recovery",
    "traps_informed",
)

SUCCESS_REPORT_REASON_TITLES: dict[str, str] = {
    "hallucination_recovery": "Hallucination Recovery",
    "multi_iter": "Multi-Iteration Recovery",
    "near_miss_resolved": "Near-Miss Resolved",
    "score_recovery": "Score Recovery",
    "traps_informed": "Trap-Informed Pass",
}

MIN_PATTERN_COUNT = 3
"""Patterns with count < this are pruned during maintain()."""

PROMOTION_THRESHOLD = 10
"""Patterns with count >= this are candidates for §14 Hallucination Detection promotion."""

GENERALIZED_CLI_CATEGORY = "generalized_cli"
"""R5: cross-product CLI traps aggregated by ``normalized_key`` (not orchestration ``cross_skill``)."""

CROSS_SKILL_MIN_SKILLS_DEFAULT = 3
"""Minimum distinct skills sharing a ``normalized_key`` before generalization."""

REMEDIATION_TRACKED_CATEGORIES = frozenset({
    "cli_parameter",
    "runtime",
    "max_iter",
    "near_miss",
    GENERALIZED_CLI_CATEGORY,
})
"""Failure categories that participate in R6 remediation tracking."""

REMEDIATION_K_MIN = 2
REMEDIATION_K_MAX = 5
REMEDIATION_SCORE_PENALTY = 0.35
"""Retrieve score multiplier for patterns already marked remediated."""

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log(msg: str, *args: Any, **kw: Any) -> None:
    """Emit structured log for AI agent consumption.

    Format: ``[HH:MM:SS] [REFLEXION] key=value [key=value] message``

    All values use ``key=value`` pairs so an AI parsing the log can
    extract structured fields without regex.
    """
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    formatted = msg.format(*args, **kw) if args or kw else msg
    print(f"[{ts}] [REFLEXION] {formatted}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Category config
# ---------------------------------------------------------------------------

CATEGORY_CONFIG: dict[str, dict[str, Any]] = {
    "cli_parameter": {
        "title": "CLI Parameter Errors",
        "description": "从 GCL trace 中提取的 CLI 参数错误模式。高频模式优先。",
        "headers": ["Skill", "Command", "Error Pattern", "Root Cause", "Fix", "Count", "Last Seen"],
        "fields": ["skill", "command", "error", "root_cause", "fix", "count", "last_seen"],
        "dedup_keys": ["skill", "command", "error"],
    },
    "skill_generation": {
        "title": "Skill Generation Issues",
        "description": "Skill 生成器（alicloud-skill-generator）常见的结构错误模式。",
        "headers": ["Issue Type", "Frequency", "Fix Pattern", "First Seen", "Last Seen"],
        "fields": ["issue_type", "frequency", "fix_pattern", "first_seen", "last_seen"],
        "dedup_keys": ["issue_type", "fix_pattern"],
    },
    "cross_skill": {
        "title": "Cross-Skill Composition Failures",
        "description": "跨 Skill 调用链中的失败模式。",
        "headers": ["Source Skill", "Target Skill", "Failure Pattern", "Resolution", "Count", "Last Seen"],
        "fields": ["source_skill", "target_skill", "failure_pattern", "resolution", "count", "last_seen"],
        "dedup_keys": ["source_skill", "target_skill", "failure_pattern"],
    },
    "runtime": {
        "title": "Runtime Execution Patterns",
        "description": "GCL 执行中发现的运行时失败模式。",
        "headers": ["Skill", "Operation", "Failure Pattern", "Root Cause", "Prevention", "Last Seen"],
        "fields": ["skill", "operation", "failure_pattern", "root_cause", "prevention", "last_seen"],
        "dedup_keys": ["skill", "operation", "failure_pattern"],
    },
    "token_efficiency": {
        "title": "Token Efficiency Violations",
        "description": "Token Efficiency 规则的常见违反模式。",
        "headers": ["TE Rule", "Common Violation", "Fix", "Frequency", "Last Seen"],
        "fields": ["te_rule", "common_violation", "fix", "frequency", "last_seen"],
        "dedup_keys": ["te_rule", "common_violation"],
    },
    "max_iter": {
        "title": "Max Iterations Exceeded",
        "description": "GCL 执行达到最大迭代次数仍无法通过 Critic 评审。通常是由于参数、环境或配置问题。",
        "headers": ["Skill", "Operation", "Failing Dimensions", "Best Score", "Fix", "Count", "Last Seen"],
        "fields": ["skill", "operation", "failing_dimensions", "best_score", "fix", "count", "last_seen"],
        "dedup_keys": ["skill", "operation", "failing_dimensions"],
    },
    "near_miss": {
        "title": "Near-Miss Executions",
        "description": "GCL 执行虽 PASS 但某维度得分低于 0.8，存在潜在风险需要关注。",
        "headers": ["Skill", "Operation", "Low Dimensions", "Scores", "Fix", "Count", "Last Seen"],
        "fields": ["skill", "operation", "low_dimensions", "scores", "fix", "count", "last_seen"],
        "dedup_keys": ["skill", "operation", "low_dimensions"],
    },
}
"""Category definitions. Each entry describes the markdown table schema and dedup keys."""

# Wrapper → Layer 2 (plan B): allowlisted API error codes only; deny transient / infra noise.
WRAPPER_L2_ALLOWLIST = frozenset({
    "InvalidParameter",
    "InvalidParameterValue",
    "MissingParameter",
    "MissingParam",
    "Forbidden",
    "NoPermission",
    "ResourceNotFound",
    "InvalidInstanceId.NotFound",
    "QuotaExceeded",
    "LimitExceeded",
})

WRAPPER_L2_DENYLIST = frozenset({
    "Throttling",
    "Throttling.User",
    "ServiceUnavailable",
    "InternalError",
    "CircuitBreakerOpen",
    "WRAPPER_BYPASS",
})

WRAPPER_FIX_HINTS: dict[str, str] = {
    "InvalidParameter": "Verify CLI param format via `aliyun <product> <action> --help` (RepeatList .N suffix, JSON arrays).",
    "InvalidParameterValue": "Check parameter value against product limits and enum constraints.",
    "MissingParameter": "Add required parameters; RepeatList params need `.N` suffix.",
    "MissingParam": "Add required parameters; RepeatList params need `.N` suffix.",
    "Forbidden": "Check RAM policy actions and resource ownership for this operation.",
    "NoPermission": "Check RAM policy actions and resource ownership for this operation.",
    "ResourceNotFound": "Verify resource ID and RegionId before retry.",
    "InvalidInstanceId.NotFound": "Verify instance ID exists in the target region.",
    "QuotaExceeded": "Request quota increase or reduce batch size.",
    "LimitExceeded": "Request quota increase or reduce batch size.",
}

_SECRET_SUBS = [
    (
        re.compile(
            r'(AccessKey(?:Id|Secret)|SecretKey|password|token|Authorization)["\s:=]+\S+',
            re.I,
        ),
        r"\1=****",
    ),
]


def _sanitize_wrapper_text(text: str, limit: int = 200) -> str:
    if not text:
        return ""
    s = str(text)
    for pat, repl in _SECRET_SUBS:
        s = pat.sub(repl, s)
    return s[:limit]


def normalize_wrapper_error_code(code: str | None) -> str:
    code = (code or "").strip()
    if not code or code.startswith("exit_code_"):
        return ""
    return code


def extract_error_code_from_output(output: Any) -> str:
    if output is None or output == "":
        return ""
    try:
        if isinstance(output, str):
            data = json.loads(output)
        elif isinstance(output, (dict, list)):
            data = output
        else:
            return ""
        if isinstance(data, dict):
            raw = data.get("Code") or data.get("code") or ""
            return normalize_wrapper_error_code(str(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return ""


def resolve_wrapper_error_code(error_code: str | None, output: Any = None) -> str:
    code = normalize_wrapper_error_code(error_code)
    if code:
        return code
    return extract_error_code_from_output(output)


def wrapper_error_eligible(error_code: str | None) -> bool:
    code = normalize_wrapper_error_code(error_code)
    if not code:
        return False
    if code in WRAPPER_L2_DENYLIST:
        return False
    return code in WRAPPER_L2_ALLOWLIST


# ---------------------------------------------------------------------------
# Repair-table coverage (Phase 1 of "case-table self-evolution")
# ---------------------------------------------------------------------------
# Static ``skillopt_repair_error()`` case tables live in each product's
# ``scripts/harness-lib.sh``. Errors whose code does not appear in that table
# fall through to the generic "failed" branch and never auto-retry.
#
# ``parse_repair_table_codes()`` extracts the literal codes from the case
# interval so we can flag L2 patterns whose code is unmapped. Pattern matches
# the single-line glob form only:
#     TokenA|TokenB|TokenC)
# Anything fancier (multi-line, extglob, character classes) is intentionally
# ignored — losing <5% of edge globs is cheaper than a 50-line parser.

_CASE_BRANCH_RE = re.compile(r"^\s*([A-Za-z0-9_.|]+)\)\s*(?:#.*)?$")


def parse_repair_table_codes(harness_lib_path: Path | str) -> set[str]:
    """Return the set of error codes handled by a product's ``skillopt_repair_error`` case table.

    Reads ``harness_lib_path``, locates the ``case "$error_code" in`` ... ``esac``
    interval, and collects every literal token appearing in glob branches like
    ``Throttling|Throttling.User)``.

    Returns an empty set if the file is missing or the case interval is absent.
    Fail-open: callers must treat an empty set as "unknown coverage" rather than
    "no coverage".
    """
    p = Path(harness_lib_path)
    if not p.is_file():
        return set()
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return set()

    in_case = False
    codes: set[str] = set()
    for line in text.splitlines():
        if not in_case:
            if line.startswith('case "$error_code" in'):
                in_case = True
            continue
        stripped = line.strip()
        if stripped.startswith("esac"):
            break
        m = _CASE_BRANCH_RE.match(line)
        if not m:
            continue
        for token in m.group(1).split("|"):
            t = token.strip()
            if t:
                codes.add(t)
    return codes


# Skill name → relative harness-lib.sh path (relative to repo root).
_REPAIR_TABLE_PATH = {
    "alicloud-ecs-ops": "alicloud-ecs-ops/scripts/harness-lib.sh",
    "alicloud-rds-ops": "alicloud-rds-ops/scripts/harness-lib.sh",
    "alicloud-redis-ops": "alicloud-redis-ops/scripts/harness-lib.sh",
    "alicloud-slb-ops": "alicloud-slb-ops/scripts/harness-lib.sh",
    "alicloud-vpc-ops": "alicloud-vpc-ops/scripts/harness-lib.sh",
    "alicloud-oss-ops": "alicloud-oss-ops/scripts/harness-lib.sh",
    "alicloud-mongodb-ops": "alicloud-mongodb-ops/scripts/harness-lib.sh",
    "alicloud-elasticsearch-ops": "alicloud-elasticsearch-ops/scripts/harness-lib.sh",
    "alicloud-ack-ops": "alicloud-ack-ops/scripts/harness-lib.sh",
    "alicloud-cms-ops": "alicloud-cms-ops/scripts/harness-lib.sh",
    # ponytail: not enumerated here on purpose. Add as overlays gain coverage.
}


def is_mapped_in_repair_table(skill: str, error_code: str, skills_root: Path | None = None) -> bool:
    """True if ``error_code`` appears in the ``skillopt_repair_error`` case table for ``skill``.

    Fail-open semantics:
    - Unknown skill (not in ``_REPAIR_TABLE_PATH``) → True (assume covered to avoid
      false-positive unmapped warnings).
    - Missing harness-lib.sh file → True (same reason).
    - Empty parse result → True (parser failed, do not assert).
    """
    if not error_code:
        return True
    rel = _REPAIR_TABLE_PATH.get(skill)
    if not rel:
        return True
    root = Path(skills_root) if skills_root else Path.cwd()
    codes = parse_repair_table_codes(root / rel)
    if not codes:
        # Parser found nothing → fail-open.
        return True
    return error_code in codes


def _find_cli_pattern(store: dict[str, list[dict[str, Any]]], pattern: dict[str, Any]) -> dict[str, Any] | None:
    dedup_keys = CATEGORY_CONFIG["cli_parameter"]["dedup_keys"]
    for existing in store.get("cli_parameter", []):
        if all(existing.get(k) == pattern.get(k) for k in dedup_keys):
            return existing
    return None


def _reflexion_root() -> Path:
    env = os.environ.get(REFLEXION_ROOT_ENV)
    if env:
        return Path(env)
    skills_dir = os.environ.get("SKILLS_DIR", os.getcwd())
    return Path(skills_dir) / REFLEXION_ROOT_DEFAULT


def _store_path(root: Path | None = None) -> Path:
    return (root or _reflexion_root()) / REFLEXION_STORE


def _empty_reflexion_store() -> dict[str, list[dict[str, Any]]]:
    store: dict[str, list[dict[str, Any]]] = {cat: [] for cat in CATEGORY_CONFIG}
    store[GENERALIZED_CLI_CATEGORY] = []
    return store


def _load_store(root: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    """Load the reflexion JSON store, returning an empty store if missing."""
    sp = _store_path(root)
    if not sp.exists():
        return _empty_reflexion_store()
    try:
        data = json.loads(sp.read_text(encoding="utf-8"))
        # Ensure all categories exist
        for cat in CATEGORY_CONFIG:
            data.setdefault(cat, [])
        data.setdefault(GENERALIZED_CLI_CATEGORY, [])
        # Version migration placeholder
        return data
    except (json.JSONDecodeError, OSError):
        return _empty_reflexion_store()


def _save_store(store: dict[str, list[dict[str, Any]]], root: Path | None = None) -> None:
    """Write the reflexion JSON store atomically (write-temp + rename)."""
    sp = _store_path(root)
    sp.parent.mkdir(parents=True, exist_ok=True)
    tmp = sp.with_suffix(sp.suffix + ".tmp")
    tmp.write_text(
        json.dumps(store, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(sp)


def normalize_skill_name(skill: str | None) -> str:
    """Normalize skill id to ``alicloud-{product}-ops`` form."""
    if not skill:
        return ""
    s = str(skill).strip()
    if s.startswith("alicloud-") and s.endswith("-ops"):
        return s
    if s.endswith("-ops"):
        return f"alicloud-{s}"
    return s


def _skill_matches(pattern_skill: str | None, query_skill: str) -> bool:
    if not pattern_skill:
        return False
    return normalize_skill_name(pattern_skill) == normalize_skill_name(query_skill)


def _operation_matches(pattern: dict[str, Any], operation: str | None) -> bool:
    if not operation:
        return True
    for key in ("operation", "command"):
        val = pattern.get(key)
        if val and operation in str(val):
            return True
    return False


def _context_matches(
    pattern: dict[str, Any],
    resource_group_id: str | None,
    tag_filter: list[dict[str, str]] | None,
) -> bool:
    """Hard-filter a pattern by RG/Tags context (WT-5).

    Rules:
      - When both ``resource_group_id`` and ``tag_filter`` are None → match
        (no filtering; preserves backward-compat).
      - When either is provided, the pattern MUST carry a ``context`` field.
        Legacy patterns (no ``context``) fail the filter when any filter is
        active — callers opt in to context-aware retrieval deliberately.
      - RG match: ``pattern.context.resource_group_id == resource_group_id`` when
        ``resource_group_id`` is provided.
      - Tag match: every ``{"Key": k, "Value": v}`` pair in ``tag_filter`` must be
        present in ``pattern.context.tags``. ``pattern.context.tags`` is a list
        of strings in the canonical ``"Key:Value"`` form emitted by WT-1.
    """
    if resource_group_id is None and not tag_filter:
        return True

    ctx = pattern.get("context")
    if not isinstance(ctx, dict):
        return False

    if resource_group_id is not None:
        if ctx.get("resource_group_id") != resource_group_id:
            return False

    if tag_filter:
        tags_raw = ctx.get("tags") or []
        if not isinstance(tags_raw, list):
            return False
        # Normalize to "Key:Value" strings for membership checks.
        normalized = set()
        for t in tags_raw:
            if isinstance(t, str):
                normalized.add(t)
            elif isinstance(t, dict):
                k = t.get("Key") or t.get("key") or ""
                v = t.get("Value") or t.get("value") or ""
                if k:
                    normalized.add(f"{k}:{v}")
        for pair in tag_filter:
            key = pair.get("Key") or pair.get("key") or ""
            value = pair.get("Value") or pair.get("value") or ""
            if not key:
                continue
            if f"{key}:{value}" not in normalized:
                return False
    return True


def _parse_tags_json(tags_json: str | None) -> list[dict[str, str]] | None:
    """Parse ``--tags-json`` for retrieve CLI: expects a JSON array of
    ``{"Key": ..., "Value": ...}`` objects. Empty / None / unparseable returns
    None (no filter).
    """
    if not tags_json:
        return None
    try:
        data = json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, list):
        return None
    out: list[dict[str, str]] = []
    for entry in data:
        if isinstance(entry, dict):
            k = entry.get("Key") or entry.get("key") or ""
            v = entry.get("Value") or entry.get("value") or ""
            if k:
                out.append({"Key": k, "Value": v})
    return out or None


def _parse_tags_string_list(tags_json: str | None) -> list[str] | None:
    """Parse ``--tags-json`` for store-wrapper-lite CLI: expects a JSON array
    of strings (canonical ``"Key:Value"`` form). Empty / None / unparseable
    returns None.
    """
    if not tags_json:
        return None
    try:
        data = json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, list):
        return None
    out: list[str] = []
    for entry in data:
        if isinstance(entry, str) and entry:
            out.append(entry)
    return out or None


# ---------------------------------------------------------------------------
# R5.1 — error normalization (cross-skill grouping key)
# ---------------------------------------------------------------------------

_KNOWN_ERROR_CODES: tuple[str, ...] = (
    "MissingParam",
    "InvalidParameter",
    "InvalidParameterValue",
    "ResourceNotFound",
    "Forbidden",
    "QuotaExceeded",
    "Throttling",
    "SignatureDoesNotMatch",
    "Unauthorized",
    "OperationDenied",
)

_ERROR_CODE_RE = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in _KNOWN_ERROR_CODES) + r")\b",
    re.IGNORECASE,
)

_PARAM_AFTER_COLON_RE = re.compile(r"[:：]\s*['\"]?([A-Za-z][A-Za-z0-9_.]*)")
_PARAM_PHRASE_RE = re.compile(
    r"(?:parameter|param|field)\s+['\"]?([A-Za-z][A-Za-z0-9_.]*)",
    re.IGNORECASE,
)
_PARAM_QUOTED_RE = re.compile(
    r"['\"]([A-Za-z][A-Za-z0-9_.]*)['\"]\s+(?:is invalid|not found|required|missing)",
    re.IGNORECASE,
)
_COMMAND_FLAG_RE = re.compile(r"--([A-Za-z][A-Za-z0-9_.]+)")


def _canonical_error_code(raw: str) -> str:
    token = raw.strip()
    if not token:
        return ""
    for known in _KNOWN_ERROR_CODES:
        if token.lower() == known.lower():
            return known
    if token.lower() == "invalidparameter.value":
        return "InvalidParameterValue"
    return token


def _canonical_param(name: str) -> str:
    """Normalize parameter tokens to PascalCase API form when possible."""
    s = (name or "").strip()
    if not s:
        return ""
    if s[0].isupper() and s.isascii():
        return s
    lowered = s.lower()
    if lowered.endswith("id") and len(lowered) > 2:
        stem = lowered[:-2]
        if stem:
            return stem[0].upper() + stem[1:] + "Id"
    if lowered.endswith("ids") and len(lowered) > 3:
        stem = lowered[:-3]
        if stem:
            return stem[0].upper() + stem[1:] + "Ids"
    return s[0].upper() + s[1:]


def _camel_from_flag(flag: str) -> str:
    """Best-effort CLI flag → API param (InstanceId.1 → InstanceId)."""
    base = flag.split(".", 1)[0]
    if not base:
        return ""
    return _canonical_param(base)


def _infer_error_semantic(error_code: str, param: str) -> str:
    if not error_code:
        return ""
    if error_code == "MissingParam" and param:
        if param.endswith("Ids") or param.endswith("Id"):
            return "repeatlist_suffix"
        return "required_param"
    if error_code == "InvalidParameter" and param.lower() in ("regionid", "zoneid"):
        return "region_format"
    if error_code == "ResourceNotFound":
        return "resource_lookup"
    if error_code == "QuotaExceeded":
        return "quota_limit"
    if error_code == "Forbidden":
        return "ram_permission"
    return "generic"


def normalize_error_pattern(
    error: str,
    command: str | None = None,
) -> dict[str, str]:
    """Normalize CLI/API error text for cross-skill aggregation (R5.1).

    Returns ``error_code``, ``param``, ``normalized_key``, ``semantic``.
    All values are empty strings when nothing reliable can be extracted.
    """
    empty = {"error_code": "", "param": "", "normalized_key": "", "semantic": ""}
    text = (error or "").strip()
    if not text:
        return dict(empty)

    code_match = _ERROR_CODE_RE.search(text)
    error_code = _canonical_error_code(code_match.group(1)) if code_match else ""

    param = ""
    for regex in (_PARAM_AFTER_COLON_RE, _PARAM_PHRASE_RE, _PARAM_QUOTED_RE):
        m = regex.search(text)
        if m:
            param = m.group(1)
            break

    if not param and command:
        flags = _COMMAND_FLAG_RE.findall(command)
        lowered = text.lower()
        for flag in flags:
            camel = _camel_from_flag(flag)
            if camel and camel.lower() in lowered:
                param = camel
                break
        if not param and error_code == "MissingParam" and flags:
            param = _camel_from_flag(flags[0])

    param = _canonical_param(param)

    if not error_code:
        return dict(empty)

    normalized_key = f"{error_code}:{param}" if param else error_code
    semantic = _infer_error_semantic(error_code, param)
    return {
        "error_code": error_code,
        "param": param,
        "normalized_key": normalized_key,
        "semantic": semantic,
    }


def _enrich_cli_parameter_normalization(pattern: dict[str, Any]) -> None:
    """Attach R5.1 fields to cli_parameter rows before store/dedup."""
    if pattern.get("category") != "cli_parameter":
        return
    norm = normalize_error_pattern(
        str(pattern.get("error") or ""),
        str(pattern.get("command") or "") or None,
    )
    if not norm.get("normalized_key"):
        return
    for key in ("error_code", "param", "normalized_key", "semantic"):
        val = norm.get(key, "")
        if val:
            pattern[key] = val


def _build_generalized_cli_row(
    normalized_key: str,
    members: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build one aggregated cross-product trap row from cli_parameter members."""
    skills = sorted(
        {
            normalize_skill_name(str(m.get("skill") or ""))
            for m in members
            if m.get("skill")
        }
    )
    total_count = sum(int(m.get("count", 1)) for m in members)
    fixes: dict[str, int] = {}
    for m in members:
        fix = str(m.get("fix") or "").strip()
        if fix:
            fixes[fix] = fixes.get(fix, 0) + int(m.get("count", 1))
    best_fix = max(fixes, key=fixes.get) if fixes else "See product CLI --help for parameter format."

    last_seen = max((str(m.get("last_seen") or "") for m in members), default="")
    first_seen = min((str(m.get("first_seen") or last_seen) for m in members), default=last_seen)
    sample_cmd = " | ".join(str(m.get("command") or "")[:50] for m in members[:3])

    norm = normalize_error_pattern(
        str(members[0].get("error") or ""),
        str(members[0].get("command") or "") or None,
    )
    semantic = norm.get("semantic") or members[0].get("semantic", "generic")
    error_code = norm.get("error_code") or normalized_key.split(":", 1)[0]

    return {
        "category": GENERALIZED_CLI_CATEGORY,
        "normalized_key": normalized_key,
        "error_code": error_code,
        "param": norm.get("param", ""),
        "semantic": semantic,
        "skills": skills,
        "skill_count": len(skills),
        "failure_pattern": f"Cross-product: {normalized_key}",
        "error": normalized_key,
        "command": sample_cmd[:200],
        "fix": best_fix[:200],
        "count": total_count,
        "first_seen": first_seen or _now_iso(),
        "last_seen": last_seen or _now_iso(),
        "source": "cross-skill-aggregate",
    }


def reflexion_aggregate_generalized(
    root: Path | None = None,
    min_skills: int = CROSS_SKILL_MIN_SKILLS_DEFAULT,
    min_count: int = 1,
    apply: bool = False,
) -> dict[str, Any]:
    """R5.2: rebuild ``generalized_cli`` rows from ``cli_parameter`` store.

    Groups by ``normalized_key``; keeps groups with >= ``min_skills`` distinct skills.
    Replaces the entire ``generalized_cli`` list (derived data, safe to recompute).
    """
    store = _load_store(root)
    groups: dict[str, list[dict[str, Any]]] = {}

    for pattern in store.get("cli_parameter", []):
        if not isinstance(pattern, dict):
            continue
        if int(pattern.get("count", 0)) < min_count:
            continue
        key = str(pattern.get("normalized_key") or "").strip()
        if not key:
            continue
        groups.setdefault(key, []).append(pattern)

    generalized: list[dict[str, Any]] = []
    for key, members in sorted(groups.items()):
        skills = {
            normalize_skill_name(str(m.get("skill") or ""))
            for m in members
            if m.get("skill")
        }
        if len(skills) < min_skills:
            continue
        generalized.append(_build_generalized_cli_row(key, members))

    before = len(store.get(GENERALIZED_CLI_CATEGORY, []))
    stats: dict[str, Any] = {
        "status": "ok",
        "groups_scanned": len(groups),
        "generalized_before": before,
        "generalized_after": len(generalized),
        "min_skills": min_skills,
        "applied": apply,
    }

    if apply:
        store[GENERALIZED_CLI_CATEGORY] = generalized
        _save_store(store, root)
        _log(
            "event=aggregate_generalized result=applied before={} after={} min_skills={}",
            before,
            len(generalized),
            min_skills,
        )
    else:
        _log(
            "event=aggregate_generalized result=dry_run would_write={} min_skills={}",
            len(generalized),
            min_skills,
        )

    return stats


# ---------------------------------------------------------------------------
# Core: reflexion_extract
# ---------------------------------------------------------------------------


def reflexion_extract(trace: dict[str, Any]) -> dict[str, Any] | None:
    """Extract a structured failure pattern from a GCL trace.

    Looks for ``trace["failure_pattern"]`` (set by ``gcl_runner.extract_failure_pattern``
    on SAFETY_FAIL). Maps the category to one of the five canonical categories.

    If ``trace["resource_dimensions"]`` is present (WT-2 schema), propagate RG/Tags
    /missing_dimensions into a ``context`` field on the returned pattern. The
    ``context`` field is purely additive — it does not affect dedup, scoring, or
    reporting. Patterns without ``trace["resource_dimensions"]`` get no ``context``
    field (backward-compat with legacy callers and traces).

    Returns:
        A pattern dict with ``category``, the dedup fields for that category,
        and ``count`` set to 1, or *None* if no pattern is present.
    """
    fp = trace.get("failure_pattern")
    if not fp:
        return None

    category = fp.get("category", "unknown")
    # Unknown categories → skip; don't pollute a default bucket with wrong patterns
    if category not in CATEGORY_CONFIG:
        return None

    config = CATEGORY_CONFIG[category]
    pattern: dict[str, Any] = {"category": category, "count": 1, "first_seen": _now_iso()}

    for field in config["fields"]:
        if field == "count":
            continue
        if field == "first_seen":
            continue
        pattern[field] = fp.get(field, "")

    # Optional RG/Tags context propagation from WT-2 trace schema.
    # Additive: only attach when trace actually carries the field. Legacy traces
    # (no resource_dimensions) keep the same shape as before.
    rd = trace.get("resource_dimensions")
    if isinstance(rd, dict):
        pattern["context"] = {
            "resource_group_id": rd.get("resource_group_id"),
            "tags": list(rd.get("tags") or []),
            "missing_dimensions": bool(rd.get("missing_dimensions", True)),
        }

    # Propagate git_commit from trace if present, else capture current HEAD
    pattern["git_commit"] = trace.get("git_commit") or _get_git_head()

    return pattern


def reflexion_extract_wrapper_lite(
    skill: str,
    product: str,
    action: str,
    command: str,
    error_code: str = "",
    output: Any = None,
    resource_group_id: str | None = None,
    tags: list[str] | None = None,
    missing_dimensions: bool | None = None,
) -> dict[str, Any] | None:
    """Extract a Layer-2 cli_parameter pattern from a failed wrapper invocation.

    Optional RG/Tags context (``resource_group_id``, ``tags``, ``missing_dimensions``)
    is propagated into a ``context`` field on the returned pattern. The ``context``
    field is only attached when at least one of these kwargs is explicitly passed,
    preserving backward-compat with existing callers.
    """
    code = resolve_wrapper_error_code(error_code, output)
    if not wrapper_error_eligible(code):
        return None

    message = ""
    if output is not None and output != "":
        try:
            data = output if isinstance(output, (dict, list)) else json.loads(str(output))
            if isinstance(data, dict):
                message = str(data.get("Message") or data.get("message") or "")[:120]
        except (json.JSONDecodeError, TypeError, ValueError):
            message = _sanitize_wrapper_text(str(output), 120)

    fix = WRAPPER_FIX_HINTS.get(
        code,
        "See references/cli-usage.md and `aliyun <product> <action> --help` for parameter format.",
    )
    error_field = code
    if message:
        error_field = f"{code}: {message}"[:120]

    pattern: dict[str, Any] = {
        "category": "cli_parameter",
        "skill": normalize_skill_name(skill),
        "command": _sanitize_wrapper_text(command.strip()[:200], 200),
        "error": _sanitize_wrapper_text(error_field, 120),
        "error_code": code,
        "fix": _sanitize_wrapper_text(fix, 200),
        "count": 1,
        "first_seen": _now_iso(),
        "source": "wrapper-lite",
    }
    # Phase 1 repair-coverage: flag if the error code is not in the product's
    # ``skillopt_repair_error`` case table. ``is_mapped_in_repair_table`` is
    # fail-open (unknown skill / missing file → True), so unmapped_in_repair
    # only flips to True when we *know* the code is unmapped.
    pattern["unmapped_in_repair"] = not is_mapped_in_repair_table(
        normalize_skill_name(skill), code
    )

    # Attach RG/Tags context only when at least one dimension is explicitly passed.
    has_rg = resource_group_id is not None
    has_tags = bool(tags)
    has_missing = missing_dimensions is not None
    if has_rg or has_tags or has_missing:
        # missing_dimensions defaults to True only when caller passed neither RG nor tags
        # but explicitly signaled missing_dimensions; otherwise stay with explicit value.
        if missing_dimensions is None:
            missing_dimensions = resource_group_id is None and not (tags or [])
        pattern["context"] = {
            "resource_group_id": resource_group_id,
            "tags": list(tags) if tags else [],
            "missing_dimensions": bool(missing_dimensions),
        }

    pattern["git_commit"] = _get_git_head()
    return pattern


def reflexion_store_wrapper_lite(
    skill: str,
    trace_path: Path | str,
    root: Path | None = None,
    resource_group_id: str | None = None,
    tags: list[str] | None = None,
    missing_dimensions: bool | None = None,
) -> int:
    """Plan B: store allowlisted wrapper failures into Layer 2 (non-fatal).

    Optional ``resource_group_id``, ``tags``, and ``missing_dimensions`` are
    propagated to ``reflexion_extract_wrapper_lite`` so the stored pattern
    carries RG/Tags context for downstream retrieval filtering. Callers that
    do not pass these kwargs preserve the original (context-less) shape.
    """
    try:
        trace = json.loads(Path(trace_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[WARN] reflexion_store_wrapper_lite: load trace failed: {exc}", file=sys.stderr)
        return 1

    product = str(trace.get("product") or "")
    action = str(trace.get("action") or "")
    params = str(trace.get("params") or "").strip()
    command = f"aliyun {product} {action} {params}".strip()
    trace_skill = str(trace.get("skill") or skill)
    pattern = reflexion_extract_wrapper_lite(
        skill=trace_skill,
        product=product,
        action=action,
        command=command,
        error_code=str(trace.get("error_code") or ""),
        output=trace.get("output"),
        resource_group_id=resource_group_id,
        tags=tags,
        missing_dimensions=missing_dimensions,
    )
    if pattern is None:
        return 0
    return reflexion_store(pattern, root=root)


def reflexion_promote_from_memory(
    memory_root: Path | str,
    reflexion_root: Path | None = None,
    min_count: int = MIN_PATTERN_COUNT,
    apply: bool = False,
) -> dict[str, Any]:
    """Plan C: aggregate failed wrapper L1 entries and reconcile Layer 2 counts."""
    memory_root = Path(memory_root)
    stats: dict[str, Any] = {
        "scanned_entries": 0,
        "failed_wrapper": 0,
        "eligible_keys": 0,
        "promoted": 0,
        "reconciled": 0,
        "skipped_low_count": 0,
        "apply": apply,
    }

    if not memory_root.is_dir():
        stats["status"] = "skipped"
        stats["reason"] = "memory root missing"
        return stats

    agg: dict[tuple[str, str, str], dict[str, Any]] = {}

    for jsonl in sorted(memory_root.rglob("*.jsonl")):
        try:
            lines = jsonl.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            stats["scanned_entries"] += 1
            if entry.get("source") != "skillopt-wrapper":
                continue
            exit_code = entry.get("exit_code", 0)
            rubric_pass = entry.get("rubric_pass", exit_code == 0)
            if exit_code == 0 and rubric_pass:
                continue
            stats["failed_wrapper"] += 1
            code = resolve_wrapper_error_code(entry.get("error_code"), entry.get("output"))
            if not wrapper_error_eligible(code):
                continue
            skill = normalize_skill_name(str(entry.get("skill") or ""))
            command = str(entry.get("command") or "")[:200]
            op = str(entry.get("operation") or "")
            key = (skill, command, code)
            if key not in agg:
                agg[key] = {
                    "skill": skill,
                    "command": command,
                    "operation": op,
                    "error_code": code,
                    "count": 0,
                }
            agg[key]["count"] += 1

    store = _load_store(reflexion_root)

    for info in agg.values():
        l1_count = info["count"]
        if l1_count < min_count:
            stats["skipped_low_count"] += 1
            continue
        stats["eligible_keys"] += 1
        pattern = reflexion_extract_wrapper_lite(
            skill=info["skill"],
            product="",
            action=info["operation"],
            command=info["command"],
            error_code=info["error_code"],
        )
        if pattern is None:
            continue
        existing = _find_cli_pattern(store, pattern)
        l2_count = existing.get("count", 0) if existing else 0
        if l1_count <= l2_count:
            continue
        if apply:
            if existing:
                existing["count"] = l1_count
                existing["last_seen"] = _now_iso()
                stats["reconciled"] += 1
            else:
                pattern["count"] = l1_count
                pattern["last_seen"] = _now_iso()
                store.setdefault("cli_parameter", []).append(pattern)
                stats["promoted"] += 1
        elif existing:
            stats["reconciled"] += 1
        else:
            stats["promoted"] += 1

    if apply and (stats["promoted"] > 0 or stats["reconciled"] > 0):
        _save_store(store, reflexion_root)

    stats["status"] = "ok"
    return stats


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_git_head() -> str:
    """Return the current git HEAD commit hash, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:40]
    except Exception:
        pass
    return ""


def _time_weighted_score(
    pattern: dict[str, Any],
    now: datetime | None = None,
    decay_days: float = 90.0,
) -> float:
    """Compute a time-weighted score for a pattern.

    ``score = count * (1 - min(elapsed_days / decay_days, 1) * 0.5)``

    Patterns seen recently get the full weight. Patterns older than
    ``decay_days`` lose half their weight. Patterns without a timestamp
    are treated as recently seen (no decay).
    """
    count = pattern.get("count", 0)
    last_seen_str = pattern.get("last_seen", "")
    if not last_seen_str:
        return float(count)
    dt = now or datetime.now(timezone.utc)
    try:
        last_seen_dt = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
        elapsed = (dt - last_seen_dt).total_seconds() / 86400.0
        decay = min(elapsed / decay_days, 1.0)
        return count * (1.0 - decay * 0.5)
    except (ValueError, TypeError):
        return float(count)


# ---------------------------------------------------------------------------
# Core: reflexion_store
# ---------------------------------------------------------------------------


def reflexion_store(pattern: dict[str, Any] | None, root: Path | None = None) -> int:
    """Store a failure pattern into the reflexion memory.

    Dedup by the category's ``dedup_keys``. If an existing pattern matches,
    its ``count`` is incremented. Otherwise the new pattern is appended.

    Args:
        pattern: The pattern dict (from ``reflexion_extract`` or manual).
        root: Override the reflexion root.

    Returns:
        0 on success or skip (None pattern), 1 on failure.
    """
    if pattern is None:
        return 0

    category = pattern.get("category", "unknown")
    if category not in CATEGORY_CONFIG:
        return 0

    _enrich_cli_parameter_normalization(pattern)

    try:
        store = _load_store(root)
        config = CATEGORY_CONFIG[category]
        dedup_keys = config["dedup_keys"]
        patterns = store.setdefault(category, [])

        # Try to find a matching existing pattern
        matched = False
        target: dict[str, Any] | None = None
        for existing in patterns:
            if all(existing.get(k) == pattern.get(k) for k in dedup_keys):
                existing["count"] = existing.get("count", 1) + 1
                existing["last_seen"] = _now_iso()
                matched = True
                target = existing
                break

        if not matched:
            if category in REMEDIATION_TRACKED_CATEGORIES:
                _ensure_remediation_fields(pattern)
                pattern["recent_failures"] = 1
            if "count" not in pattern:
                pattern["count"] = 1
            pattern["last_seen"] = _now_iso()
            patterns.append(pattern)
            target = pattern
            _log("event=reflexion_store result=new category={} skill={} command={}",
                 category, pattern.get("skill", "?"), pattern.get("command", "?")[:60])
        else:
            if category in REMEDIATION_TRACKED_CATEGORIES and target is not None:
                remediation_record_failure_event(target)
            _log("event=reflexion_store result=incremented category={} skill={} new_count={}",
                 category, pattern.get("skill", "?"), target.get("count", 0) if target else 0)

        _save_store(store, root)
        return 0
    except Exception as exc:
        print(f"[WARN] reflexion_store failed: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Core: reflexion_retrieve (R2 — pre-flight read path)
# ---------------------------------------------------------------------------


def reflexion_retrieve(
    skill: str,
    operation: str | None = None,
    top_k: int = 5,
    root: Path | None = None,
    min_count: int = 1,
    resource_group_id: str | None = None,
    tag_filter: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Return failure patterns for a skill (R2 + R5.3 tiered ranking).

    Priority: **specific** (per-skill rows) → **generalized_cli** (cross-product)
    → **generic** (other categories, e.g. orchestration ``cross_skill``).

    Optional ``resource_group_id`` and ``tag_filter`` apply a hard filter on the
    pattern's ``context`` field. When both are None, behaviour is unchanged
    (legacy entries without ``context`` are returned). When either is provided,
    patterns without ``context`` are excluded — this opt-in preserves the
    principle that legacy data is still visible by default.
    """
    store = _load_store(root)
    tiers: dict[int, list[tuple[float, dict[str, Any]]]] = {0: [], 1: [], 2: []}

    def _append(tier: int, pattern: dict[str, Any], category: str) -> None:
        count = pattern.get("count", 0)
        if not isinstance(count, int) or count < min_count:
            return
        if not _operation_matches(pattern, operation):
            return
        if not _context_matches(pattern, resource_group_id, tag_filter):
            return
        score = _time_weighted_score(pattern)
        if pattern.get("remediated"):
            score *= REMEDIATION_SCORE_PENALTY
        entry = dict(pattern)
        entry["category"] = category
        entry["_tier"] = tier
        entry["_score"] = round(score, 2)
        tiers[tier].append((score, entry))

    for category, patterns in store.items():
        if not isinstance(patterns, list):
            continue
        if category == GENERALIZED_CLI_CATEGORY:
            for pattern in patterns:
                if not isinstance(pattern, dict):
                    continue
                skills = pattern.get("skills") or []
                if not any(_skill_matches(s, skill) for s in skills):
                    continue
                _append(1, pattern, category)
            continue
        if category not in CATEGORY_CONFIG:
            continue
        for pattern in patterns:
            if not isinstance(pattern, dict):
                continue
            if category in ("cli_parameter", "runtime", "max_iter", "near_miss"):
                if not _skill_matches(pattern.get("skill"), skill):
                    continue
                _append(0, pattern, category)
            elif category == "cross_skill":
                if not _skill_matches(
                    pattern.get("source_skill") or pattern.get("skill"), skill
                ):
                    continue
                _append(2, pattern, category)
            else:
                if not _skill_matches(
                    pattern.get("skill") or pattern.get("source_skill"), skill
                ):
                    continue
                _append(2, pattern, category)

    merged: list[dict[str, Any]] = []
    for tier in (0, 1, 2):
        tiers[tier].sort(key=lambda item: item[0], reverse=True)
        for _, entry in tiers[tier]:
            if len(merged) >= top_k:
                return merged
            merged.append(entry)
    return merged


# ---------------------------------------------------------------------------
# R6: remediation confirmation & stability tracking
# ---------------------------------------------------------------------------


def _default_remediation_fields() -> dict[str, Any]:
    return {
        "remediated": False,
        "remediated_at": "",
        "total_opportunities": 0,
        "recent_failures": 0,
        "consecutive_successes": 0,
    }


def _ensure_remediation_fields(pattern: dict[str, Any]) -> None:
    """Backfill R6 schema fields on legacy store rows (idempotent)."""
    defaults = _default_remediation_fields()
    for key, default in defaults.items():
        if key not in pattern:
            pattern[key] = default
    if pattern.get("remediated") and not pattern.get("remediated_at"):
        pattern["remediated_at"] = pattern.get("last_seen") or _now_iso()


def remediation_confirm_window_k(pattern: dict[str, Any]) -> int:
    """R6.2: dynamic confirmation window K from pattern frequency."""
    count = int(pattern.get("count", 1))
    opportunities = int(pattern.get("total_opportunities", 0))
    signal = count + opportunities
    if signal >= 20:
        return REMEDIATION_K_MAX
    if signal >= 10:
        return 4
    if signal >= 5:
        return 3
    return REMEDIATION_K_MIN


def _find_trap_store_row(
    store: dict[str, list[dict[str, Any]]],
    trap: dict[str, Any],
) -> dict[str, Any] | None:
    """Locate the store row matching a preflight ``known_traps`` entry."""
    category = trap.get("category") or "cli_parameter"
    if category == GENERALIZED_CLI_CATEGORY:
        key = str(trap.get("normalized_key") or "").strip()
        if not key:
            return None
        for row in store.get(GENERALIZED_CLI_CATEGORY, []):
            if isinstance(row, dict) and row.get("normalized_key") == key:
                return row
        return None
    if category not in CATEGORY_CONFIG:
        return None
    dedup_keys = CATEGORY_CONFIG[category]["dedup_keys"]
    for row in store.get(category, []):
        if not isinstance(row, dict):
            continue
        if all(row.get(k) == trap.get(k) for k in dedup_keys):
            return row
    return None


def remediation_record_failure_event(pattern: dict[str, Any]) -> None:
    """R6.3: failure recurred — reset success streak and unmark remediated."""
    _ensure_remediation_fields(pattern)
    pattern["consecutive_successes"] = 0
    pattern["recent_failures"] = int(pattern.get("recent_failures", 0)) + 1
    if pattern.get("remediated"):
        pattern["remediated"] = False
        pattern["remediated_at"] = ""
        _log(
            "event=remediation_unmark reason=failure_recurred category={} skill={}",
            pattern.get("category", "?"),
            pattern.get("skill", "?"),
        )


def remediation_record_opportunities(
    traps: list[dict[str, Any]],
    root: Path | None = None,
) -> int:
    """Increment ``total_opportunities`` for traps shown at preflight."""
    if not traps:
        return 0
    try:
        store = _load_store(root)
        updated = False
        for trap in traps:
            if not isinstance(trap, dict):
                continue
            category = trap.get("category")
            if category not in REMEDIATION_TRACKED_CATEGORIES:
                continue
            row = _find_trap_store_row(store, trap)
            if row is None:
                continue
            _ensure_remediation_fields(row)
            row["total_opportunities"] = int(row.get("total_opportunities", 0)) + 1
            updated = True
        if updated:
            _save_store(store, root)
        return 0
    except Exception as exc:
        print(f"[WARN] remediation_record_opportunities failed: {exc}", file=sys.stderr)
        return 1


def remediation_record_success_streak(
    traps: list[dict[str, Any]],
    root: Path | None = None,
) -> dict[str, int]:
    """R6.3: PASS after traps were injected — advance streak; confirm at K."""
    stats = {"updated": 0, "confirmed": 0}
    if not traps:
        return stats
    try:
        store = _load_store(root)
        updated = False
        for trap in traps:
            if not isinstance(trap, dict):
                continue
            category = trap.get("category")
            if category not in REMEDIATION_TRACKED_CATEGORIES:
                continue
            row = _find_trap_store_row(store, trap)
            if row is None:
                continue
            _ensure_remediation_fields(row)
            row["consecutive_successes"] = int(row.get("consecutive_successes", 0)) + 1
            stats["updated"] += 1
            k = remediation_confirm_window_k(row)
            if row["consecutive_successes"] >= k and not row.get("remediated"):
                row["remediated"] = True
                row["remediated_at"] = _now_iso()
                row["recent_failures"] = 0
                stats["confirmed"] += 1
                _log(
                    "event=remediation_confirm k={} category={} skill={} key={}",
                    k,
                    category,
                    row.get("skill", "?"),
                    row.get("normalized_key") or row.get("error", "")[:40],
                )
            updated = True
        if updated:
            _save_store(store, root)
        return stats
    except Exception as exc:
        print(f"[WARN] remediation_record_success_streak failed: {exc}", file=sys.stderr)
        return stats


def remediation_apply_from_trace(
    trace: dict[str, Any],
    root: Path | None = None,
) -> dict[str, Any]:
    """Apply R6 updates from a completed GCL trace (non-fatal hook)."""
    preflight = trace.get("memory_preflight") or {}
    traps = preflight.get("known_traps") or []
    final = trace.get("final") or {}
    status = final.get("status")
    result: dict[str, Any] = {
        "traps": len(traps),
        "status": status,
        "opportunities_recorded": False,
        "success_streak": {"updated": 0, "confirmed": 0},
    }
    if not traps:
        return result
    remediation_record_opportunities(traps, root=root)
    result["opportunities_recorded"] = True
    if status == "PASS":
        result["success_streak"] = remediation_record_success_streak(traps, root=root)
    return result


# ---------------------------------------------------------------------------
# R4: success pattern store / retrieve (hard-won PASS)
# ---------------------------------------------------------------------------


def _success_patterns_path(root: Path | None = None) -> Path:
    return (root or _reflexion_root()) / SUCCESS_PATTERNS_STORE


def _empty_success_store() -> dict[str, Any]:
    return {
        "version": SUCCESS_PATTERN_VERSION,
        "updated_at": _now_iso(),
        "patterns": [],
    }


def _load_success_store(root: Path | None = None) -> dict[str, Any]:
    """Load success_patterns.json; return empty store if missing or corrupt."""
    sp = _success_patterns_path(root)
    if not sp.exists():
        return _empty_success_store()
    try:
        data = json.loads(sp.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("patterns"), list):
            return _empty_success_store()
        data.setdefault("version", SUCCESS_PATTERN_VERSION)
        data.setdefault("patterns", [])
        return data
    except (json.JSONDecodeError, OSError, TypeError):
        return _empty_success_store()


def _save_success_store(store: dict[str, Any], root: Path | None = None) -> None:
    """Write success_patterns.json atomically (write-temp + rename)."""
    store["version"] = SUCCESS_PATTERN_VERSION
    store["updated_at"] = _now_iso()
    sp = _success_patterns_path(root)
    sp.parent.mkdir(parents=True, exist_ok=True)
    tmp = sp.with_suffix(sp.suffix + ".tmp")
    tmp.write_text(
        json.dumps(store, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(sp)


def compute_command_hash(command: str) -> str:
    """Normalize whitespace and return ``sha256:<hex>`` for dedup."""
    normalized = " ".join(command.split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _validate_success_pattern(pattern: dict[str, Any]) -> str | None:
    """Return error message if invalid, else None."""
    for field in SUCCESS_STORE_REQUIRED_FIELDS:
        if field not in pattern:
            return f"missing field: {field}"
    reason = pattern.get("capture_reason")
    if reason not in VALID_CAPTURE_REASONS:
        return f"invalid capture_reason: {reason!r}"
    if pattern.get("command_excerpt") and "<masked>" in str(pattern["command_excerpt"]):
        return "command_excerpt contains masked secret placeholder"
    if pattern.get("hint") and "<masked>" in str(pattern["hint"]):
        return "hint contains masked secret placeholder"
    return None


def success_store(pattern: dict[str, Any] | None, root: Path | None = None) -> int:
    """Store a hard-won PASS success pattern (R4).

    Dedup by ``SUCCESS_DEDUP_KEYS``. On match: increment ``count``, update
    ``last_seen``; refresh ``hint`` / ``scores_min`` only when the new row improves.

    Returns 0 on success or skip (``None`` pattern), 1 on failure.
    """
    if pattern is None:
        return 0

    err = _validate_success_pattern(pattern)
    if err:
        _log("event=success_store result=skipped reason={}", err)
        return 0

    try:
        store = _load_success_store(root)
        patterns: list[dict[str, Any]] = store["patterns"]
        matched: dict[str, Any] | None = None
        for existing in patterns:
            if all(existing.get(k) == pattern.get(k) for k in SUCCESS_DEDUP_KEYS):
                matched = existing
                break

        now = _now_iso()
        excerpt = str(pattern.get("command_excerpt", ""))[:200]
        hint = str(pattern.get("hint", ""))[:300]

        if matched is not None:
            matched["count"] = int(matched.get("count", 1)) + 1
            matched["last_seen"] = now
            new_min = float(pattern.get("scores_min", 0))
            old_min = float(matched.get("scores_min", 0))
            if new_min > old_min:
                matched["scores_min"] = new_min
                matched["scores_summary"] = pattern.get("scores_summary", matched.get("scores_summary", ""))
                matched["hint"] = hint
            _log(
                "event=success_store result=incremented skill={} op={} count={}",
                pattern.get("skill", "?"),
                pattern.get("operation", "?"),
                matched.get("count", 0),
            )
        else:
            row = {
                "skill": normalize_skill_name(str(pattern["skill"])),
                "operation": str(pattern["operation"]),
                "command_excerpt": excerpt,
                "command_hash": str(pattern["command_hash"]),
                "capture_reason": str(pattern["capture_reason"]),
                "iterations": int(pattern["iterations"]),
                "scores_summary": str(pattern["scores_summary"])[:200],
                "scores_min": float(pattern["scores_min"]),
                "preflight_had_traps": bool(pattern["preflight_had_traps"]),
                "trap_count": int(pattern["trap_count"]),
                "hint": hint,
                "count": 1,
                "first_seen": now,
                "last_seen": now,
                "source": str(pattern.get("source") or "gcl-runner"),
            }
            for opt in ("execution_path", "matched_trap_categories", "trace_path"):
                if pattern.get(opt) not in (None, "", []):
                    row[opt] = pattern[opt]
            patterns.append(row)
            _log(
                "event=success_store result=new skill={} op={} reason={}",
                row["skill"],
                row["operation"],
                row["capture_reason"],
            )

        _save_success_store(store, root)
        return 0
    except Exception as exc:
        print(f"[WARN] success_store failed: {exc}", file=sys.stderr)
        return 1


def success_retrieve(
    skill: str,
    operation: str | None = None,
    top_k: int = 3,
    root: Path | None = None,
    min_count: int = 1,
    resource_group_id: str | None = None,
    tag_filter: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Return hard-won success patterns for a skill, sorted by time-weighted score.

    Optional ``resource_group_id`` and ``tag_filter`` apply a hard filter on the
    pattern's ``context`` field. When both are None, behaviour is unchanged.
    When either is provided, patterns without ``context`` are excluded.
    """
    store = _load_success_store(root)
    ranked: list[tuple[float, dict[str, Any]]] = []

    for pattern in store.get("patterns", []):
        if not isinstance(pattern, dict):
            continue
        count = pattern.get("count", 0)
        if not isinstance(count, int) or count < min_count:
            continue
        if not _skill_matches(pattern.get("skill"), skill):
            continue
        if not _operation_matches(pattern, operation):
            continue
        if not _context_matches(pattern, resource_group_id, tag_filter):
            continue
        score = _time_weighted_score(pattern)
        if pattern.get("preflight_had_traps"):
            score *= 1.15
        entry = dict(pattern)
        entry["_score"] = round(score, 2)
        ranked.append((score, entry))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked[:top_k]]


def format_success_patterns(
    patterns: list[dict[str, Any]],
    max_chars: int = 600,
    item_max_chars: int = 200,
) -> str:
    """Format patterns as prompt-ready ``{{success_patterns}}`` text.

    Each per-pattern row is truncated to ``item_max_chars`` chars (default 200)
    BEFORE joining, so no single row can blow the per-item budget even if the
    underlying ``hint``/``command_excerpt`` is long. The overall joined text
    is then truncated to ``max_chars`` as a final guard.
    """
    if not patterns:
        return "(none — no hard-won success patterns for this skill/operation)"

    lines: list[str] = []
    for p in patterns:
        reason = p.get("capture_reason", "unknown")
        count = p.get("count", 1)
        hint = p.get("hint") or p.get("command_excerpt") or ""
        line = f"- [{reason}] count={count}"
        if hint:
            line += f" {str(hint)[:160]}"
        if len(line) > item_max_chars:
            line = line[: item_max_chars - 3] + "..."
        lines.append(line)

    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    truncated = text[: max_chars - 3].rsplit("\n", 1)[0]
    return truncated + "..."


def format_known_traps(
    patterns: list[dict[str, Any]],
    max_chars: int = 800,
    item_max_chars: int = 200,
) -> str:
    """Format patterns as prompt-ready ``{{known_traps}}`` text.

    Each per-pattern row is truncated to ``item_max_chars`` chars (default 200)
    BEFORE joining, so no single row can blow the per-item budget even when
    the underlying ``fix``/``command``/``error`` fields are long. The overall
    joined text is then truncated to ``max_chars`` as a final guard.
    """
    filtered: list[dict[str, Any]] = []
    for p in patterns:
        count = p.get("count", 1)
        if count < MIN_PATTERN_COUNT:
            continue
        root_cause = p.get("root_cause")
        if root_cause is not None and not str(root_cause).strip():
            continue
        filtered.append(p)

    if not filtered:
        return "(none — no matching failure patterns in Reflexion memory)"

    lines: list[str] = []
    for p in filtered:
        category = p.get("category", "unknown")
        count = p.get("count", 1)
        fix = p.get("fix") or p.get("prevention") or p.get("resolution") or ""
        err = (
            p.get("error")
            or p.get("failure_pattern")
            or p.get("failing_dimensions")
            or p.get("low_dimensions")
            or p.get("normalized_key")
            or ""
        )
        cmd = p.get("command", "")
        line = f"- [{category}] count={count}"
        if p.get("remediated"):
            line += " remediated=yes"
        if category == GENERALIZED_CLI_CATEGORY:
            skill_count = p.get("skill_count") or len(p.get("skills") or [])
            line += f" cross_skill_skills={skill_count}"
        if err:
            line += f" error={str(err)[:80]}"
        if cmd:
            line += f" cmd={str(cmd)[:60]}"
        if fix:
            line += f" fix={str(fix)[:100]}"
        if len(line) > item_max_chars:
            line = line[: item_max_chars - 3] + "..."
        lines.append(line)

    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    truncated = text[: max_chars - 3].rsplit("\n", 1)[0]
    return truncated + "..."


# ---------------------------------------------------------------------------
# Core: success_report (R4)
# ---------------------------------------------------------------------------


def success_report(
    root: Path | None = None,
    output_path: str | Path | None = None,
    sort_by: str = "weighted",
) -> int:
    """Regenerate ``docs/success-patterns.md`` from the success pattern store.

    Args:
        root: Override the reflexion root (``success_patterns.json`` lives here).
        output_path: Defaults to ``docs/success-patterns.md`` under SKILLS_DIR/cwd.
        sort_by: ``weighted`` (time-weighted score, default) or ``count``.

    Returns:
        0 on success, 1 on failure.
    """
    try:
        store = _load_success_store(root)
        patterns: list[dict[str, Any]] = store.get("patterns", [])
        skills_dir = Path(os.environ.get("SKILLS_DIR", os.getcwd()))
        output = Path(output_path) if output_path else (skills_dir / SUCCESS_PATTERNS_PATH)

        lines: list[str] = [
            "# Success Patterns — Hard-Won PASS Memory",
            "",
            "> **Purpose**: Structured positive reference from GCL hard-won PASS outcomes.",
            "> Agents load via R2 ``{{success_patterns}}`` (Generator only — not Critic).",
            ">",
            "> **Auto-generated**: Regenerated by ``gcl_reflexion.py success-report``.",
            f"> **Token budget**: ≤ {MAX_SUCCESS_REPORT_LINES} lines.",
            "",
        ]

        now = datetime.now(timezone.utc)
        by_reason: dict[str, list[dict[str, Any]]] = {}
        for pat in patterns:
            if not isinstance(pat, dict):
                continue
            reason = str(pat.get("capture_reason") or "multi_iter")
            by_reason.setdefault(reason, []).append(pat)

        total_entries = 0
        reason_order = list(SUCCESS_REPORT_REASON_ORDER) + sorted(
            r for r in by_reason if r not in SUCCESS_REPORT_REASON_ORDER
        )

        for reason in reason_order:
            group = by_reason.get(reason)
            if not group:
                continue

            if sort_by == "count":
                sorted_group = sorted(group, key=lambda p: p.get("count", 0), reverse=True)
            else:
                sorted_group = sorted(
                    group,
                    key=lambda p: _time_weighted_score(p, now=now),
                    reverse=True,
                )

            title = SUCCESS_REPORT_REASON_TITLES.get(reason, reason.replace("_", " ").title())
            lines.extend(["---", "", f"## {title}", ""])
            lines.append(
                "|Skill|Operation|Command|Hint|Count|Scores Min|Last Seen|"
            )
            lines.append("|---|---|---|---|---|---|---|")

            for pat in sorted_group:
                hint = str(pat.get("hint") or "")[:80].replace("|", "/")
                cmd = str(pat.get("command_excerpt") or "")[:60].replace("|", "/")
                last_seen = str(pat.get("last_seen") or "")[:19]
                row = "|".join(
                    [
                        str(pat.get("skill", "")),
                        str(pat.get("operation", "")),
                        cmd,
                        hint,
                        str(pat.get("count", 1)),
                        str(pat.get("scores_min", "")),
                        last_seen,
                    ]
                )
                lines.append(f"|{row}|")

            lines.append("")
            total_entries += len(sorted_group)

        lines.extend(
            [
                "---",
                "",
                "## Usage Guidelines",
                "",
                "### For Agents (Pre-flight)",
                "",
                "```",
                "# Prefer runtime injection (do not rely on this file alone):",
                "#   memory_preflight.py → {{success_patterns}}",
                "# Optional: read this file and filter by skill/operation",
                "```",
                "",
                "### For GCL Runner",
                "",
                "```",
                "# After hard-won PASS, the runner stores patterns:",
                "#   success_store(extract_success_pattern(trace))",
                "# Regenerate this file:",
                "#   python gcl_reflexion.py success-report",
                "```",
                "",
            ]
        )

        report = "\n".join(lines) + "\n"
        line_count = len(lines)
        if line_count > MAX_SUCCESS_REPORT_LINES:
            print(
                f"[WARN] success-patterns.md exceeds {MAX_SUCCESS_REPORT_LINES} lines "
                f"({line_count}). Prune low-count rows in success_patterns.json.",
                file=sys.stderr,
            )

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        _log(
            "event=success_report_written file={} lines={} entries={} sort_by={}",
            output,
            line_count,
            total_entries,
            sort_by,
        )
        return 0

    except Exception as exc:
        print(f"[ERROR] success_report failed: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Core: reflexion_report
# ---------------------------------------------------------------------------


def reflexion_report(
    root: Path | None = None,
    output_path: str | Path | None = None,
    sort_by: str = "weighted",
) -> int:
    """Regenerate ``docs/failure-patterns.md`` from the reflexion store.

    Renders each non-empty category as a markdown table, sorted descending.

    Args:
        root: Override the reflexion root.
        output_path: Where to write the report. Defaults to ``docs/failure-patterns.md``
                     relative to SKILLS_DIR or cwd.
        sort_by: Sort order — ``"weighted"`` (time-weighted score, default) or
                 ``"count"`` (raw frequency, no recency bias).

    Returns:
        0 on success, 1 on failure.
    """
    try:
        store = _load_store(root)
        lines: list[str] = []
        skills_dir = Path(os.environ.get("SKILLS_DIR", os.getcwd()))
        output = Path(output_path) if output_path else (skills_dir / FAILURE_PATTERNS_PATH)

        # Header
        lines.append("# Failure Patterns — Reflexion Memory")
        lines.append("")
        lines.append("> **Purpose**: Structured failure memory extracted from GCL traces and Self-Review records.")
        lines.append("> Agents can optionally load this file during Pre-flight to prevent known errors.")
        lines.append(">")
        lines.append("> **Auto-generated**: This file is regenerated by ``gcl_reflexion.py report``.")
        lines.append("> **Token budget**: ≤ 200 lines. When exceeded, prune with ``gcl_reflexion.py maintain``.")
        lines.append("")

        total_entries = 0
        for cat_key, config in CATEGORY_CONFIG.items():
            patterns = store.get(cat_key, [])
            if not patterns:
                continue

            # Sort by selected strategy
            now = datetime.now(timezone.utc)
            if sort_by == "count":
                sorted_patterns = sorted(
                    patterns,
                    key=lambda p: p.get("count", 0),
                    reverse=True,
                )
            else:
                # Default: time-weighted score (considers both frequency and recency)
                sorted_patterns = sorted(
                    patterns,
                    key=lambda p: _time_weighted_score(p, now=now),
                    reverse=True,
                )

            lines.append("---")
            lines.append("")
            lines.append(f"## {config['title']}")
            lines.append("")
            lines.append(f"> {config['description']}")
            lines.append("")

            # Render table
            headers = config["headers"]
            fields = config["fields"]
            sep = "|" + "|".join("---" for _ in headers) + "|"
            header_row = "|" + "|".join(headers) + "|"
            lines.append(header_row)
            lines.append(sep)
            for pat in sorted_patterns:
                row = "|" + "|".join(str(pat.get(f, "")) for f in fields) + "|"
                lines.append(row)
            lines.append("")

            total_entries += len(sorted_patterns)

        # Usage guidelines (static)
        lines.append("---")
        lines.append("")
        lines.append("## Usage Guidelines")
        lines.append("")
        lines.append("### For Agents (Pre-flight)")
        lines.append("")
        lines.append("```")
        lines.append("# Optional: Load failure patterns before executing a skill")
        lines.append("# 1. Read this file (lazy-load, ~150 lines)")
        lines.append("# 2. Filter patterns by current skill name")
        lines.append("# 3. Inject relevant patterns into Generator context as prevention hints")
        lines.append("```")
        lines.append("")
        lines.append("### For GCL Runner")
        lines.append("")
        lines.append("```")
        lines.append("# After each GCL run with SAFETY_FAIL, the runner stores patterns:")
        lines.append("#   reflexion_store(reflexion_extract(trace))")
        lines.append("# Regenerate this file:")
        lines.append("#   python gcl_reflexion.py report")
        lines.append("```")
        lines.append("")
        lines.append("### Maintenance")
        lines.append("")
        lines.append("```")
        lines.append(f"# Prune patterns with count < {MIN_PATTERN_COUNT} if lines > {MAX_REPORT_LINES}:")
        lines.append("#   python gcl_reflexion.py maintain --apply")
        lines.append("```")

        report = "\n".join(lines) + "\n"

        # Check if within budget (informational only — maintain() does enforcement)
        line_count = len(lines)
        if line_count > MAX_REPORT_LINES:
            print(f"[WARN] failure-patterns.md exceeds {MAX_REPORT_LINES} lines ({line_count}). "
                  f"Run `gcl_reflexion.py maintain --apply` to prune.",
                  file=sys.stderr)

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        _log("event=report_written file={} lines={} entries={} sort_by={}",
             output, line_count, total_entries, sort_by)
        return 0

    except Exception as exc:
        print(f"[ERROR] reflexion_report failed: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Core: reflexion_maintain
# ---------------------------------------------------------------------------


def reflexion_maintain(
    root: Path | None = None,
    max_lines: int = MAX_REPORT_LINES,
    min_count: int = MIN_PATTERN_COUNT,
    decay_days: int = 0,
    apply: bool = False,
) -> dict[str, Any]:
    """Prune low-frequency and/or stale patterns from the reflexion store.

    Two-tier pruning:
      1. Always: remove patterns with ``count < min_count``.
      2. If ``decay_days > 0``: also remove patterns whose ``last_seen`` is
         older than ``decay_days``, regardless of count.

    In dry-run mode (default), reports what would be pruned.

    Args:
        root: Override the reflexion root.
        max_lines: Line budget for the markdown report (informational).
        min_count: Minimum count threshold. Patterns below this are pruned.
        decay_days: If > 0, prune patterns not seen in this many days.
        apply: If True, actually prune; if False, dry-run.

    Returns:
        A dict with per-category and total prune counts.
    """
    store = _load_store(root)
    now = datetime.now(timezone.utc)
    result: dict[str, Any] = {
        "max_lines": max_lines,
        "min_count": min_count,
        "decay_days": decay_days,
        "applied": apply,
        "total_before": 0,
        "total_pruned": 0,
        "total_after": 0,
        "pruned_by_count": 0,
        "pruned_by_decay": 0,
        "categories": {},
    }

    for cat in CATEGORY_CONFIG:
        patterns = store.get(cat, [])
        before = len(patterns)
        result["total_before"] += before

        kept = [p for p in patterns if p.get("count", 0) >= min_count]
        pruned_count = before - len(kept)
        result["pruned_by_count"] += pruned_count
        pruned_decay = 0

        if decay_days > 0 and kept:
            decay_kept: list[dict[str, Any]] = []
            for p in kept:
                last_seen_str = p.get("last_seen", "")
                if not last_seen_str:
                    # Legacy entry without timestamp — keep as-is for backward compat
                    decay_kept.append(p)
                    continue
                try:
                    last_seen_dt = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
                    age_seconds = (now - last_seen_dt).total_seconds()
                    # Adaptive window: high-frequency patterns get longer retention.
                    # Each occurrence (up to 90) adds 7 days to the base decay_days.
                    count = p.get("count", 0)
                    base_window = decay_days + min(count, 90) * 7
                    max_window = 365  # Never retain patterns longer than 1 year regardless of frequency
                    effective_window = min(base_window, max_window)
                    adaptive_window = 86400.0 * effective_window

                    if effective_window < base_window:
                        _log("event=adaptive_window_capped cat={} skill={} count={} base_window={}d capped_to={}d",
                             cat, p.get("skill", "?"), count, base_window, effective_window)

                    if age_seconds >= adaptive_window:
                        _log("event=decay_prune cat={} skill={} count={} age={:.0f}d window={:.0f}d",
                             cat, p.get("skill", "?"), count,
                             age_seconds / 86400.0, adaptive_window / 86400.0)
                        continue
                except (ValueError, TypeError):
                    pass
                decay_kept.append(p)
            pruned_decay = len(kept) - len(decay_kept)
            result["pruned_by_decay"] += pruned_decay
            if pruned_decay > 0:
                _log("event=decay_prune_summary cat={} pruned={} kept={}",
                     cat, pruned_decay, len(decay_kept))
            kept = decay_kept

        pruned_total = before - len(kept)
        result["total_pruned"] += pruned_total

        result["categories"][cat] = {
            "before": before,
            "pruned": pruned_total,
            "pruned_by_count": pruned_count,
            "pruned_by_decay": pruned_decay if decay_days > 0 else 0,
            "after": len(kept),
        }

        if apply:
            store[cat] = kept

    result["total_after"] = result["total_before"] - result["total_pruned"]

    if apply:
        _save_store(store, root)

    return result


def success_maintain(
    root: Path | None = None,
    decay_days: int = 90,
    apply: bool = False,
) -> dict[str, Any]:
    """Prune success patterns not seen in ``decay_days`` days.

    In dry-run mode (default), reports what would be pruned.
    """
    try:
        store = _load_success_store(root)
        patterns: list[dict[str, Any]] = store.get("patterns", [])
        now = datetime.now(timezone.utc)

        before = len(patterns)
        kept: list[dict[str, Any]] = []
        window_seconds = float(decay_days) * 86400.0

        for pat in patterns:
            last_seen_str = pat.get("last_seen", "")
            if not last_seen_str:
                kept.append(pat)
                continue
            try:
                last_seen_dt = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
                age = (now - last_seen_dt).total_seconds()
                if age >= window_seconds:
                    _log("event=success_maintain_prune skill={} op={} age={:.0f}d window={}d",
                         pat.get("skill", "?"), pat.get("operation", "?"),
                         age / 86400.0, decay_days)
                    continue
            except (ValueError, TypeError):
                pass
            kept.append(pat)

        pruned = before - len(kept)
        if apply:
            store["patterns"] = kept
            _save_success_store(store, root)

        result: dict[str, Any] = {
            "status": "ok",
            "applied": apply,
            "before": before,
            "pruned": pruned,
            "after": len(kept),
            "decay_days": decay_days,
        }
        return result
    except Exception as exc:
        _log("event=success_maintain result=error exception={}", exc)
        return {"status": "error", "applied": apply, "error": str(exc)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gcl_reflexion.py",
        description="Layer 2: Reflexion Memory — failure pattern extraction, store, report, maintain.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # extract
    ext_p = sub.add_parser("extract", help="Extract failure pattern from a GCL trace JSON")
    ext_p.add_argument("--trace", required=True, help="Path to GCL trace JSON file")
    ext_p.add_argument("--json", action="store_true", help="Output as JSON")

    # store
    store_p = sub.add_parser("store", help="Store a failure pattern (from --json or --trace)")
    store_p.add_argument("--trace", help="Path to GCL trace JSON file (extracts and stores)")
    store_p.add_argument("--json", help="Pattern as JSON string")
    store_p.add_argument("--reflexion-root", help="Override reflexion root")

    # report (A1.5: dual output — failure + success)
    report_p = sub.add_parser("report", help="Regenerate docs/failure-patterns.md AND docs/success-patterns.md")
    report_p.add_argument("--reflexion-root", help="Override reflexion root")
    report_p.add_argument("--sort-by", choices=["weighted", "count"], default="weighted",
                          help="Sort order: 'weighted' (time-decayed, default) or 'count' (raw frequency)")

    success_report_p = sub.add_parser(
        "success-report",
        help="Regenerate docs/success-patterns.md (R4 hard-won PASS)",
    )
    success_report_p.add_argument("--reflexion-root", help="Override reflexion root")
    success_report_p.add_argument("--output", help="Override output path")
    success_report_p.add_argument("--sort-by", choices=["weighted", "count"], default="weighted",
                                  help="Sort order within each capture_reason group")

    # retrieve (R2)
    ret_p = sub.add_parser("retrieve", help="Retrieve failure patterns for pre-flight injection")
    ret_p.add_argument("--skill", required=True, help="Skill name (e.g. alicloud-ecs-ops)")
    ret_p.add_argument("--operation", default=None, help="Optional operation filter")
    ret_p.add_argument("--top-k", type=int, default=5)
    ret_p.add_argument("--min-count", type=int, default=1)
    ret_p.add_argument("--format", choices=["json", "text"], default="json")
    ret_p.add_argument("--max-chars", type=int, default=800)
    ret_p.add_argument("--reflexion-root", help="Override reflexion root")
    ret_p.add_argument("--resource-group-id", default=None,
                       help="Hard-filter patterns by resource_group_id (context)")
    ret_p.add_argument("--tags-json", default=None,
                       help="JSON array of {Key,Value} pairs to filter context.tags")

    # maintain
    maint_p = sub.add_parser("maintain", help="Prune low-frequency and/or stale patterns")
    maint_p.add_argument("--min-count", type=int, default=MIN_PATTERN_COUNT,
                         help=f"Minimum count threshold (default: {MIN_PATTERN_COUNT})")
    maint_p.add_argument("--decay-days", type=int, default=0,
                         help="Prune patterns not seen in this many days (0=disable time-based pruning)")
    maint_p.add_argument("--success-decay-days", type=int, default=0,
                         help="Prune success patterns not seen in this many days (0=disable)")
    maint_p.add_argument("--apply", action="store_true", help="Actually prune (default: dry-run)")
    maint_p.add_argument("--reflexion-root", help="Override reflexion root")

    # success-store (A1.4)
    ss_p = sub.add_parser("success-store", help="Store a hard-won PASS success pattern")
    ss_p.add_argument("--trace", required=True, help="Path to GCL trace JSON file")
    ss_p.add_argument("--reflexion-root", help="Override reflexion root")

    agg_p = sub.add_parser(
        "aggregate-generalized",
        help="R5: rebuild generalized_cli cross-product traps from cli_parameter",
    )
    agg_p.add_argument(
        "--min-skills",
        type=int,
        default=CROSS_SKILL_MIN_SKILLS_DEFAULT,
        help=f"Distinct skills required per normalized_key (default: {CROSS_SKILL_MIN_SKILLS_DEFAULT})",
    )
    agg_p.add_argument("--min-count", type=int, default=1)
    agg_p.add_argument("--apply", action="store_true", help="Write generalized_cli (default: dry-run)")
    agg_p.add_argument("--reflexion-root", help="Override reflexion root")

    # store-wrapper-lite (plan B)
    swl_p = sub.add_parser("store-wrapper-lite", help="Store allowlisted wrapper failure into Layer 2")
    swl_p.add_argument("--skill", required=True, help="Skill tag (e.g. alicloud-ecs-ops)")
    swl_p.add_argument("--trace-file", required=True, help="Path to local wrapper trace JSON")
    swl_p.add_argument("--reflexion-root", help="Override reflexion root")
    swl_p.add_argument("--resource-group-id", default=None,
                       help="Forwarded to reflexion_extract_wrapper_lite for context")
    swl_p.add_argument("--tags-json", default=None,
                       help="JSON array of strings (Key:Value) for context.tags")
    swl_p.add_argument("--missing-dimensions", default=None,
                       choices=["true", "false"],
                       help="Explicit missing_dimensions signal (true/false)")

    # promote-from-memory (plan C)
    pfm_p = sub.add_parser(
        "promote-from-memory",
        help="Aggregate failed wrapper L1 entries into Layer 2 (reconcile counts)",
    )
    pfm_p.add_argument("--memory-root", required=True, help="Layer 1 memory root (.runtime/memory)")
    pfm_p.add_argument("--min-count", type=int, default=MIN_PATTERN_COUNT,
                       help=f"Minimum L1 occurrences to promote (default: {MIN_PATTERN_COUNT})")
    pfm_p.add_argument("--apply", action="store_true", help="Write reconciled patterns (default: dry-run)")
    pfm_p.add_argument("--reflexion-root", help="Override reflexion root")

    return p


def _resolve_root(args: argparse.Namespace) -> Path | None:
    if hasattr(args, "reflexion_root") and args.reflexion_root:
        return Path(args.reflexion_root)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    root = _resolve_root(args)

    if args.command == "extract":
        try:
            trace = json.loads(Path(args.trace).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[ERROR] failed to load trace: {e}", file=sys.stderr)
            return 1
        pattern = reflexion_extract(trace)
        if pattern is None:
            print("(no failure pattern found)")
            return 0
        if args.json:
            print(json.dumps(pattern, indent=2, ensure_ascii=False))
        else:
            print(f"Category: {pattern['category']}")
            for k, v in pattern.items():
                if k != "category" and v:
                    print(f"  {k}: {v}")
        return 0

    elif args.command == "store":
        if args.trace:
            try:
                trace = json.loads(Path(args.trace).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                print(f"[ERROR] failed to load trace: {e}", file=sys.stderr)
                return 1
            pattern = reflexion_extract(trace)
        elif args.json:
            pattern = json.loads(args.json)
        else:
            _log("event=store_error reason=missing_input")
            return 1

        rc = reflexion_store(pattern, root=root)
        if rc == 0:
            _log("event=seed_store result=success")
        return rc

    elif args.command == "success-store":
        # Load trace, extract _success_pattern_payload, store it
        try:
            trace = json.loads(Path(args.trace).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[ERROR] failed to load trace: {e}", file=sys.stderr)
            return 1
        success_payload = trace.get("_success_pattern_payload")
        if not success_payload:
            _log("event=success_store result=skipped reason=no_payload")
            return 0
        rc = success_store(success_payload, root=root)
        if rc == 0:
            _log("event=success_store result=success")
        return rc

    elif args.command == "report":
        # A1.5: dual output — failure patterns + success patterns in one call
        rc = reflexion_report(root=root, sort_by=args.sort_by)
        if rc == 0:
            rc = success_report(root=root)
        return rc

    elif args.command == "success-report":
        out = Path(args.output) if getattr(args, "output", None) else None
        return success_report(root=root, output_path=out, sort_by=args.sort_by)

    elif args.command == "retrieve":
        tags_json = getattr(args, "tags_json", None)
        tag_filter = _parse_tags_json(tags_json)
        patterns = reflexion_retrieve(
            skill=args.skill,
            operation=args.operation,
            top_k=args.top_k,
            root=root,
            min_count=args.min_count,
            resource_group_id=getattr(args, "resource_group_id", None),
            tag_filter=tag_filter,
        )
        if args.format == "text":
            print(format_known_traps(patterns, max_chars=args.max_chars))
        else:
            print(json.dumps(patterns, indent=2, ensure_ascii=False))
        return 0

    elif args.command == "maintain":
        result = reflexion_maintain(
            root=root,
            min_count=args.min_count,
            decay_days=args.decay_days,
            apply=args.apply,
        )
        mode = "APPLY" if args.apply else "DRY-RUN"
        parts = []
        if result["pruned_by_count"] > 0:
            parts.append(f"low-count={result['pruned_by_count']}")
        if result["pruned_by_decay"] > 0:
            parts.append(f"decay(>{args.decay_days}d)={result['pruned_by_decay']}")
        detail = f"({', '.join(parts)}) " if parts else ""
        print(f"[REFLEXION] maintain ({mode}): {result['total_before']} → {result['total_after']} "
              f"{detail}(pruned {result['total_pruned']})")
        for cat, info in result["categories"].items():
            if info["pruned"] > 0:
                tag = ""
                if info.get("pruned_by_decay", 0) > 0:
                    tag = f" (decay={info['pruned_by_decay']}, low-count={info['pruned_by_count']})"
                elif info.get("pruned_by_count", 0) > 0:
                    tag = f" (low-count={info['pruned_by_count']})"
                print(f"  {cat}: {info['before']} → {info['after']} (pruned {info['pruned']}){tag}")

        # A3.1 extend: success pattern TTL
        success_decay = args.success_decay_days
        if success_decay > 0:
            s_result = success_maintain(
                root=root,
                decay_days=success_decay,
                apply=args.apply,
            )
            s_mode = "APPLY" if args.apply else "DRY-RUN"
            print(f"[REFLEXION] success-maintain ({s_mode}): "
                  f"{s_result.get('before', 0)} → {s_result.get('after', 0)} "
                  f"(pruned {s_result.get('pruned', 0)}, decay_days={success_decay})")
        return 0

    elif args.command == "aggregate-generalized":
        result = reflexion_aggregate_generalized(
            root=root,
            min_skills=args.min_skills,
            min_count=args.min_count,
            apply=args.apply,
        )
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(
            f"[REFLEXION] aggregate-generalized ({mode}): "
            f"groups={result['groups_scanned']} "
            f"{result['generalized_before']} → {result['generalized_after']} "
            f"(min_skills={result['min_skills']})"
        )
        return 0

    elif args.command == "store-wrapper-lite":
        tags_json = getattr(args, "tags_json", None)
        tags_list = _parse_tags_string_list(tags_json)
        missing_raw = getattr(args, "missing_dimensions", None)
        missing_bool: bool | None
        if missing_raw is None:
            missing_bool = None
        elif str(missing_raw).lower() == "true":
            missing_bool = True
        else:
            missing_bool = False
        rc = reflexion_store_wrapper_lite(
            skill=args.skill,
            trace_path=Path(args.trace_file),
            root=root,
            resource_group_id=getattr(args, "resource_group_id", None),
            tags=tags_list,
            missing_dimensions=missing_bool,
        )
        if rc == 0:
            _log("event=store_wrapper_lite result=success skill={}", args.skill)
        return rc

    elif args.command == "promote-from-memory":
        result = reflexion_promote_from_memory(
            memory_root=Path(args.memory_root),
            reflexion_root=root,
            min_count=args.min_count,
            apply=args.apply,
        )
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(
            f"[REFLEXION] promote-from-memory ({mode}): "
            f"scanned={result.get('scanned_entries', 0)} "
            f"failed_wrapper={result.get('failed_wrapper', 0)} "
            f"eligible={result.get('eligible_keys', 0)} "
            f"promoted={result.get('promoted', 0)} "
            f"reconciled={result.get('reconciled', 0)} "
            f"skipped_low={result.get('skipped_low_count', 0)}"
        )
        if result.get("status") == "skipped":
            print(f"  reason: {result.get('reason', 'unknown')}", file=sys.stderr)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
