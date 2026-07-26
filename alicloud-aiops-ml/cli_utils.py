"""CLI wrapper with read-only protection and error handling."""
from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any

READONLY_PREFIXES = ("Describe", "List", "Get")


def is_readonly_action(action: str) -> bool:
    """Check if an API action is read-only."""
    action_lower = action.lower()
    return any(action_lower.startswith(prefix.lower()) for prefix in READONLY_PREFIXES)


def cli_call(cmd: str, timeout: int = 30, parse_json: bool = True) -> dict[str, Any] | str | None:
    """Execute an aliyun CLI command with read-only protection."""
    parts = cmd.split()
    if len(parts) >= 3:
        action = parts[2]
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
        raise RuntimeError(f"CLI timeout after {timeout}s: {cmd}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response: {e}")


def _mask_credentials(text: str) -> str:
    """Mask AccessKey IDs and Secrets in output."""
    text = re.sub(r"LTAI\w{8,}", "LTAI****", text)
    text = re.sub(r'"access_key_secret"\s*:\s*"[^"]*"', '"access_key_secret": "****"', text)
    return text
