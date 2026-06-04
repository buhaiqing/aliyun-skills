"""JSON → HCL conversion engine for Aliyun resource exports.

Consumes raw Describe* API JSON responses and produces HCL `resource` blocks
using MappingSpec definitions. Integrates with SensitiveMasker for secure
handling of password/key fields.

Architecture:
    MappingSpec(resource_type, terraform_type, rules, parent_ref=None)
    MappingRule(hcl_attr, path, type, sensitive, required, default)
    FieldMapper.map_resource(resource_type, resource_data, spec, block_name) -> str
"""
from dataclasses import dataclass, field
from typing import Any, Optional

from scripts.lib.sensitive_masker import SensitiveMasker


@dataclass
class MappingRule:
    """Defines how a single JSON field maps to an HCL attribute."""
    hcl_attr: str
    path: str
    type: str = "string"
    sensitive: bool = False
    required: bool = True
    default: Any = None


@dataclass
class MappingSpec:
    """Defines a complete resource type mapping."""
    resource_type: str
    terraform_type: str
    rules: list = field(default_factory=list)
    parent_ref: Optional[str] = None


class FieldMapper:
    """Converts Aliyun Describe* API JSON responses into HCL resource blocks.

    Usage:
        mapper = FieldMapper()
        hcl = mapper.map_resource(
            resource_type="vpc",
            resource_data={"VpcName": "prod", "CidrBlock": "10.0.0.0/8"},
            spec=MappingSpec("vpc", "alicloud_vpc", rules=[...]),
            block_name="alicloud_vpc.prod"
        )
    """

    def __init__(self):
        self._masker = SensitiveMasker()

    def map_resource(
        self,
        resource_type: str,
        resource_data: dict,
        spec: MappingSpec,
        block_name: str,
    ) -> str:
        """Map a single resource's JSON data to an HCL resource block.

        Returns a string like:
            resource "alicloud_vpc" "prod" {
              vpc_name = "prod"
              cidr_block = "10.0.0.0/8"
            }
        """
        lines = [f'resource "{spec.terraform_type}" "{block_name}" {{']

        for rule in spec.rules:
            raw_value = self._resolve_path(resource_data, rule.path)
            if raw_value is None:
                if rule.default is not None:
                    raw_value = rule.default
                elif rule.required:
                    # Skip missing required fields (they'll be caught by
                    # the user reviewing the output, not by the mapper)
                    continue
                else:
                    continue

            hcl_value = self._format_value(raw_value, rule.type)

            if rule.sensitive:
                # Pass the original API field name (last part of dotted path)
                # so the masker can look it up in SENSITIVE_FIELDS correctly.
                api_field_name = rule.path.split(".")[-1]
                var_ref = self._masker.mask_field(resource_type, api_field_name, raw_value)[0]
                hcl_value = var_ref if isinstance(var_ref, str) else self._format_value(var_ref, rule.type)
                lines.append(f"  {rule.hcl_attr} = {hcl_value}")
                lines.append(f"  sensitive = true")
            else:
                lines.append(f"  {rule.hcl_attr} = {hcl_value}")

        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def _resolve_path(data: dict, path: str) -> Any:
        """Resolve a dotted JSON path like 'VpcName' or 'Tags.Tag[*].TagKey'.

        Simple dot notation only (no wildcards in Phase 1).
        Returns None if any intermediate key is missing.
        """
        parts = path.split(".")
        current = data
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                # Handle list-of-dicts: part is a key, we collect values
                try:
                    current = [item.get(part) if isinstance(item, dict) else None for item in current]
                    # Filter None values
                    current = [v for v in current if v is not None]
                    if not current:
                        return None
                    return current[0] if len(current) == 1 else current
                except (AttributeError, IndexError):
                    return None
            else:
                return None
        return current

    @staticmethod
    def _format_value(value: Any, type_hint: str) -> str:
        """Format a Python value as an HCL literal."""
        if value is None:
            return "null"
        if type_hint == "bool":
            return "true" if value else "false"
        if type_hint == "int":
            return str(int(value))
        if type_hint == "list":
            if isinstance(value, (list, tuple)):
                items = ", ".join(f'"{str(v)}"' for v in value)
                return f"[{items}]"
            return f'["{value}"]'
        if type_hint == "dict" and isinstance(value, dict):
            items = ", ".join(f'{k} = "{v}"' for k, v in value.items())
            return "{ " + items + " }"
        # Default: string (with quote escaping)
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    @staticmethod
    def generate_block_name(terraform_type: str, resource_data: dict, spec: MappingSpec) -> str:
        """Generate a stable, human-readable block name from resource data.

        Examples:
            alicloud_vpc + {VpcName: "prod"} -> "prod"
            alicloud_vswitch + {VSwitchName: "vsw-a"} -> "vsw_a"
            alicloud_instance + {InstanceName: "web-1"} -> "web_1"

        Uses resource type-specific logic from MappingSpec.
        If no name field exists, falls back to ID-based slug.
        """
        name_field = _NAME_FIELDS.get(spec.resource_type, "Name")
        name = resource_data.get(name_field)
        if not name:
            # Fallback to resource-type-specific ID field
            id_field = _ID_FIELDS.get(spec.resource_type)
            if id_field and id_field in resource_data:
                name = resource_data[id_field]
        if not name:
            name = terraform_type

        slug = _slugify(str(name))
        return f"{terraform_type}_{slug}" if spec.resource_type == "unknown" else slug


def _slugify(name: str) -> str:
    """Convert a resource name to a valid HCL identifier slug.

    Rules:
    - Replace non-alphanumeric with underscore
    - Collapse multiple underscores
    - Must not start with a number (prefix with 'r_' if needed)
    """
    slug = ""
    for ch in name:
        if ch.isalnum():
            slug += ch.lower()
        else:
            slug += "_"
    slug = "_".join(filter(None, slug.split("_")))
    if slug and slug[0].isdigit():
        slug = "r_" + slug
    return slug or "unnamed"


# Resource-type-specific name field mapping (Describe* API → HCL block name)
_NAME_FIELDS = {
    "vpc": "VpcName",
    "vswitch": "VSwitchName",
    "ecs": "InstanceName",
    "rds": "DBInstanceDescription",
    "slb": "LoadBalancerName",
}

# Resource-type-specific ID field mapping (Describe* API → fallback block name)
_ID_FIELDS = {
    "vpc": "VpcId",
    "vswitch": "VSwitchId",
    "ecs": "InstanceId",
    "rds": "DBInstanceId",
    "slb": "LoadBalancerId",
}
