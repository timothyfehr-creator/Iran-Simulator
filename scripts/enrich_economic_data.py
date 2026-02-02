#!/usr/bin/env python3
"""
Enrich compiled_intel.json with live economic data from Bonbast.

This script:
1. Fetches current exchange rates from Bonbast
2. Updates the economic_conditions section in compiled_intel.json
3. Creates a backup of the original file

Usage:
    python scripts/enrich_economic_data.py --intel runs/RUN_*/compiled_intel.json

The script will update:
- current_state.economic_conditions.rial_usd_rate.market
- current_state.economic_conditions.rial_usd_rate.sell
- current_state.economic_conditions.rial_usd_rate.buy
- current_state.economic_conditions.rial_usd_rate.date
"""

import argparse
import json
import os
import sys
import shutil
from datetime import datetime, timezone

import yaml

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ingest.fetch_bonbast import BonbastFetcher


def _load_source_config(source_id: str) -> dict:
    """Load a source config from config/sources.yaml by ID."""
    sources_path = os.path.join(
        os.path.dirname(__file__), '..', 'config', 'sources.yaml'
    )
    with open(sources_path, 'r') as f:
        config = yaml.safe_load(f)
    for source in config.get("sources", []):
        if source.get("id") == source_id:
            return source
    raise ValueError(f"Source '{source_id}' not found in config/sources.yaml")


def fetch_economic_data() -> dict:
    """Fetch current economic data from Bonbast.

    Returns:
        Dict with economic data or empty dict on failure
    """
    config = _load_source_config("bonbast")

    try:
        fetcher = BonbastFetcher(config)
        docs, error = fetcher.fetch()

        if error:
            print(f"WARNING: Bonbast fetch failed: {error}")
            return {}

        if not docs:
            print("WARNING: No data returned from Bonbast")
            return {}

        return docs[0].get("structured_data", {})

    except Exception as e:
        print(f"WARNING: Error fetching Bonbast data: {e}")
        return {}


def enrich_intel(intel_path: str, backup: bool = True) -> bool:
    """Enrich compiled_intel.json with economic data.

    Args:
        intel_path: Path to compiled_intel.json
        backup: Whether to create a backup before modifying

    Returns:
        True if successful, False otherwise
    """
    # Load existing intel
    try:
        with open(intel_path, 'r', encoding='utf-8') as f:
            intel = json.load(f)
    except Exception as e:
        print(f"ERROR: Could not load {intel_path}: {e}")
        return False

    # Fetch economic data
    print("Fetching economic data from Bonbast...")
    econ_data = fetch_economic_data()

    if not econ_data:
        print("WARNING: No economic data available, skipping enrichment")
        return False

    # Create backup
    if backup:
        backup_path = intel_path + ".bak"
        shutil.copy2(intel_path, backup_path)
        print(f"Created backup: {backup_path}")

    # Ensure current_state exists
    if "current_state" not in intel:
        intel["current_state"] = {}

    # Ensure economic_conditions exists
    if "economic_conditions" not in intel["current_state"]:
        intel["current_state"]["economic_conditions"] = {}

    econ = intel["current_state"]["economic_conditions"]

    # Update rial_usd_rate
    rial_data = econ_data.get("rial_usd_rate", {})
    if rial_data:
        econ["rial_usd_rate"] = {
            "market": rial_data.get("market"),
            "sell": rial_data.get("sell"),
            "buy": rial_data.get("buy"),
            "date": econ_data.get("last_modified"),
            "source": "bonbast",
        }
        print(f"Updated rial_usd_rate: {rial_data.get('market'):,} IRR")

    # Update rial_eur_rate if available
    eur_data = econ_data.get("rial_eur_rate", {})
    if eur_data:
        econ["rial_eur_rate"] = {
            "sell": eur_data.get("sell"),
            "buy": eur_data.get("buy"),
        }

    # Update gold prices if available
    if econ_data.get("gold_18k_rial"):
        econ["gold_18k_per_gram_rial"] = econ_data["gold_18k_rial"]

    # Seed inflation baseline if not already set by claim extraction.
    # Iran's SCI-reported annual inflation has been 40-50% through 2025-2026.
    # This is an analyst-anchored baseline; claim extraction can override it.
    if "inflation" not in econ or not isinstance(econ.get("inflation"), dict):
        econ["inflation"] = {
            "official_annual_percent": 42,
            "source": "baseline_anchor",
            "note": "SCI-reported range 40-50% (2025-2026). Override via claim extraction.",
        }
        print("Seeded baseline inflation: 42% (SCI anchor)")

    # Add data source metadata
    econ["_enrichment_metadata"] = {
        "source": "bonbast",
        "enriched_at_utc": datetime.now(timezone.utc).isoformat(),
        "original_timestamp": econ_data.get("last_modified"),
    }

    # Write updated intel
    try:
        with open(intel_path, 'w', encoding='utf-8') as f:
            json.dump(intel, f, indent=2)
        print(f"Updated: {intel_path}")
        return True
    except Exception as e:
        print(f"ERROR: Could not write {intel_path}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Enrich compiled_intel.json with live economic data"
    )
    parser.add_argument(
        "--intel",
        required=True,
        help="Path to compiled_intel.json"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Don't create backup before modifying"
    )

    args = parser.parse_args()

    if not os.path.exists(args.intel):
        print(f"ERROR: File not found: {args.intel}")
        sys.exit(1)

    success = enrich_intel(args.intel, backup=not args.no_backup)

    if success:
        print("\nEconomic enrichment complete!")

        # Show a preview
        with open(args.intel, 'r') as f:
            intel = json.load(f)
        econ = intel.get("current_state", {}).get("economic_conditions", {})

        print("\nCurrent economic conditions:")
        rial = econ.get("rial_usd_rate", {})
        if rial:
            print(f"  USD/IRR rate: {rial.get('market', 'N/A'):,} IRR")

        sys.exit(0)
    else:
        # Soft fail — exit 2 so daily_update.py captures via run_stage()
        sys.exit(2)


if __name__ == "__main__":
    main()
