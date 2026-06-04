"""Infer resource dependency graph and produce topological order.

Used by export-hcl.py to order HCL resource blocks so that parent
resources (VPC) are declared before children (VSwitch, ECS).

Algorithm: Kahn's algorithm (BFS-based topological sort) using
adjacency list from MappingSpec.parent_ref fields. Handles cycles,
orphans, and DAG ordering correctly across all Python 3.x versions.
"""
from collections import defaultdict, deque
from typing import Any, Optional


class DependencyInferenceError(Exception):
    """Raised when dependency inference encounters an unresolvable condition."""


def infer_dependencies(resources: list) -> list:
    """Infer dependencies and return topologically ordered resource list.

    Args:
        resources: List of tuples (resource_type, resource_data, spec, block_name).

    Returns:
        The input list reordered so parents precede children.

    Raises:
        DependencyInferenceError: on circular references.
    """
    if not resources:
        return []

    # Build block_name -> (resource_type, resource_data, spec) lookup
    block_lookup = {
        block_name: (rt, data, spec)
        for rt, data, spec, block_name in resources
    }

    # Build adjacency + in-degree for Kahn's algorithm
    children_of = defaultdict(set)
    in_degree = {}
    all_nodes = []

    for rt, data, spec, block_name in resources:
        all_nodes.append(block_name)
        if block_name not in in_degree:
            in_degree[block_name] = 0

        if spec.parent_ref:
            parent_id = _resolve_parent_id(data, spec.parent_ref)
            if parent_id:
                parent_block = _find_block_by_id(
                    parent_id, block_lookup, exclude=block_name
                )
                if parent_block:
                    children_of[parent_block].add(block_name)
                    in_degree[block_name] = in_degree.get(block_name, 0) + 1

    # Kahn's algorithm: start with nodes with no incoming edges
    queue = deque(n for n in all_nodes if in_degree.get(n, 0) == 0)
    ordered = []

    while queue:
        node = queue.popleft()
        ordered.append(node)
        for child in children_of.get(node, set()):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(ordered) != len(all_nodes):
        raise DependencyInferenceError(
            "Circular dependency detected: topological sort incomplete "
            f"({len(ordered)} of {len(all_nodes)} nodes processed)"
        )

    # Map ordered block names back to original tuples
    resource_lookup = {}
    for rt, data, spec, block_name in resources:
        resource_lookup[block_name] = (rt, data, spec, block_name)
    return [resource_lookup[b] for b in ordered]


def _resolve_parent_id(data: dict, parent_ref: str) -> Any:
    """Extract the parent resource ID from resource_data using parent_ref path."""
    parts = parent_ref.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _find_block_by_id(
    parent_id: Any, block_lookup: dict, exclude: Optional[str] = None
) -> Optional[str]:
    """Find a block name whose resource_data contains the given parent_id.

    Args:
        parent_id: The ID value to search for (e.g. "vpc-xxx").
        block_lookup: Dict of block_name -> (rt, data, spec).
        exclude: Optional block_name to skip (prevents self-matching when
                 the child resource has the same ID field name as its parent).

    Returns:
        Block name of matching parent, or None.
    """
    id_fields = ["VpcId", "VSwitchId", "InstanceId", "DBInstanceId", "LoadBalancerId"]
    for block_name, (rt, data, spec) in block_lookup.items():
        if exclude and block_name == exclude:
            continue
        for field in id_fields:
            if data.get(field) == parent_id:
                return block_name
    return None