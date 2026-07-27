"""Tests for cost_model.py — date parsing, expiration, and cost estimation."""
from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest

from cost_model import (
    PRICE_MAP,
    _estimate_ecs,
    _estimate_rds,
    _estimate_redis,
    _estimate_slb,
    _parse_date_safe,
    compute_days_until_expire,
    estimate_monthly_cost,
)


class TestParseDateSafe:
    """Tests for _parse_date_safe with all format strings."""

    def test_iso_with_z(self) -> None:
        result = _parse_date_safe("2026-08-01T00:00:00Z")
        assert result == datetime.datetime(2026, 8, 1, 0, 0, 0)

    def test_iso_without_seconds_z(self) -> None:
        result = _parse_date_safe("2029-03-31T16:00Z")
        assert result == datetime.datetime(2029, 3, 31, 16, 0)

    def test_iso_with_tz_offset(self) -> None:
        result = _parse_date_safe("2026-08-01T00:00:00+08:00")
        assert result == datetime.datetime(2026, 8, 1, 0, 0, 0)

    def test_iso_without_tz(self) -> None:
        result = _parse_date_safe("2026-08-01T00:00:00")
        assert result == datetime.datetime(2026, 8, 1, 0, 0, 0)

    def test_space_separated(self) -> None:
        result = _parse_date_safe("2026-08-01 00:00:00")
        assert result == datetime.datetime(2026, 8, 1, 0, 0, 0)

    def test_date_only(self) -> None:
        result = _parse_date_safe("2026-08-01")
        assert result == datetime.datetime(2026, 8, 1, 0, 0)

    def test_unparseable_returns_none(self) -> None:
        assert _parse_date_safe("not-a-date") is None
        assert _parse_date_safe("") is None
        assert _parse_date_safe("2026/08/01") is None


class TestComputeDaysUntilExpire:
    """Tests for compute_days_until_expire."""

    def test_future_date(self) -> None:
        future = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        result = compute_days_until_expire(future)
        assert 29 <= result <= 30

    def test_past_date_returns_zero(self) -> None:
        past = "2020-01-01"
        result = compute_days_until_expire(past)
        assert result == 0

    def test_none_returns_zero(self) -> None:
        assert compute_days_until_expire(None) == 0

    def test_empty_string_returns_zero(self) -> None:
        assert compute_days_until_expire("") == 0

    def test_whitespace_only_returns_zero(self) -> None:
        assert compute_days_until_expire("   ") == 0

    def test_unparseable_returns_zero(self) -> None:
        assert compute_days_until_expire("garbage") == 0

    def test_tomorrow(self) -> None:
        tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        result = compute_days_until_expire(tomorrow)
        assert result >= 0

    def test_iso_with_z_format(self) -> None:
        future = (datetime.datetime.now() + datetime.timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = compute_days_until_expire(future)
        assert 9 <= result <= 10

    def test_iso_without_seconds_z_format(self) -> None:
        future = (datetime.datetime.now() + datetime.timedelta(days=5)).strftime("%Y-%m-%dT%H:%MZ")
        result = compute_days_until_expire(future)
        assert 4 <= result <= 5


class TestEstimateMonthlyCost:
    """Tests for estimate_monthly_cost dispatch."""

    def test_ecs_known_instance(self) -> None:
        cost = estimate_monthly_cost("ecs", "ecs.g9i.2xlarge", 8, 32, 100, False)
        # 1000 (base) + 100*0.35 (disk) = 1035
        assert cost == 1035.0

    def test_ecs_prepaid_discount(self) -> None:
        cost = estimate_monthly_cost("ecs", "ecs.g9i.2xlarge", 8, 32, 100, True)
        # (1000 + 35) * 0.85 = 879.75 → ceil(87975)/100 = 879.75
        expected = __import__("math").ceil((1000.0 + 35.0) * 0.85 * 100) / 100
        assert cost == expected

    def test_ecs_unknown_instance_heuristic(self) -> None:
        cost = estimate_monthly_cost("ecs", "unknown-type", 4, 16, 50, False)
        # 4*100 + 16*25 + 50*0.35 = 400 + 400 + 17.5 = 817.5
        assert cost == 817.5

    def test_rds(self) -> None:
        cost = estimate_monthly_cost("rds", "", 4, 16, 100, False)
        # 4*200 + 16*50 + 100*1 = 800 + 800 + 100 = 1700
        assert cost == 1700.0

    def test_rds_prepaid(self) -> None:
        cost = estimate_monthly_cost("rds", "", 4, 16, 100, True)
        # 1700 * 0.85 = 1445.0
        expected = __import__("math").ceil(1700.0 * 0.85 * 100) / 100
        assert cost == expected

    def test_redis(self) -> None:
        cost = estimate_monthly_cost("redis", "", 0, 32, 0, False)
        # 32 * 80 = 2560
        assert cost == 2560.0

    def test_redis_prepaid(self) -> None:
        cost = estimate_monthly_cost("redis", "", 0, 32, 0, True)
        # 2560 * 0.85 = 2176.0
        expected = __import__("math").ceil(2560.0 * 0.85 * 100) / 100
        assert cost == expected

    def test_slb_internet(self) -> None:
        cost = estimate_monthly_cost("slb", "internet", 0, 0, 0, False)
        assert cost == 100.0

    def test_slb_intranet(self) -> None:
        cost = estimate_monthly_cost("slb", "intranet", 0, 0, 0, False)
        assert cost == 0.0

    def test_slb_unknown_type_defaults_100(self) -> None:
        cost = estimate_monthly_cost("slb", "unknown-lb", 0, 0, 0, False)
        assert cost == 100.0

    def test_oss(self) -> None:
        cost = estimate_monthly_cost("oss", "", 0, 0, 500, False)
        assert cost == 60.0  # 500 * 0.12

    def test_k8s_node(self) -> None:
        cost = estimate_monthly_cost("k8s_node", "", 4, 16, 0, False)
        # 4*100 + 16*25 = 400 + 400 = 800
        assert cost == 800.0

    def test_unknown_resource_type_returns_zero(self) -> None:
        cost = estimate_monthly_cost("unknown", "", 10, 100, 1000, False)
        assert cost == 0.0


class TestEstimateEcs:
    """Tests for _estimate_ecs internal function."""

    def test_known_instance_no_disk(self) -> None:
        cost = _estimate_ecs("ecs.g9i.xlarge", 4, 16, 0, False)
        assert cost == 500.0

    def test_unknown_instance_heuristic(self) -> None:
        cost = _estimate_ecs("custom", 8, 32, 0, False)
        # 8*100 + 32*25 = 800 + 800 = 1600
        assert cost == 1600.0

    def test_empty_instance_type_falls_to_heuristic(self) -> None:
        cost = _estimate_ecs("", 2, 8, 0, False)
        assert cost == 400.0  # 2*100 + 8*25

    def test_with_disk(self) -> None:
        cost = _estimate_ecs("ecs.g9i.large", 2, 8, 40, False)
        # 250 + 40*0.35 = 250 + 14 = 264
        assert cost == 264.0

    def test_prepaid_discount(self) -> None:
        cost = _estimate_ecs("ecs.g9i.large", 2, 8, 0, True)
        expected = __import__("math").ceil(250.0 * 0.85 * 100) / 100
        assert cost == expected


class TestEstimateRds:
    """Tests for _estimate_rds."""

    def test_basic(self) -> None:
        cost = _estimate_rds(2, 8, 50, False)
        # 2*200 + 8*50 + 50*1 = 400 + 400 + 50 = 850
        assert cost == 850.0

    def test_zero_cpu(self) -> None:
        cost = _estimate_rds(0, 16, 100, False)
        assert cost == 900.0  # 0 + 800 + 100

    def test_prepaid(self) -> None:
        cost = _estimate_rds(2, 8, 50, True)
        expected = __import__("math").ceil(850.0 * 0.85 * 100) / 100
        assert cost == expected


class TestEstimateRedis:
    """Tests for _estimate_redis."""

    def test_basic(self) -> None:
        cost = _estimate_redis(16, False)
        assert cost == 1280.0

    def test_zero_memory(self) -> None:
        cost = _estimate_redis(0, False)
        assert cost == 0.0

    def test_prepaid(self) -> None:
        cost = _estimate_redis(32, True)
        expected = __import__("math").ceil(2560.0 * 0.85 * 100) / 100
        assert cost == expected


class TestEstimateSlb:
    """Tests for _estimate_slb."""

    def test_internet(self) -> None:
        assert _estimate_slb("internet") == 100.0

    def test_intranet(self) -> None:
        assert _estimate_slb("intranet") == 0.0

    def test_unknown_defaults_to_100(self) -> None:
        assert _estimate_slb("anything-else") == 100.0


class TestPriceMap:
    """Verify PRICE_MAP has expected entries."""

    def test_ecs_entries_exist(self) -> None:
        assert "ecs.g9i.large" in PRICE_MAP
        assert "ecs.g8i.2xlarge" in PRICE_MAP
        assert "ecs.c8i.4xlarge" in PRICE_MAP
        assert "ecs.r8i.8xlarge" in PRICE_MAP

    def test_slb_entries_exist(self) -> None:
        assert PRICE_MAP["internet"] == 100.0
        assert PRICE_MAP["intranet"] == 0.0

    def test_k8s_entries_exist(self) -> None:
        assert PRICE_MAP["ack.standard"] == 900.0
        assert PRICE_MAP["ack.pro"] == 2800.0

    def test_prices_are_positive(self) -> None:
        for key, value in PRICE_MAP.items():
            if key != "intranet":
                assert value > 0, f"PRICE_MAP[{key}] should be positive, got {value}"
