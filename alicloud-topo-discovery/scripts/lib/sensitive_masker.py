"""Mask sensitive fields in resource JSON before HCL generation.

Phase 1 covers: RDS AccountPassword, ECS Password
(only fields that appear in Describe* responses for Top-5 types).

For each sensitive field:
- Replace value with `${var.<field_name>}` variable reference
- Track field path in returned tuple (for manifest logging)
- In HCL output, append `sensitive = true` directive

Security principle: NEVER log or return the original sensitive value.
"""

# Resource type -> field name (lowercase) -> HCL variable name
# These are fields that appear in Describe* API responses.
SENSITIVE_FIELDS: dict = {
    "rds": {
        "accountpassword": "rds_password",
    },
    "ecs": {
        "password": "ecs_password",
    },
    # VPC/VSwitch/SLB have no sensitive fields in Describe* responses
    "vpc": {},
    "vswitch": {},
    "slb": {},
}


def _var_name_for(resource_type: str, field_name: str) -> str | None:
    """Return the HCL variable name for a sensitive field, or None if not sensitive."""
    rt_fields = SENSITIVE_FIELDS.get(resource_type.lower(), {})
    return rt_fields.get(field_name.lower())


def _is_sensitive(resource_type: str, field_name: str) -> bool:
    """True if this (resource_type, field_name) pair is registered as sensitive."""
    return _var_name_for(resource_type, field_name) is not None


def _field_path(resource_type: str, field_name: str) -> str:
    """Build a dotted path like 'rds.account_password' for manifest logging.

    Field name is normalised to snake_case so 'AccountPassword' becomes
    'account_password'. Matches the convention used in SENSITIVE_FIELDS keys.
    """
    snake = "".join(
        "_" + c.lower() if c.isupper() else c.lower()
        for c in field_name
    ).lstrip("_")
    return f"{resource_type.lower()}.{snake}"


def mask_value(resource_type: str, field_name: str, value) -> object:
    """Convenience function: mask if sensitive, else return original value.

    Usage: new_value = mask_value("rds", "AccountPassword", "secret")
    """
    var_name = _var_name_for(resource_type, field_name)
    if var_name is None:
        return value
    return f"${{var.{var_name}}}"


class SensitiveMasker:
    """Masks sensitive field values in resource JSON.

    Usage:
        masker = SensitiveMasker()
        masked_paths = []
        for field, value in resource_dict.items():
            new_value, path = masker.mask_field(resource_type, field, value)
            if path:
                masked_paths.append(path)
            resource_dict[field] = new_value
    """

    def mask_field(
        self, resource_type: str, field_name: str, value
    ) -> tuple[object, str | None]:
        """Mask a single field value.

        Returns:
            (masked_value, field_path_or_None)
            - If sensitive: (var_ref_string, dotted_path)
            - If not: (original_value, None)
        """
        var_name = _var_name_for(resource_type, field_name)
        if var_name is None:
            return value, None
        return f"${{var.{var_name}}}", _field_path(resource_type, field_name)

    def hcl_line(
        self, resource_type: str, field_name: str, value, indent: int = 0
    ) -> str:
        """Generate a single HCL attribute line.

        For sensitive fields: outputs two lines (the var ref + sensitive = true).
        For non-sensitive: outputs single `attr = value` line.
        Note: caller wraps the variable name in ${...} since this method
        returns the bare var name.
        """
        prefix = "  " * indent
        var_name = _var_name_for(resource_type, field_name)
        if var_name is not None:
            return f"{prefix}{field_name} = var.{var_name}\n{prefix}sensitive = true"
        return f"{prefix}{field_name} = {self._hcl_literal(value)}"

    @staticmethod
    def _hcl_literal(value) -> str:
        """Format a Python value as an HCL literal."""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int | float):
            return str(value)
        if value is None:
            return "null"
        # String: wrap in double quotes, escape backslash and quote
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
