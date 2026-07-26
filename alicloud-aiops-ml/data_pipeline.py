"""Data pipeline - aggregate all collectors into unified DataFrame."""
from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from resource_model import Resource


def aggregate_to_json(resources: list[Resource], output_path: str) -> None:
    """Write resources to JSON file."""
    data = [asdict(r) for r in resources]
    Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def load_resources(json_path: str) -> list[Resource]:
    """Load resources from JSON file."""
    data = json.loads(Path(json_path).read_text())
    return [_dict_to_resource(d) for d in data]


def _dict_to_resource(d: dict[str, Any]) -> Resource:
    known = {f.name for f in fields(Resource)}
    return Resource(**{k: v for k, v in d.items() if k in known})
