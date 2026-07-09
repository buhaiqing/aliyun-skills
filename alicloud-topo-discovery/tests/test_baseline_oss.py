#!/usr/bin/env python3
"""Tests for OSS backend (Plan 2 Task 2)."""
import pytest

from scripts.lib.baseline_oss import OSSBackend


def test_empty_bucket_raises():
    """Empty bucket raises ValueError."""
    with pytest.raises(ValueError, match="bucket"):
        OSSBackend(bucket="", prefix="baselines/", ak_id="test-ak")


def test_missing_ak_raises(monkeypatch):
    """Missing AK raises ValueError."""
    monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_ID", raising=False)
    with pytest.raises(ValueError, match="AK"):
        OSSBackend(bucket="my-bucket", prefix="baselines/", ak_id="")


def test_default_prefix_ends_with_slash():
    """Default prefix ends with /."""
    backend = OSSBackend(bucket="my-bucket", ak_id="test-ak")
    assert backend.prefix == "baselines/"


def test_custom_prefix_ends_with_slash():
    """Custom prefix also ends with /."""
    backend = OSSBackend(bucket="my-bucket", prefix="custom/topo/", ak_id="test-ak")
    assert backend.prefix == "custom/topo/"


def test_endpoint_fallback_to_env(monkeypatch):
    """Endpoint falls back to env var."""
    monkeypatch.setenv("OSS_ENDPOINT", "oss-cn-shenzhen.aliyuncs.com")
    backend = OSSBackend(bucket="my-bucket", ak_id="test-ak")
    assert backend.endpoint == "oss-cn-shenzhen.aliyuncs.com"


def test_default_endpoint():
    """Default endpoint is oss-cn-hangzhou."""
    backend = OSSBackend(bucket="my-bucket", ak_id="test-ak")
    assert backend.endpoint == "oss-cn-hangzhou.aliyuncs.com"


def test_ak_from_init():
    """AK from init param overrides env."""
    backend = OSSBackend(bucket="my-bucket", ak_id="explicit-ak")
    assert backend.ak_id == "explicit-ak"


def test_ak_from_env(monkeypatch):
    """AK from env var when init param not given."""
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "env-ak")
    monkeypatch.setenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "env-sk")
    backend = OSSBackend(bucket="my-bucket")
    assert backend.ak_id == "env-ak"
