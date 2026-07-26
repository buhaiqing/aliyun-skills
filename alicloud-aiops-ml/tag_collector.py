"""Tag enrichment collector for product/env/owner."""
from __future__ import annotations

from resource_model import Resource
from cli_utils import cli_call


BATCH_SIZE = 50


def enrich_tags(resources: list[Resource], region: str) -> list[Resource]:
    """Enrich resources with Tag-based product/env/owner info.

    Batches up to BATCH_SIZE resources per ListTagResources API call to avoid N+1.
    """
    if not resources:
        return resources

    for batch_start in range(0, len(resources), BATCH_SIZE):
        batch = resources[batch_start:batch_start + BATCH_SIZE]
        tags_by_id = _fetch_tags_batch(batch, region)
        for res in batch:
            tags = tags_by_id.get(res.resource_id, {})
            res.product = tags.get("product", "unknown")
            res.env = tags.get("env", "unknown")
            res.owner = tags.get("owner", "unknown")
    return resources


def _fetch_tags_batch(resources: list[Resource], region: str) -> dict[str, dict[str, str]]:
    """Fetch tags for a batch of resources via ListTagResources.

    Returns dict mapping resource_id -> {tag_key: tag_value}.
    """
    arns = [f"acs:ecs:{region}:0000000000000000:instance/{r.resource_id}" for r in resources]
    id_index = {r.resource_id: r.resource_id for r in resources}

    arn_args = " ".join(f"--ResourceARN.{i + 1} {arn}" for i, arn in enumerate(arns))
    cmd = (
        f"aliyun tag ListTagResources --RegionId {region} "
        f"--ResourceType instance {arn_args} --output json"
    )
    data = cli_call(cmd) or {}

    result: dict[str, dict[str, str]] = {rid: {} for rid in id_index}
    for item in data.get("TagResources", {}).get("TagResource", []):
        arn = item.get("ResourceARN", "")
        rid = arn.rsplit("/", 1)[-1]
        if rid not in result:
            continue
        for tag in item.get("Tags", {}).get("Tag", []):
            result[rid][tag.get("TagKey", "")] = tag.get("TagValue", "")
    return result


def _fetch_tags(resource_id: str, region: str) -> dict[str, str]:
    """Fetch tags for a single resource. Kept for backward compatibility / single-resource use."""
    r = Resource(
        resource_id=resource_id, resource_type="ecs", instance_name="",
        instance_type="", product="", env="", owner="",
        cpu_cores=0, memory_gb=0.0, disk_gb=0.0,
        cpu_util_avg=0.0, mem_util_avg=0.0, disk_util_avg=0.0,
        iops_util_avg=0.0, net_in_avg=0.0, net_out_avg=0.0,
        monthly_cost=0.0, is_prepaid=0, days_until_expire=0,
    )
    batched = _fetch_tags_batch([r], region)
    return batched.get(resource_id, {})