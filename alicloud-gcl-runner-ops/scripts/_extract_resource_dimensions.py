#!/usr/bin/env python3
"""
_extract_resource_dimensions.py — Parse ResourceGroupId and Tags from CLI params.

Pure-function module: takes a list of CLI tokens, returns a normalized dict.
Three Tag formats are supported (priority order, exclusive):

1. **RepeatList** (Aliyun CLI canonical):
       --Tag.1.Key env --Tag.1.Value prod --Tag.2.Key team --Tag.2.Value core
2. **Single key=value string** (legacy):
       --Tag env=prod --Tag team=core
3. **JSON array** (some products / SDK wrappers):
       --Tags '[{"key":"env","value":"prod"},{"key":"team","value":"core"}]'

Priority rules:
  - RepeatList wins if any `--Tag.N.Key` or `--Tag.N.Value` token is seen.
  - Otherwise single key=value is parsed.
  - Otherwise `--Tags` JSON is parsed.
  - All three are mutually exclusive in one call.

Failure modes (NEVER raise; always return a dict):
  - Parse error → populate ``tags_raw`` with the offending raw input,
    set ``tags`` to ``[]``.
  - Malformed input → graceful ``{}``-style fields.

Python 3.10+ stdlib only. No external dependencies.
"""

from __future__ import annotations

import json
import re
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Token prefixes for the three Tag formats.
# We strip a leading "k=" or "v=" for single KV form.
_REPEATED_KEY_PREFIX = "--Tag."
_REPEATED_KEY_RE = re.compile(r"^--Tag\.(\d+)\.Key$")
_REPEATED_VALUE_RE = re.compile(r"^--Tag\.(\d+)\.Value$")
_SINGLE_KV_PREFIX = "--Tag"  # exact token, NOT a prefix (avoid --Tag.* collision)
_JSON_TAGS_PREFIX = "--Tags"  # exact token

_RESOURCE_GROUP_FLAG = "--ResourceGroupId"

# Sentinel for "we tried but failed" — keeps callers from misinterpreting
# an absent field as "not present in input".
_PARSE_FAILED = "__PARSE_FAILED__"

# Warning + suggestion templates for the missing_dimensions case.
# Kept in English so trace JSON / logs / Critic verdicts stay consistent.
MISSING_DIMENSIONS_WARNING = (
    "Caller did not specify --ResourceGroupId or --Tag. "
    "The Aliyun API will return ALL resources in the region "
    "(no default resource-group filtering), which may cause "
    "token bloat, latency, and throttle risk."
)
MISSING_DIMENSIONS_SUGGESTION = (
    "Re-run with explicit --ResourceGroupId rg-xxx and/or "
    "--Tag.1.Key <k> --Tag.1.Value <v> to scope the query."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract(params: list[str]) -> dict[str, Any]:
    """Extract resource_group_id and tags from a CLI parameter list.

    Args:
        params: List of CLI tokens, e.g.
                ``['--RegionId', 'cn-hz', '--ResourceGroupId', 'rg-abc',
                   '--Tag.1.Key', 'env', '--Tag.1.Value', 'prod']``

    Returns:
        Dict with keys:
          - ``resource_group_id``: str | None
          - ``tags``: ``[{"key": str, "value": str}, ...]`` (empty list if absent)
          - ``tags_raw``: str | None
              * Set to the offending raw input if a parse error occurred
                (so forensic consumers can see what was tried).
              * ``None`` when no tags were present at all.
              * ``None`` when tags were parsed successfully (use ``tags``).
          - ``missing_dimensions``: bool
              * ``True`` ⟺ resource_group_id is None AND tags is empty.
                Caller did NOT specify any resource filtering dimension.
                Most Aliyun products do not support "default resource group
                filtering" — without RG/Tags the API returns the entire
                account's resources in the region, which is a frequent
                source of token bloat, latency, and throttle risk.
              * ``False`` ⟺ at least one of RG / Tags is set.
          - ``warning``: str | None
              * Set to a human-readable explanation when ``missing_dimensions``
                is ``True``. ``None`` otherwise.
              * Carried in trace JSON for log / UI inspection; NOT mirrored
                to Langfuse (keeps remote payload compact — only the
                boolean ``missing_dimensions`` is mirrored).
          - ``suggestion``: str | None
              * Set to an actionable remediation hint when
                ``missing_dimensions`` is ``True``. ``None`` otherwise.
              * Designed for LLM self-correction: an Agent reading this can
                splice it directly into a Critic prompt or retry message.

    Never raises. All exceptions are caught and reflected in the return value.
    """
    resource_group_id: str | None = None
    tags: list[dict[str, str]] = []
    tags_raw: str | None = None

    if not params:
        return {
            "resource_group_id": None,
            "tags": [],
            "tags_raw": None,
            "missing_dimensions": True,
            "warning": MISSING_DIMENSIONS_WARNING,
            "suggestion": MISSING_DIMENSIONS_SUGGESTION,
        }

    # First pass: detect which Tag format is in use.
    # Priority: RepeatList > single KV > JSON array.
    has_repeatlist = False
    has_single_kv = False
    has_json_array = False
    single_kv_tokens: list[str] = []
    json_array_value: str | None = None

    i = 0
    n = len(params)
    while i < n:
        tok = params[i]
        if _REPEATED_KEY_RE.match(tok) or _REPEATED_VALUE_RE.match(tok):
            has_repeatlist = True
            # consume key OR value + its argument
            i += 2
            continue
        if tok == _SINGLE_KV_PREFIX and i + 1 < n:
            has_single_kv = True
            single_kv_tokens.append(params[i + 1])
            i += 2
            continue
        if tok == _JSON_TAGS_PREFIX and i + 1 < n:
            has_json_array = True
            json_array_value = params[i + 1]
            i += 2
            continue
        # Skip other flags and their values heuristically:
        # Long-option flag followed by a value that doesn't start with '-'
        # — but we don't try to be perfect here; we only care about the
        # tokens above. The general flow won't consume them.
        i += 1

    # ResourceGroupId (single-value flag).
    for j, tok in enumerate(params):
        if tok == _RESOURCE_GROUP_FLAG and j + 1 < len(params):
            resource_group_id = params[j + 1]
            break

    # Tag parsing — by priority.
    if has_repeatlist:
        tags = _parse_repeatlist(params)
    elif has_single_kv:
        tags, tags_raw = _parse_single_kv_tokens(single_kv_tokens)
    elif has_json_array:
        tags, tags_raw = _parse_json_array(json_array_value or "")

    # missing_dimensions flag: True when caller specified neither RG nor Tags.
    # Edge cases:
    #   - RG was set but Tag parsing failed → missing_dimensions=False
    #     (caller did try to filter; partial info is better than silent
    #     "missing everything" assertion).
    #   - Tags array is non-empty (after parsing) → False.
    #   - Both RG is None AND tags is empty → True.
    missing_dimensions = resource_group_id is None and len(tags) == 0

    # Warning + suggestion pair: only populated when the caller truly
    # skipped both dimensions (i.e. NOT on parser-failure fallback —
    # that path returns early before this point in practice, but we
    # gate explicitly here for safety).
    if missing_dimensions:
        warning = MISSING_DIMENSIONS_WARNING
        suggestion = MISSING_DIMENSIONS_SUGGESTION
    else:
        warning = None
        suggestion = None

    return {
        "resource_group_id": resource_group_id,
        "tags": tags,
        "tags_raw": tags_raw,
        "missing_dimensions": missing_dimensions,
        "warning": warning,
        "suggestion": suggestion,
    }


def extract_from_command(command: str) -> dict[str, Any]:
    """Convenience wrapper: tokenize a full aliyun command string, then extract.

    Strips the leading ``aliyun <product> <action>`` prefix if present
    (heuristic: first three whitespace-separated tokens when the first
    token is ``aliyun``).

    Example:
        >>> extract_from_command(
        ...     "aliyun ecs DescribeInstances --ResourceGroupId rg-x "
        ...     "--Tag.1.Key env --Tag.1.Value prod"
        ... )
        {'resource_group_id': 'rg-x',
         'tags': [{'key': 'env', 'value': 'prod'}],
         'tags_raw': None,
         'missing_dimensions': False,
         'warning': None,
         'suggestion': None}
    """
    if not command or not command.strip():
        return {
            "resource_group_id": None,
            "tags": [],
            "tags_raw": None,
            "missing_dimensions": True,
            "warning": MISSING_DIMENSIONS_WARNING,
            "suggestion": MISSING_DIMENSIONS_SUGGESTION,
        }

    tokens = command.strip().split()
    # Strip leading "aliyun <product> <action>" if present.
    if len(tokens) >= 3 and tokens[0] == "aliyun":
        tokens = tokens[3:]
    return extract(tokens)


# ---------------------------------------------------------------------------
# Tag format parsers
# ---------------------------------------------------------------------------


def _parse_repeatlist(params: list[str]) -> list[dict[str, str]]:
    """Parse ``--Tag.N.Key`` / ``--Tag.N.Value`` pairs into ordered list.

    Order is by N ascending. Missing key or value → that pair is dropped
    (we do NOT silently default to empty string).
    """
    pairs: dict[int, dict[str, str]] = {}
    i = 0
    n = len(params)
    while i < n:
        tok = params[i]
        m_key = _REPEATED_KEY_RE.match(tok)
        m_val = _REPEATED_VALUE_RE.match(tok)
        if m_key and i + 1 < n:
            idx = int(m_key.group(1))
            pairs.setdefault(idx, {})["key"] = params[i + 1]
            i += 2
            continue
        if m_val and i + 1 < n:
            idx = int(m_val.group(1))
            pairs.setdefault(idx, {})["value"] = params[i + 1]
            i += 2
            continue
        i += 1

    result: list[dict[str, str]] = []
    for idx in sorted(pairs.keys()):
        pair = pairs[idx]
        if "key" in pair and "value" in pair:
            result.append({"key": pair["key"], "value": pair["value"]})
    return result


def _parse_single_kv_tokens(
    kv_tokens: list[str],
) -> tuple[list[dict[str, str]], str | None]:
    """Parse one or more ``key=value`` strings.

    Splitting rule: first ``=`` separates key from value. This means values
    like ``https://x=y`` parse correctly as ``{'https://x', 'y'}``.

    On per-token parse failure, fall back: tags=[], tags_raw=<all tokens joined>.
    """
    if not kv_tokens:
        return [], None

    parsed: list[dict[str, str]] = []
    for tok in kv_tokens:
        if "=" not in tok:
            # Malformed single-KV; abort parsing, surface raw.
            return [], " ".join(kv_tokens)
        key, _, value = tok.partition("=")
        if not key:
            return [], " ".join(kv_tokens)
        parsed.append({"key": key, "value": value})

    return parsed, None


def _parse_json_array(
    raw: str,
) -> tuple[list[dict[str, str]], str | None]:
    """Parse a JSON array of ``{"key":..., "value":...}`` objects.

    Tolerates common field aliases (``Key``/``Value`` capitalisation).
    Falls back gracefully on JSON decode error or wrong shape.
    """
    if not raw:
        return [], raw or None

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return [], raw

    if not isinstance(data, list):
        return [], raw

    parsed: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            return [], raw  # mixed-shape array → bail
        # Accept both lowercase and capitalised keys.
        key = item.get("key") or item.get("Key")
        value = item.get("value") or item.get("Value")
        if key is None or value is None:
            return [], raw  # missing field → bail
        parsed.append({"key": str(key), "value": str(value)})

    return parsed, None


__all__ = ["extract", "extract_from_command"]
