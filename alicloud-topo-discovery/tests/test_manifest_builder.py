"""Tests for manifest.json builder."""
import re

from scripts.lib.manifest_builder import ManifestBuilder


def test_build_minimal_manifest():
    """Build a manifest with only required fields."""
    builder = ManifestBuilder(
        account_id="1234567890",
        region="cn-hangzhou",
        scope="vpc-xxx",
        provider_version="1.220.0",
    )
    manifest = builder.build(
        resource_count=0,
        by_type={},
        sensitive_masked=[],
        unsupported_types=[],
        execution_time_ms=1000,
    )
    assert manifest["schema_version"] == "1.0"
    assert manifest["generator"] == "alicloud-topo-discovery"
    assert manifest["generator_version"] == "1.0.0"
    assert manifest["account_id"] == "1234567890"
    assert manifest["region"] == "cn-hangzhou"
    assert manifest["scope"] == "vpc-xxx"
    assert manifest["provider_version"] == "1.220.0"
    assert manifest["resource_count"] == 0
    assert manifest["import_ids_stable"] is True
    assert "generated_at" in manifest


def test_build_with_optional_fields():
    """Build a manifest with all optional fields."""
    builder = ManifestBuilder(
        account_id="1234567890",
        account_alias="prod-finance",
        role_arn="arn:acs:ram::1234:role/TopologyReader",
        region="cn-hangzhou",
        scope="all",
        provider_version="1.220.0",
    )
    manifest = builder.build(
        resource_count=47,
        by_type={"vpc": 1, "vswitch": 3, "ecs": 12},
        sensitive_masked=["rds.account_password"],
        unsupported_types=["fc.function_code"],
        execution_time_ms=12345,
    )
    assert manifest["account_alias"] == "prod-finance"
    assert manifest["role_arn"] == "arn:acs:ram::1234:role/TopologyReader"
    assert manifest["resource_count"] == 47
    assert manifest["by_type"] == {"vpc": 1, "vswitch": 3, "ecs": 12}
    assert manifest["sensitive_masked"] == ["rds.account_password"]
    assert manifest["unsupported_types"] == ["fc.function_code"]


def test_generated_at_is_iso8601_utc():
    """generated_at must be ISO 8601 UTC with Z suffix."""
    builder = ManifestBuilder(
        account_id="1234567890",
        region="cn-hangzhou",
        scope="vpc-xxx",
        provider_version="1.220.0",
    )
    manifest = builder.build(
        resource_count=0, by_type={}, sensitive_masked=[],
        unsupported_types=[], execution_time_ms=1000,
    )
    iso_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
    assert re.match(iso_pattern, manifest["generated_at"]), \
        f"got '{manifest['generated_at']}'"


def test_by_type_count_matches_resource_count():
    """Sum of by_type values equals resource_count (sanity check)."""
    builder = ManifestBuilder(
        account_id="1234567890",
        region="cn-hangzhou",
        scope="vpc-xxx",
        provider_version="1.220.0",
    )
    by_type = {"vpc": 1, "vswitch": 3, "ecs": 12, "rds": 2}
    total = sum(by_type.values())
    manifest = builder.build(
        resource_count=total,
        by_type=by_type,
        sensitive_masked=[],
        unsupported_types=[],
        execution_time_ms=1000,
    )
    assert sum(manifest["by_type"].values()) == manifest["resource_count"]


def test_import_ids_stable_defaults_to_true():
    """import_ids_stable is always True (we guarantee stability)."""
    builder = ManifestBuilder(
        account_id="1234567890",
        region="cn-hangzhou",
        scope="vpc-xxx",
        provider_version="1.220.0",
    )
    manifest = builder.build(
        resource_count=0, by_type={}, sensitive_masked=[],
        unsupported_types=[], execution_time_ms=1000,
    )
    assert manifest["import_ids_stable"] is True


def test_built_manifest_passes_validator():
    """A built manifest must validate against the canonical schema."""
    from scripts.lib.manifest_validator import ManifestValidator

    builder = ManifestBuilder(
        account_id="1234567890",
        region="cn-hangzhou",
        scope="vpc-xxx",
        provider_version="1.220.0",
    )
    manifest = builder.build(
        resource_count=5,
        by_type={"vpc": 1, "vswitch": 2, "ecs": 2},
        sensitive_masked=["rds.account_password"],
        unsupported_types=[],
        execution_time_ms=2000,
    )
    validator = ManifestValidator()
    validator.validate(manifest)  # raises on failure


def test_negative_resource_count_raises():
    """Negative resource_count raises ValueError."""
    builder = ManifestBuilder(
        account_id="1234567890",
        region="cn-hangzhou",
        scope="vpc-xxx",
        provider_version="1.220.0",
    )
    with __import__("pytest").raises(ValueError):
        builder.build(
            resource_count=-1, by_type={}, sensitive_masked=[],
            unsupported_types=[], execution_time_ms=0,
        )


def test_empty_string_account_id_raises():
    """Empty account_id raises ValueError."""
    with __import__("pytest").raises(ValueError):
        ManifestBuilder(
            account_id="",
            region="cn-hangzhou",
            scope="vpc-xxx",
            provider_version="1.220.0",
        )
