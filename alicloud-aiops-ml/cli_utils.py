"""CLI wrapper with read-only protection and error handling."""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from typing import Any

READONLY_PREFIXES = ("Describe", "List", "Get")

# aliyun CLI v3 sub-commands that are read-only but don't follow the
# Describe*/List*/Get* convention. Each entry is a (product, subcommand) pair.
READONLY_SUBCOMMANDS = {
    ("oss", "ls"),
    ("oss", "stat"),
    ("oss", "list"),
}

# aliyun CLI v3 outputs JSON by default and rejects --output json.
# This flag is a no-op on v3 but required on older versions.
# We strip it to maintain compatibility with both.
_STRIP_FLAGS = {"--output", "json"}

# Defense in depth: reject shell metachars at the API boundary even though
# we use shell=True downstream.
_SHELL_METACHARS = re.compile(r"[;&|`$<>\\\n\r]")


def is_readonly_action(action: str) -> bool:
    """Check if an API action is read-only."""
    action_lower = action.lower()
    return any(action_lower.startswith(prefix.lower()) for prefix in READONLY_PREFIXES)


def _is_readonly_subcommand(product: str, subcommand: str) -> bool:
    """Check if a product+subcommand pair is a known read-only operation."""
    return (product.lower(), subcommand.lower()) in READONLY_SUBCOMMANDS


def _extract_aliyun_action(cmd: str) -> tuple[str | None, str | None]:
    """Locate the 'aliyun' token in cmd and return (product, action).

    Returns (None, None) if the pattern cannot be parsed.
    For 'aliyun ecs DescribeInstances' → ('ecs', 'DescribeInstances')
    For 'aliyun oss ls' → ('oss', 'ls')
    """
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return None, None
    for i, tok in enumerate(tokens):
        if tok != "aliyun":
            continue
        # Product is the token right after 'aliyun'
        product = tokens[i + 1] if i + 1 < len(tokens) else None
        if product is None:
            return None, None
        # Action is the first non-flag token after product
        for j in range(i + 2, len(tokens)):
            candidate = tokens[j]
            if not candidate.startswith("-"):
                return product, candidate
        return product, None
    return None, None


def _scan_for_dangerous_args(cmd: str) -> str | None:
    """Reject shell metacharacters in argument values before subprocess.run.

    Returns the first dangerous token found, or None if safe.
    """
    if _SHELL_METACHARS.search(cmd):
        match = _SHELL_METACHARS.search(cmd)
        return match.group(0) if match else cmd
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return cmd
    for tok in tokens:
        if _SHELL_METACHARS.search(tok):
            return tok
    return None


def cli_call(cmd: str, timeout: int = 30, parse_json: bool = True) -> dict[str, Any] | str | None:
    """Execute an aliyun CLI command with read-only protection.

    Strips --output json (no-op on aliyun CLI v3, required on older versions)
    for compatibility across CLI versions.
    """
    dangerous = _scan_for_dangerous_args(cmd)
    if dangerous is not None:
        raise ValueError(
            f"Refusing command with shell metacharacter: {repr(dangerous)}. "
            f"This is a read-only audit module."
        )

    product, action = _extract_aliyun_action(cmd)
    if product is None or action is None:
        raise ValueError(
            f"Could not locate aliyun action in cmd. "
            f"Expected 'aliyun <product> <Action>' pattern."
        )

    if not is_readonly_action(action) and not _is_readonly_subcommand(product, action):
        raise ValueError(
            f"Read-only module: '{action}' is a write action. "
            f"Only Describe*/List*/Get* are allowed."
        )

    # Strip --output json for aliyun CLI v3 compatibility.
    # v3 outputs JSON by default and rejects --output json.
    # We only strip the exact token pair "--output", "json" when adjacent.
    cmd = _strip_output_json(cmd)

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        if result.returncode != 0:
            stderr = _mask_credentials(result.stderr)
            raise RuntimeError(f"CLI failed (exit {result.returncode}): {stderr}")

        stdout = _mask_credentials(result.stdout)
        if not stdout.strip():
            return None
        if not parse_json:
            return stdout
        return json.loads(stdout)

    except subprocess.TimeoutExpired:
        safe_cmd = _mask_credentials(cmd.split("--", 1)[0].strip())
        raise RuntimeError(f"CLI timeout after {timeout}s: {safe_cmd} ...")
    except json.JSONDecodeError:
        raise RuntimeError("Invalid JSON response from aliyun CLI (output masked)")


def _strip_output_json(cmd: str) -> str:
    """Remove '--output json' from the command string.

    aliyun CLI v3 outputs JSON by default and rejects --output json.
    We strip it for compatibility while keeping the command valid for older versions
    that actually need it (those versions would need it added back).
    """
    import shlex as _shlex
    try:
        tokens = _shlex.split(cmd)
    except ValueError:
        return cmd
    result = []
    skip_next = False
    for tok in tokens:
        if skip_next:
            skip_next = False
            continue
        if tok == "--output":
            # Check if next token is "json" — if so, skip both
            idx = tokens.index(tok)
            if idx + 1 < len(tokens) and tokens[idx + 1] == "json":
                skip_next = True
                continue
        result.append(tok)
    return _shlex.join(result)


def _mask_credentials(text: str) -> str:
    """Mask AccessKey IDs and Secrets in output."""
    text = re.sub(r"LTAI\w{8,}", "LTAI****", text)
    text = re.sub(r'"access_key_secret"\s*:\s*"[^"]*"', '"access_key_secret": "****"', text)
    return text
