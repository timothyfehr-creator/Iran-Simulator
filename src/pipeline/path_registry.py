"""
Path registry for validating and normalizing claim paths.

Loads config/path_registry.json and provides validation + enum normalization.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Any, Optional, Tuple, List


class PathRegistry:
    """Registry of valid paths with enum normalization."""

    def __init__(self, registry_path: str):
        """
        Load path registry from JSON file.

        Args:
            registry_path: Path to path_registry.json
        """
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)

        self.paths: Dict[str, Dict[str, Any]] = registry.get("paths", {})
        self._schema_version = registry.get("_schema_version", "1.0")

    def is_valid_path(self, path: str) -> bool:
        """Check if path is registered."""
        return path in self.paths

    def get_path_info(self, path: str) -> Optional[Dict[str, Any]]:
        """Get path metadata (type, enum_values, etc.)."""
        return self.paths.get(path)

    def normalize_enum_value(self, path: str, value: Any) -> Tuple[Any, List[str]]:
        """
        Normalize enum value to uppercase if path has enum type.

        Args:
            path: The claim path
            value: The value to normalize

        Returns:
            (normalized_value, errors)
            - If not an enum path: returns (value, [])
            - If enum path: returns (UPPERCASE_VALUE, []) or (value, [error_msg])
        """
        path_info = self.get_path_info(path)
        if not path_info:
            # Path not in registry; will be caught by unknown path check
            return value, []

        if path_info.get("type") != "enum":
            # Not an enum, no normalization needed
            return value, []

        # This is an enum field
        if not isinstance(value, str):
            return value, [f"path '{path}': enum value must be string, got {type(value).__name__}"]

        normalize_uppercase = path_info.get("normalize_uppercase", True)
        enum_values = path_info.get("enum_values", [])

        if normalize_uppercase:
            normalized = value.upper()
        else:
            normalized = value

        if normalized not in enum_values:
            return value, [
                f"path '{path}': value '{value}' (normalized to '{normalized}') "
                f"not in allowed values {enum_values}"
            ]

        return normalized, []

    def validate_claim_path(self, claim: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validate and normalize a claim.

        Args:
            claim: The claim dict

        Returns:
            (normalized_claim, errors)
        """
        path = claim.get("path", "")
        value = claim.get("value")
        errors: List[str] = []

        # Check if path is registered
        if not self.is_valid_path(path):
            errors.append(f"claim_id '{claim.get('claim_id')}': unknown path '{path}'")
            return claim, errors

        # Normalize enum if applicable
        if value is not None:  # Don't normalize null values
            normalized_value, norm_errors = self.normalize_enum_value(path, value)
            if norm_errors:
                errors.extend(norm_errors)
            else:
                # Update claim with normalized value
                claim = dict(claim)  # shallow copy
                claim["value"] = normalized_value

        return claim, errors


def load_default_registry() -> PathRegistry:
    """Load path registry from default location (config/path_registry.json)."""
    # Find repo root (go up from src/pipeline/)
    current_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    registry_path = os.path.join(repo_root, "config", "path_registry.json")

    if not os.path.exists(registry_path):
        raise FileNotFoundError(f"Path registry not found at {registry_path}")

    return PathRegistry(registry_path)
