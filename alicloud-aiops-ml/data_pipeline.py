"""Data pipeline - aggregate all collectors into unified DataFrame."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from resource_model import Resource


def aggregate_to_json(resources: list[Resource], output_path: str) -> None:
    """Write resources to JSON file."""
    data = [_resource_to_dict(r) for r in resources]
    Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def load_resources(json_path: str) -> list[Resource]:
    """Load resources from JSON file."""
    data = json.loads(Path(json_path).read_text())
    return [_dict_to_resource(d) for d in data]


def _resource_to_dict(r: Resource) -> dict[str, Any]:
    return {
        "resource_id": r.resource_id,
        "resource_type": r.resource_type,
        "instance_name": r.instance_name,
        "instance_type": r.instance_type,
        "product": r.product,
        "env": r.env,
        "owner": r.owner,
        "cpu_cores": r.cpu_cores,
        "memory_gb": r.memory_gb,
        "disk_gb": r.disk_gb,
        "cpu_util_avg": r.cpu_util_avg,
        "mem_util_avg": r.mem_util_avg,
        "disk_util_avg": r.disk_util_avg,
        "iops_util_avg": r.iops_util_avg,
        "net_in_avg": r.net_in_avg,
        "net_out_avg": r.net_out_avg,
        "monthly_cost": r.monthly_cost,
        "is_prepaid": r.is_prepaid,
        "days_until_expire": r.days_until_expire,
    }


def _dict_to_resource(d: dict[str, Any]) -> Resource:
    from dataclasses import fields
    known = {f.name for f in fields(Resource)}
    return Resource(**{k: v for k, v in d.items() if k in known})
