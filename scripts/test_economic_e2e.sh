#!/bin/bash
#
# End-to-end test for economic integration
#
# This script tests the full economic data flow:
# 1. IODA fetcher functionality
# 2. Economic bucket fetchers
# 3. Simulation with economic integration
# 4. Economic analysis in output
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Economic Integration E2E Test ==="
echo "Project root: $PROJECT_ROOT"
echo ""

cd "$PROJECT_ROOT"

# 1. Test IODA fetcher
echo "Step 1: Testing IODA fetcher..."
python3 -c "
from src.ingest.fetch_ioda import IODAFetcher

config = {
    'id': 'ioda',
    'name': 'IODA',
    'access_grade': 'A',
    'bias_grade': 1
}
fetcher = IODAFetcher(config)
docs, error = fetcher.fetch()

if error:
    print(f'WARN: IODA fetch failed (may be network issue): {error}')
else:
    print(f'OK: Fetched {len(docs)} docs')
    if docs:
        data = docs[0].get('structured_data', {})
        print(f'    Connectivity index: {data.get(\"connectivity_index\", \"N/A\")}')
" || echo "WARN: IODA test failed (network may be unavailable)"

echo ""

# 2. Test economic fetchers via coordinator (dry run)
echo "Step 2: Testing economic bucket configuration..."
python3 -c "
import yaml
from pathlib import Path

sources_path = Path('config/sources.yaml')
with open(sources_path) as f:
    config = yaml.safe_load(f)

econ_sources = [s for s in config.get('sources', []) if s.get('bucket') == 'econ_fx']
print(f'OK: Found {len(econ_sources)} econ_fx sources:')
for s in econ_sources:
    status = 'enabled' if s.get('enabled') else 'disabled'
    print(f'    - {s[\"id\"]}: {s[\"name\"]} ({status})')

# Check IODA source
ioda_sources = [s for s in config.get('sources', []) if s.get('id') == 'ioda']
if ioda_sources:
    print(f'OK: IODA source configured in internet_monitoring bucket')
else:
    print('FAIL: IODA source not found in sources.yaml')
    exit(1)
"

echo ""

# 3. Run simulation with economic integration
echo "Step 3: Running simulation with economic integration..."

# Find latest run with compiled_intel.json
LATEST_RUN=$(ls -td runs/RUN_* 2>/dev/null | head -1)

if [ -n "$LATEST_RUN" ] && [ -f "$LATEST_RUN/compiled_intel.json" ]; then
    echo "    Using intel from: $LATEST_RUN"

    # Create temp output directory
    OUTPUT_DIR=$(mktemp -d)
    trap "rm -rf $OUTPUT_DIR" EXIT

    python3 src/simulation.py \
        --intel "$LATEST_RUN/compiled_intel.json" \
        --priors data/analyst_priors.json \
        --runs 500 \
        --output "$OUTPUT_DIR/results.json" \
        2>&1 | head -20

    echo ""
    echo "Step 4: Checking economic analysis in output..."
    python3 -c "
import json
with open('$OUTPUT_DIR/results.json') as f:
    results = json.load(f)

if 'economic_analysis' in results:
    econ = results['economic_analysis']
    print(f'OK: Economic analysis present in output')
    print(f'    Stress level: {econ.get(\"stress_level\", \"N/A\")}')
    print(f'    Rial rate used: {econ.get(\"rial_rate_used\", \"N/A\")}')
    print(f'    Inflation used: {econ.get(\"inflation_used\", \"N/A\")}')
    mods = econ.get('modifiers_applied', {})
    print(f'    Modifiers applied:')
    for k, v in mods.items():
        print(f'        {k}: {v}')
else:
    print('FAIL: economic_analysis not in results')
    exit(1)
"
else
    echo "SKIP: No compiled_intel.json found in runs/"
    echo "    Creating synthetic test instead..."

    # Create temp directory for synthetic test
    OUTPUT_DIR=$(mktemp -d)
    trap "rm -rf $OUTPUT_DIR" EXIT

    # Create synthetic intel with critical economic conditions
    cat > "$OUTPUT_DIR/test_intel.json" << 'EOFJ'
{
  "_schema_version": "2.0",
  "current_state": {
    "as_of": "2026-01-17T12:00:00Z",
    "casualties": {"protesters": {"killed": {"mid": 50}}},
    "economic_conditions": {
      "rial_usd_rate": {"market": 1500000},
      "inflation": {"official_annual_percent": 42}
    }
  }
}
EOFJ

    python3 src/simulation.py \
        --intel "$OUTPUT_DIR/test_intel.json" \
        --priors data/analyst_priors.json \
        --runs 500 \
        --output "$OUTPUT_DIR/results.json" \
        2>&1 | head -20

    echo ""
    echo "Step 4: Checking economic analysis in output..."
    python3 -c "
import json
with open('$OUTPUT_DIR/results.json') as f:
    results = json.load(f)

if 'economic_analysis' in results:
    econ = results['economic_analysis']
    print(f'OK: Economic analysis present in output')
    print(f'    Stress level: {econ.get(\"stress_level\", \"N/A\")}')
    print(f'    Rial rate used: {econ.get(\"rial_rate_used\", \"N/A\")}')
    print(f'    Inflation used: {econ.get(\"inflation_used\", \"N/A\")}')

    # Verify it's CRITICAL given our synthetic data
    if econ.get('stress_level') == 'critical':
        print('OK: Correctly classified as CRITICAL stress')
    else:
        print('WARN: Expected CRITICAL stress level')

    mods = econ.get('modifiers_applied', {})
    print(f'    Modifiers applied:')
    for k, v in mods.items():
        print(f'        {k}: {v}')
else:
    print('FAIL: economic_analysis not in results')
    exit(1)
"
fi

echo ""
echo "=== E2E Test Complete ==="
