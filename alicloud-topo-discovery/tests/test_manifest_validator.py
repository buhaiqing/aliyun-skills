"""Tests for manifest.json schema validation."""
import copy

import pytest

from scripts.lib.manifest_validator import ManifestValidationError, ManifestValidator

# A complete, valid manifest used as the base for "mutate one field" tests
VALID_MANIFEST = {
    "schema_version": "1.0",
    "generator": "alicloud-topo-discovery",
    "generator_version": "1.0.0",
    "generated_at": "2026-06-04T15:00:00Z",
    "account_id": "1234567890",
    "region": "cn-hangzhou",
    "scope": "vpc-xxx",
    "provider_version": "1.220.0",
    "resource_count": 47,
    "by_type": {"vpc": 1, "vswitch": 3},
    "sensitive_masked": ["rds.password"],
    "unsupported_types": [],
    "import_ids_stable": True,
    "execution_time_ms": 12345,
}


@pytest.fixture
def validator():
    """Returns a fresh ManifestValidator instance per test."""
    return ManifestValidator()


def test_valid_manifest_passes(validator):
    """A complete, valid manifest should pass validation."""
    validator.validate(VALID_MANIFEST)  # should not raise


def test_missing_required_field_fails(validator):
    """Missing a required field must fail validation with field in error."""
    invalid = copy.deepcopy(VALID_MANIFEST)
    del invalid["schema_version"]
    with pytest.raises(ManifestValidationError) as exc_info:
        validator.validate(invalid)
    assert "schema_version" in str(exc_info.value)


def test_wrong_schema_version_fails(validator):
    """schema_version other than '1.0' must fail (locked const)."""
    invalid = copy.deepcopy(VALID_MANIFEST)
    invalid["schema_version"] = "2.0"
    with pytest.raises(ManifestValidationError):
        validator.validate(invalid)


def test_wrong_generator_fails(validator):
    """generator must be exactly 'alicloud-topo-discovery'."""
    invalid = copy.deepcopy(VALID_MANIFEST)
    invalid["generator"] = "some-other-tool"
    with pytest.raises(ManifestValidationError):
        validator.validate(invalid)


def test_account_id_must_be_string(validator):
    """account_id must be a string, not int (Aliyun returns as string)."""
    invalid = copy.deepcopy(VALID_MANIFEST)
    invalid["account_id"] = 1234567890  # int instead of string
    with pytest.raises(ManifestValidationError):
        validator.validate(invalid)


def test_resource_count_must_be_non_negative(validator):
    """resource_count must be >= 0."""
    invalid = copy.deepcopy(VALID_MANIFEST)
    invalid["resource_count"] = -1
    with pytest.raises(ManifestValidationError):
        validator.validate(invalid)


def test_import_ids_stable_must_be_bool(validator):
    """import_ids_stable must be boolean, not string."""
    invalid = copy.deepcopy(VALID_MANIFEST)
    invalid["import_ids_stable"] = "true"  # string instead of bool
    with pytest.raises(ManifestValidationError):
        validator.validate(invalid)


def test_optional_role_arn_accepted(validator):
    """role_arn is optional; when present must be string with ARN format."""
    with_arn = copy.deepcopy(VALID_MANIFEST)
    with_arn["role_arn"] = "arn:acs:ram::1234:role/TopologyReader"
    validator.validate(with_arn)  # should not raise


def test_invalid_role_arn_format_fails(validator):
    """role_arn must match ARN pattern when present."""
    invalid = copy.deepcopy(VALID_MANIFEST)
    invalid["role_arn"] = "not-an-arn"
    with pytest.raises(ManifestValidationError):
        validator.validate(invalid)


def test_invalid_manifest_raises_with_field_path(validator):
    """Error message should include the field path for debugging."""
    invalid = copy.deepcopy(VALID_MANIFEST)
    invalid["region"] = ""  # empty string violates minLength: 1
    with pytest.raises(ManifestValidationError) as exc_info:
        validator.validate(invalid)
    assert "region" in str(exc_info.value)


def test_additional_properties_rejected(validator):
    """additionalProperties: false means unknown fields are rejected."""
    invalid = copy.deepcopy(VALID_MANIFEST)
    invalid["unknown_field"] = "should-fail"
    with pytest.raises(ManifestValidationError):
        validator.validate(invalid)
