"""Tag enrichment collector for product/env/owner."""
from __future__ import annotations

from resource_model import Resource
from cli_utils import cli_call


def enrich_tags(resources: list[Resource], region: str) -> list[Resource]:
    """Enrich resources with Tag-based product/env/owner info.

    Uses DescribeTags API to batch-query tags for each resource.
    """
    for res in resources:
        tags = _fetch_tags(res.resource_id, region)
        res.product = tags.get("product", "unknown")
        res.env = tags.get("env", "unknown")
        res.owner = tags.get("owner", "unknown")
    return resources


def _fetch_tags(resource_id: str, region: str) -> dict[str, str]:
    """Fetch tags for a specific resource via ListTagResources."""
    cmd = (
        f"aliyun tag ListTagResources --RegionId {region} "
        f"--ResourceType instance --ResourceId.1 {resource_id} --output json"
    )
    data = cli_call(cmd) or {}
    tags = {}
    for item in data.get("TagResources", {}).get("TagResource", []):
        tags[item.get("TagKey", "")] = item.get("TagValue", "")
    return tags
