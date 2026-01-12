#!/usr/bin/env python3
"""
Verify pipeline output files exist and are valid.

Usage:
    python scripts/verify_pipeline_output.py <output_dir>
"""

import json
import os
import sys


def verify_pipeline_output(output_dir: str) -> bool:
    """
    Verify that all expected pipeline outputs exist and are valid JSON.

    Args:
        output_dir: Directory containing compiled outputs

    Returns:
        True if all checks pass, False otherwise
    """
    errors = []
    warnings = []

    # Expected files
    expected_files = {
        "compiled_intel.json": "Compiled intelligence",
        "merge_report.json": "Merge report",
        "qa_report.json": "QA report"
    }

    print(f"Verifying pipeline outputs in: {output_dir}")
    print("")

    for filename, description in expected_files.items():
        filepath = os.path.join(output_dir, filename)

        # Check file exists
        if not os.path.exists(filepath):
            errors.append(f"Missing {description}: {filename}")
            continue

        # Check valid JSON
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            # Specific checks
            if filename == "compiled_intel.json":
                if "_schema_version" not in data:
                    warnings.append(f"{filename}: missing _schema_version")
                if "claims_ledger" not in data:
                    errors.append(f"{filename}: missing claims_ledger")

            elif filename == "qa_report.json":
                status = data.get("status", "UNKNOWN")
                if status != "OK":
                    errors.append(f"QA status: {status}")
                    if "errors" in data and data["errors"]:
                        for err in data["errors"]:
                            errors.append(f"  - {err}")

            print(f"✓ {description}: {filename}")

        except json.JSONDecodeError as e:
            errors.append(f"{filename}: Invalid JSON - {e}")
        except Exception as e:
            errors.append(f"{filename}: {e}")

    print("")

    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"  ⚠ {warning}")
        print("")

    if errors:
        print("Errors:")
        for error in errors:
            print(f"  ✗ {error}")
        print("")
        return False

    print("All checks passed!")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/verify_pipeline_output.py <output_dir>")
        sys.exit(1)

    output_dir = sys.argv[1]

    if not os.path.isdir(output_dir):
        print(f"Error: {output_dir} is not a directory")
        sys.exit(1)

    success = verify_pipeline_output(output_dir)
    sys.exit(0 if success else 1)
