"""Manage Aliyun Terraform provider version locking.

Generates provider.tf blocks with version pinned and credentials sourced
from environment variables (NEVER hardcoded).

Phase 1 strategy:
- Default version: 1.220.0 (current stable as of 2026-06)
- Lock format: pessimistic constraint (~>) to allow patch updates only
- Credentials: sourced from ALIBABA_CLOUD_ACCESS_KEY_ID / ACCESS_KEY_SECRET env vars
- NEVER output AK patterns (LTAI*, AKIA*) in any path
"""
import re
from typing import Optional


# Current stable Aliyun Provider version (update when Aliyun releases new stable)
DEFAULT_PROVIDER_VERSION = "1.220.0"

_SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def _validate_version(version: str) -> None:
    """Raise ValueError if not a valid semver string."""
    if not isinstance(version, str) or not _SEMVER_RE.match(version):
        raise ValueError(
            f"Invalid version '{version}': must be semver (e.g. '1.220.0')"
        )


# Credential patterns that MUST NOT appear in generated HCL (security check)
_FORBIDDEN_PATTERNS = [
    re.compile(r"LTAI[A-Za-z0-9]{10,}"),
    re.compile(r"AKIA[A-Za-z0-9]{10,}"),
    re.compile(r"access_key\s*=\s*\"[^\"]+\""),
]


def generate_provider_block(
    version: str = DEFAULT_PROVIDER_VERSION,
    region: str = "cn-hangzhou",
    profile: Optional[str] = None,
) -> str:
    """Generate a Terraform provider block as a string.

    Uses pessimistic version constraint (~>) for safe patch-only updates.
    Credentials are NEVER hardcoded — they come from env vars.

    Args:
        version: Aliyun Provider version (default: DEFAULT_PROVIDER_VERSION)
        region: Default region (default: cn-hangzhou)
        profile: Optional named profile from ~/.aliyun/config.json

    Returns:
        Multi-line HCL provider block string.

    Raises:
        ValueError: if version is not a valid semver string.
    """
    _validate_version(version)
    lines = [
        "terraform {",
        "  required_providers {",
        '    alicloud = {',
        '      source  = "alibaba/alicloud"',
        f"      version = \"~> {version}\"",
        "    }",
        "  }",
        "}",
        "",
        'provider "alicloud" {',
        f'  region  = "{region}"',
    ]
    if profile:
        lines.append(f'  profile = "{profile}"')
    lines.extend([
        "",
        "  # Credentials sourced from environment variables (NEVER hardcoded).",
        "  # Required: ALIBABA_CLOUD_ACCESS_KEY_ID, ALIBABA_CLOUD_ACCESS_KEY_SECRET",
        "  # Optional: ALIBABA_CLOUD_SESSION_TOKEN (for STS temporary credentials)",
        "}",
        "",
    ])
    block = "\n".join(lines)

    # Security sanity check: scan output for leaked credential patterns
    for pattern in _FORBIDDEN_PATTERNS:
        match = pattern.search(block)
        if match:
            raise ValueError(
                f"Security violation: generated provider block contains "
                f"forbidden pattern '{match.group()}'. This should never happen."
            )

    return block


class ProviderLocker:
    """Manages the Aliyun Provider version for an export run.

    Usage:
        locker = ProviderLocker(version="1.220.0")
        block = locker.render_block(region="cn-hangzhou")
    """

    def __init__(self, version: str = DEFAULT_PROVIDER_VERSION):
        _validate_version(version)
        self.version = version

    def render_block(
        self, region: str = "cn-hangzhou", profile: Optional[str] = None
    ) -> str:
        """Render the provider block with this locker's version."""
        return generate_provider_block(
            version=self.version, region=region, profile=profile
        )
