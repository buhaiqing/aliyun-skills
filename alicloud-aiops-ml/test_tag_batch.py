"""RED tests for tag collector N+1 fix (Fix #3)."""
from __future__ import annotations

from unittest.mock import patch

from resource_model import Resource
from tag_collector import enrich_tags, _fetch_tags_batch


def make_r(i: int) -> Resource:
    return Resource(
        resource_id=f"r-{i}", resource_type="ecs", instance_name=f"x{i}",
        instance_type="t", product="unknown", env="unknown", owner="unknown",
        cpu_cores=4, memory_gb=8.0, disk_gb=40.0,
        cpu_util_avg=0.0, mem_util_avg=0.0, disk_util_avg=0.0,
        iops_util_avg=0.0, net_in_avg=0.0, net_out_avg=0.0,
        monthly_cost=100.0, is_prepaid=0, days_until_expire=0,
    )


def test_enrich_tags_uses_batch_fetch(tmp_path=None) -> None:
    """enrich_tags must call the batch API, NOT one call per resource."""
    resources = [make_r(i) for i in range(10)]

    with patch("tag_collector._fetch_tags_batch") as mock_batch, \
         patch("tag_collector._fetch_tags") as mock_single:
        mock_batch.return_value = {
            f"r-{i}": {"product": "app", "env": "prod", "owner": "team"}
            for i in range(10)
        }
        enrich_tags(resources, "cn-hangzhou", "123456")

        assert mock_single.call_count == 0, (
            f"Per-resource _fetch_tags called {mock_single.call_count} times; "
            f"expected 0 (batch mode required)"
        )
        assert mock_batch.call_count >= 1, "Batch fetch was never called"


def test_fetch_tags_batch_returns_per_resource_dict() -> None:
    """_fetch_tags_batch returns dict[resource_id] -> dict[str, str]."""
    resources = [make_r(i) for i in range(3)]
    with patch("tag_collector.cli_call") as mock_cli:
        mock_cli.return_value = {
            "TagResources": {
                "TagResource": [
                    {"ResourceARN": f"acs:ecs:cn-hangzhou::instance/r-0",
                     "Tags": {"Tag": [{"TagKey": "product", "TagValue": "app"}]}},
                ]
            }
        }
        result = _fetch_tags_batch(resources, "cn-hangzhou", "123456")
        assert isinstance(result, dict)