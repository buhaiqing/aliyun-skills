"""Validate manifest.json against the canonical JSON Schema (v1.0).

Used by export-hcl.py and baseline-manager.py to ensure any manifest
written or read conforms to schema_version 1.0.

The schema is intentionally strict (additionalProperties: false) so that
typos and implicit field additions are caught at write time rather than
discovered later when downstream tools fail to parse the manifest.
"""
import json
from pathlib import Path

try:
    from jsonschema import Draft7Validator
except ImportError as e:
    raise ImportError(
        "jsonschema package required. Install with: pip install jsonschema>=4.21"
    ) from e


SCHEMA_PATH = (
    Path(__file__).parent.parent.parent / "references" / "manifest-schema.json"
)


class ManifestValidationError(Exception):
    """Raised when a manifest fails schema validation.

    Error messages include the JSON path of the failing field for easy
    debugging of bad input.
    """


class ManifestValidator:
    """Validates manifest.json dicts against the canonical schema.

    Example:
        validator = ManifestValidator()
        validator.validate(manifest_dict)  # raises on failure
    """

    def __init__(self, schema_path: Path = SCHEMA_PATH):
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {schema_path}")
        with open(schema_path, encoding="utf-8") as f:
            self.schema = json.load(f)
        self._validator = Draft7Validator(self.schema)

    def validate(self, manifest: dict) -> None:
        """Validate manifest against schema. Raises ManifestValidationError on failure.

        On failure, raises with a message that includes the field path
        (using `->` separator) of the first error encountered. Returns
        None on success.
        """
        errors = list(self._validator.iter_errors(manifest))
        if not errors:
            return

        # Format first error with field path for debuggability
        err = errors[0]
        path = " -> ".join(str(p) for p in err.absolute_path) or "(root)"
        raise ManifestValidationError(
            f"Manifest validation failed at '{path}': {err.message}"
        )
