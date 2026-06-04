"""Build manifest.json dicts that conform to the canonical schema.

Single entry point: ManifestBuilder(...).build(...). Used by
export-hcl.py after scanning + HCL generation completes.

This module guarantees that any dict returned by .build() will pass
ManifestValidator().validate() without raising.
"""
from datetime import datetime, timezone
from typing import Optional

GENERATOR = "alicloud-topo-discovery"
GENERATOR_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"


class ManifestBuilder:
    """Builds a manifest.json dict for a single export run.

    Required: account_id, region, scope, provider_version.
    Optional: account_alias, role_arn.
    """

    def __init__(
        self,
        account_id: str,
        region: str,
        scope: str,
        provider_version: str,
        account_alias: Optional[str] = None,
        role_arn: Optional[str] = None,
    ):
        if not account_id or not isinstance(account_id, str):
            raise ValueError("account_id must be a non-empty string")
        if not region or not isinstance(region, str):
            raise ValueError("region must be a non-empty string")
        if not scope or not isinstance(scope, str):
            raise ValueError("scope must be a non-empty string")
        if not provider_version or not isinstance(provider_version, str):
            raise ValueError("provider_version must be a non-empty string")

        self.account_id = account_id
        self.account_alias = account_alias
        self.role_arn = role_arn
        self.region = region
        self.scope = scope
        self.provider_version = provider_version

    def build(
        self,
        resource_count: int,
        by_type: dict,
        sensitive_masked: list,
        unsupported_types: list,
        execution_time_ms: int,
    ) -> dict:
        """Build and return the manifest dict.

        Raises ValueError on invalid inputs.
        Returns a dict that conforms to manifest-schema.json v1.0.
        """
        if resource_count < 0:
            raise ValueError("resource_count must be >= 0")
        if execution_time_ms < 0:
            raise ValueError("execution_time_ms must be >= 0")
        if not isinstance(by_type, dict):
            raise TypeError("by_type must be a dict")
        if not isinstance(sensitive_masked, list):
            raise TypeError("sensitive_masked must be a list")
        if not isinstance(unsupported_types, list):
            raise TypeError("unsupported_types must be a list")

        # ISO 8601 UTC, Z suffix, no microseconds (matches date-time format)
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "generator": GENERATOR,
            "generator_version": GENERATOR_VERSION,
            "generated_at": generated_at,
            "account_id": self.account_id,
            "region": self.region,
            "scope": self.scope,
            "provider_version": self.provider_version,
            "resource_count": resource_count,
            "by_type": by_type,
            "sensitive_masked": sensitive_masked,
            "unsupported_types": unsupported_types,
            "import_ids_stable": True,
            "execution_time_ms": execution_time_ms,
        }

        # Optional fields added only when set
        if self.account_alias is not None:
            manifest["account_alias"] = self.account_alias
        if self.role_arn is not None:
            manifest["role_arn"] = self.role_arn

        return manifest
