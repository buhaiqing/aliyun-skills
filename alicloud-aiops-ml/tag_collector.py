"""Tag enrichment collector for product/env/owner."""
from __future__ import annotations

from resource_model import Resource
from cli_utils import cli_call


BATCH_SIZE = 50

_RESOURCE_TYPE_TO_ARN_PRODUCT = {
    "ecs": ("ecs", "instance"),
    "rds": ("rds", "db"),
    "redis": ("r-kvstore", "instance"),
    "slb": ("slb", "slb"),
    "oss": ("oss", "bucket"),
    "k8s_node": ("cs", "node"),
}


def _build_arn(resource_id: str, resource_type: str, region: str, account_id: str) -> str:
    """Build Alibaba Cloud Resource ARN for a resource.

    ARN format: acs:<product>:<region>:<account_id>:<type>/<id>
    """
    if resource_type not in _RESOURCE_TYPE_TO_ARN_PRODUCT:
        raise ValueError(
            f"Unsupported resource_type for ARN: {resource_type!r}. "
            f"Known: {sorted(_RESOURCE_TYPE_TO_ARN_PRODUCT.keys())}"
        )
    product, type_segment = _RESOURCE_TYPE_TO_ARN_PRODUCT[resource_type]
    return f"acs:{product}:{region}:{account_id}:{type_segment}/{resource_id}"


def _resource_type_arg(resource_type: str) -> str:
    """Map our internal resource_type to the Aliyun Tag service --ResourceType value.

    Must match the type_segment used in the ARN for the same resource.
    """
    mapping = {
        "ecs": "instance",
        "rds": "db",
        "redis": "instance",
        "slb": "slb",
        "oss": "bucket",
        "k8s_node": "cluster",
    }
    return mapping.get(resource_type, "instance")


def enrich_tags(resources: list[Resource], region: str, account_id: str) -> list[Resource]:
    """Enrich resources with Tag-based product/env/owner info.

    Batches up to BATCH_SIZE resources per ListTagResources API call to avoid N+1.
    Account_id is required to construct valid ARNs.
    """
    if not resources:
        return resources

    for batch_start in range(0, len(resources), BATCH_SIZE):
        batch = resources[batch_start:batch_start + BATCH_SIZE]
        tags_by_id = _fetch_tags_batch(batch, region, account_id)
        for res in batch:
            tags = tags_by_id.get(res.resource_id, {})
            res.product = tags.get("product", "unknown")
            res.env = tags.get("env", "unknown")
            res.owner = tags.get("owner", "unknown")
    return resources


def _fetch_tags_batch(
    resources: list[Resource], region: str, account_id: str,
) -> dict[str, dict[str, str]]:
    """Fetch tags for a batch of resources via ListTagResources.

    Returns dict mapping resource_id -> {tag_key: tag_value}.
    """
    arns = [_build_arn(r.resource_id, r.resource_type, region, account_id) for r in resources]
    types = [_resource_type_arg(r.resource_type) for r in resources]

    arn_args = " ".join(f"--ResourceARN.{i + 1} {arn}" for i, arn in enumerate(arns))
    type_args = " ".join(f"--ResourceType.{i + 1} {t}" for i, t in enumerate(types))
    cmd = (
        f"aliyun tag ListTagResources --RegionId {region} "
        f"{arn_args} {type_args} --output json"
    )
    data = cli_call(cmd) or {}

    result: dict[str, dict[str, str]] = {r.resource_id: {} for r in resources}
    for item in data.get("TagResources", {}).get("TagResource", []):
        arn = item.get("ResourceARN", "")
        rid = arn.rsplit("/", 1)[-1]
        if rid not in result:
            continue
        for tag in item.get("Tags", {}).get("Tag", []):
            result[rid][tag.get("TagKey", "")] = tag.get("TagValue", "")
    return result


def _fetch_tags(resource_id: str, resource_type: str, region: str, account_id: str) -> dict[str, str]:
    """Fetch tags for a single resource."""
    r = Resource(
        resource_id=resource_id, resource_type=resource_type, instance_name="",
        instance_type="", product="", env="", owner="",
        cpu_cores=0, memory_gb=0.0, disk_gb=0.0,
        cpu_util_avg=0.0, mem_util_avg=0.0, disk_util_avg=0.0,
        iops_util_avg=0.0, net_in_avg=0.0, net_out_avg=0.0,
        monthly_cost=0.0, is_prepaid=0, days_until_expire=0,
    )
    batched = _fetch_tags_batch([r], region, account_id)
    return batched.get(resource_id, {})