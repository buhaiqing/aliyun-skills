"""CLI wrapper with read-only protection and error handling."""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from typing import Any

READONLY_PREFIXES = ("Describe", "List", "Get")

# Defense in depth: reject shell metachars at the API boundary even though
# we use shell=True downstream.
_SHELL_METACHARS = re.compile(r"[;&|`$<>\\\n\r]")


def is_readonly_action(action: str) -> bool:
    """Check if an API action is read-only."""
    action_lower = action.lower()
    return any(action_lower.startswith(prefix.lower()) for prefix in READONLY_PREFIXES)


def _extract_aliyun_action(cmd: str) -> str | None:
    """Locate the 'aliyun' token in cmd and return the action immediately after it.

    Handles arbitrary leading tokens (env vars, comments, redirections) by
    scanning for the literal 'aliyun' instead of assuming a fixed positional layout.
    """
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        return None
    for i, tok in enumerate(tokens):
        if tok == "aliyun" and i + 2 < len(tokens):
            return tokens[i + 2]
    return None


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
    """Execute an aliyun CLI command with read-only protection."""
    dangerous = _scan_for_dangerous_args(cmd)
    if dangerous is not None:
        raise ValueError(
            f"Refusing command with shell metacharacter: {repr(dangerous)}. "
            f"This is a read-only audit module."
        )

    action = _extract_aliyun_action(cmd)
    if action is None:
        raise ValueError(
            f"Could not locate aliyun action in cmd. "
            f"Expected 'aliyun <product> <Action>' pattern."
        )

    if not is_readonly_action(action):
        raise ValueError(
            f"Read-only module: '{action}' is a write action. "
            f"Only Describe*/List*/Get* are allowed."
        )

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
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response: {e}")


def _mask_credentials(text: str) -> str:
    """Mask AccessKey IDs and Secrets in output."""
    text = re.sub(r"LTAI\w{8,}", "LTAI****", text)
    text = re.sub(r'"access_key_secret"\s*:\s*"[^"]*"', '"access_key_secret": "****"', text)
    return text
