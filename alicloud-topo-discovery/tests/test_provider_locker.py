"""Tests for Aliyun Terraform provider version locking."""
import re
import pytest
from scripts.lib.provider_locker import (
    ProviderLocker,
    DEFAULT_PROVIDER_VERSION,
    generate_provider_block,
    _validate_version,
)


def test_default_provider_version_format():
    """DEFAULT_PROVIDER_VERSION must be a valid semver string."""
    assert re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", DEFAULT_PROVIDER_VERSION)


def test_generate_provider_block_with_default():
    """Generate a provider block using the default version."""
    block = generate_provider_block()
    assert 'source  = "alibaba/alicloud"' in block
    assert f"~> {DEFAULT_PROVIDER_VERSION}" in block


def test_generate_provider_block_with_explicit_version():
    """Generate a provider block with explicit version override."""
    block = generate_provider_block(version="1.215.0")
    assert "1.215.0" in block


def test_generate_provider_block_contains_required_fields():
    """Provider block must declare source, version, and region."""
    block = generate_provider_block(region="cn-beijing", profile="my-profile")
    assert 'source  = "alibaba/alicloud"' in block
    assert "version =" in block
    assert 'region  = "cn-beijing"' in block
    assert 'profile = "my-profile"' in block


def test_provider_locker_class_init():
    """ProviderLocker can be instantiated with custom version."""
    locker = ProviderLocker(version="1.220.0")
    assert locker.version == "1.220.0"


def test_provider_locker_invalid_version_raises():
    """Invalid semver version must raise ValueError."""
    with pytest.raises(ValueError, match="Invalid version"):
        ProviderLocker(version="not-a-version")

    with pytest.raises(ValueError, match="Invalid version"):
        ProviderLocker(version="1.2")  # missing patch


def test_generate_block_no_hardcoded_ak():
    """Generated block must NOT contain hardcoded AK patterns."""
    block = generate_provider_block(region="cn-hangzhou")

    # These patterns MUST NOT appear
    assert not re.search(r"LTAI[A-Za-z0-9]{10,}", block)
    assert not re.search(r"AKIA[A-Za-z0-9]{10,}", block)
    assert not re.search(r'access_key\s*=\s*"[A-Za-z0-9]+"', block)


def test_generate_block_contains_env_var_comments():
    """Block should document that credentials come from env vars."""
    block = generate_provider_block()
    assert "ALIBABA_CLOUD_ACCESS_KEY_ID" in block
    assert "ALIBABA_CLOUD_ACCESS_KEY_SECRET" in block
    assert "NEVER hardcoded" in block


def test_generate_block_no_profile_when_none():
    """profile line is omitted when profile is None."""
    block = generate_provider_block(profile=None)
    assert "profile" not in block


def test_generate_block_pessimistic_constraint():
    """Version uses pessimistic constraint (~>) not exact match."""
    block = generate_provider_block(version="1.220.0")
    # ~> 1.220.0 allows patch updates (1.220.x) but not minor (1.221.x)
    assert "~>" in block
    assert "exact" not in block.lower()
