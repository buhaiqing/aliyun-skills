"""Tests for sensitive field masker."""
import pytest
from scripts.lib.sensitive_masker import (
    SensitiveMasker,
    mask_value,
    SENSITIVE_FIELDS,
)


def test_sensitive_fields_registry_has_rds_and_ecs():
    """SENSITIVE_FIELDS must cover rds and ecs at minimum."""
    assert "rds" in SENSITIVE_FIELDS
    assert "ecs" in SENSITIVE_FIELDS


def test_mask_rds_password_value():
    """RDS password values must be replaced with variable ref."""
    masker = SensitiveMasker()
    masked, field_path = masker.mask_field("rds", "AccountPassword", "secret123")
    assert masked == "${var.rds_password}"
    assert field_path == "rds.account_password"


def test_mask_ecs_password_value():
    """ECS password values must be replaced with variable ref."""
    masker = SensitiveMasker()
    masked, field_path = masker.mask_field("ecs", "Password", "P@ssw0rd")
    assert masked == "${var.ecs_password}"
    assert field_path == "ecs.password"


def test_mask_vpc_field_no_sensitive():
    """Non-sensitive VPC fields pass through unchanged."""
    masker = SensitiveMasker()
    masked, field_path = masker.mask_field("vpc", "VpcName", "my-vpc")
    assert masked == "my-vpc"
    assert field_path is None


def test_mask_unknown_resource_type_passes_through():
    """Unknown resource types pass through unchanged."""
    masker = SensitiveMasker()
    masked, field_path = masker.mask_field("unknown_type", "Password", "x")
    assert masked == "x"
    assert field_path is None


def test_mask_field_returns_field_path_when_masking():
    """When masking happens, field_path is set (for manifest tracking)."""
    masker = SensitiveMasker()
    _, field_path = masker.mask_field("rds", "AccountPassword", "secret")
    assert field_path is not None
    assert "password" in field_path.lower()


def test_mask_field_case_insensitive_match():
    """Field name matching is case-insensitive (Aliyun API uses PascalCase)."""
    masker = SensitiveMasker()
    masked, _ = masker.mask_field("rds", "accountpassword", "secret")
    assert masked == "${var.rds_password}"


def test_mask_value_helper_function():
    """mask_value() helper works without instantiating SensitiveMasker."""
    result = mask_value("rds", "AccountPassword", "secret")
    assert result == "${var.rds_password}"


def test_mask_value_non_sensitive_returns_original():
    """mask_value() returns original value for non-sensitive fields."""
    result = mask_value("vpc", "VpcName", "my-vpc")
    assert result == "my-vpc"


def test_hcl_line_sensitive_includes_sensitive_directive():
    """Sensitive fields produce a 'sensitive = true' line."""
    masker = SensitiveMasker()
    hcl_line = masker.hcl_line("rds", "AccountPassword", "secret", indent=2)
    assert "var.rds_password" in hcl_line
    assert "sensitive = true" in hcl_line


def test_hcl_line_non_sensitive_no_sensitive_directive():
    """Non-sensitive HCL lines have no 'sensitive' marker."""
    masker = SensitiveMasker()
    hcl_line = masker.hcl_line("vpc", "VpcName", "my-vpc", indent=2)
    assert "my-vpc" in hcl_line
    assert "sensitive" not in hcl_line


def test_hcl_literal_bool():
    """Boolean values are rendered as HCL true/false."""
    masker = SensitiveMasker()
    assert masker._hcl_literal(True) == "true"
    assert masker._hcl_literal(False) == "false"


def test_hcl_literal_null():
    """None is rendered as HCL null."""
    masker = SensitiveMasker()
    assert masker._hcl_literal(None) == "null"


def test_hcl_literal_string_escapes_quotes():
    """String values with quotes are properly escaped."""
    masker = SensitiveMasker()
    result = masker._hcl_literal('hello "world"')
    assert result == '"hello \\"world\\""'


def test_hcl_literal_int():
    """Integer values render as bare numbers."""
    masker = SensitiveMasker()
    assert masker._hcl_literal(42) == "42"
    assert masker._hcl_literal(3.14) == "3.14"
