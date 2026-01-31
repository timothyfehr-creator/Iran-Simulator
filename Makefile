# Makefile for Iran Crisis Simulator Pipeline
# Convenience commands for running importer + compiler on test fixtures

.PHONY: help test clean import-fixture compile-fixture run-fixture-pipeline validate daily daily-manual daily-status daily-diff dashboard cron-install cron-remove cron-status cron-test deterministic-smoke

# Default target
help:
	@echo "Iran Crisis Simulator - Pipeline Commands"
	@echo "=========================================="
	@echo ""
	@echo "Test & Validation:"
	@echo "  make test                  - Run all unit tests"
	@echo "  make validate              - Validate path registry and schemas"
	@echo "  make deterministic-smoke   - Verify pipeline reproducibility"
	@echo ""
	@echo "Fixture Pipeline (End-to-End):"
	@echo "  make run-fixture-pipeline  - Import + compile minimal test bundle"
	@echo "  make import-fixture        - Import test bundle only"
	@echo "  make compile-fixture       - Compile test bundle only"
	@echo ""
	@echo "Dashboard:"
	@echo "  make dashboard             - Launch Mission Control dashboard"
	@echo ""
	@echo "Cron/Automation:"
	@echo "  make cron-install          - Install daily cron job"
	@echo "  make cron-remove           - Remove daily cron job"
	@echo "  make cron-status           - Check cron job status"
	@echo "  make cron-test             - Test cron wrapper (runs full pipeline)"
	@echo ""
	@echo "Real Data Pipeline (when Deep Research completes):"
	@echo "  make import-real BUNDLE=<path>"
	@echo "  make compile-real RUN_DIR=<path>"
	@echo "  make simulate RUN_DIR=<path>"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean                 - Remove generated test outputs"
	@echo ""

# Run all tests
test:
	@echo "Running unit tests..."
	python3 -m unittest discover -s tests -p "test_*.py"

# Validate schemas
validate:
	@echo "Validating path registry..."
	@python3 -c "from src.pipeline.path_registry import load_default_registry; r = load_default_registry(); print(f'✓ Loaded {len(r.paths)} registered paths')"
	@echo "✓ Path registry valid"

# Import test fixture bundle
import-fixture:
	@echo "Importing test fixture bundle..."
	python3 -m src.pipeline.import_deep_research_bundle \
		--bundle tests/fixtures/minimal_bundle.json \
		--out_dir tests/fixtures/output
	@echo "✓ Import complete: tests/fixtures/output/"

# Compile test fixture
compile-fixture:
	@echo "Compiling test fixture intel..."
	python3 -m src.pipeline.compile_intel \
		--bundle tests/fixtures/minimal_bundle.json \
		--template data/iran_crisis_intel.json \
		--outdir tests/fixtures/compiled
	@echo "✓ Compilation complete: tests/fixtures/compiled/"

# Run full fixture pipeline (import + compile)
run-fixture-pipeline: clean
	@echo "=========================================="
	@echo "Running Full Fixture Pipeline"
	@echo "=========================================="
	@echo ""
	@echo "Step 1/3: Importing bundle..."
	@$(MAKE) import-fixture
	@echo ""
	@echo "Step 2/3: Compiling intel..."
	@$(MAKE) compile-fixture
	@echo ""
	@echo "Step 3/3: Verifying outputs..."
	@python3 scripts/verify_pipeline_output.py tests/fixtures/compiled
	@echo ""
	@echo "=========================================="
	@echo "✓ Fixture pipeline complete!"
	@echo "=========================================="
	@echo ""
	@echo "Outputs:"
	@echo "  - tests/fixtures/output/evidence_docs.jsonl"
	@echo "  - tests/fixtures/output/claims_deep_research.jsonl"
	@echo "  - tests/fixtures/compiled/compiled_intel.json"
	@echo "  - tests/fixtures/compiled/merge_report.json"
	@echo "  - tests/fixtures/compiled/qa_report.json"
	@echo ""

# Import real Deep Research bundle (when available)
import-real:
	@if [ -z "$(BUNDLE)" ]; then \
		echo "Error: BUNDLE parameter required"; \
		echo "Usage: make import-real BUNDLE=path/to/bundle.json"; \
		exit 1; \
	fi
	@echo "Importing real bundle: $(BUNDLE)"
	@RUN_ID=$$(basename $(BUNDLE) .json); \
	RUN_DIR="runs/$$RUN_ID"; \
	mkdir -p $$RUN_DIR; \
	python3 -m src.pipeline.import_deep_research_bundle \
		--bundle $(BUNDLE) \
		--out_dir $$RUN_DIR; \
	echo "✓ Import complete: $$RUN_DIR/"

# Compile real intel from imported bundle
compile-real:
	@if [ -z "$(RUN_DIR)" ]; then \
		echo "Error: RUN_DIR parameter required"; \
		echo "Usage: make compile-real RUN_DIR=runs/my_run"; \
		exit 1; \
	fi
	@echo "Compiling intel from: $(RUN_DIR)"
	python3 -m src.pipeline.compile_intel \
		--claims $(RUN_DIR)/claims_deep_research.jsonl \
		--template data/iran_crisis_intel.json \
		--outdir $(RUN_DIR)
	@echo "✓ Compilation complete: $(RUN_DIR)/"

# Run simulation on compiled intel
simulate:
	@if [ -z "$(RUN_DIR)" ]; then \
		echo "Error: RUN_DIR parameter required"; \
		echo "Usage: make simulate RUN_DIR=runs/my_run [RUNS=10000] [SEED=42]"; \
		exit 1; \
	fi
	@RUNS=$${RUNS:-10000}; \
	SEED=$${SEED:-42}; \
	echo "Running simulation: $$RUNS runs, seed $$SEED"; \
	python3 src/simulation.py \
		--intel $(RUN_DIR)/compiled_intel.json \
		--priors data/analyst_priors.json \
		--runs $$RUNS \
		--seed $$SEED \
		--output $(RUN_DIR)/simulation_results.json
	@echo "✓ Simulation complete: $(RUN_DIR)/simulation_results.json"

# Clean generated test outputs
clean:
	@echo "Cleaning test outputs..."
	rm -rf tests/fixtures/output
	rm -rf tests/fixtures/compiled
	@echo "✓ Clean complete"

# Quick validation (run tests + verify fixture)
quick-validate: test run-fixture-pipeline
	@echo ""
	@echo "=========================================="
	@echo "✓ Quick validation passed!"
	@echo "=========================================="

# Deterministic smoke test - verify pipeline reproducibility
deterministic-smoke:
	@echo "Running deterministic smoke test..."
	python3 scripts/deterministic_smoke.py
	@echo "✓ Deterministic smoke test passed"

# ============================================================================
# Daily Update Targets
# ============================================================================

# Run daily update with Deep Research bundle
daily:
	@BUNDLE=$${BUNDLE:-bundle_daily_$$(date +%Y-%m-%d).json}; \
	CUTOFF=$${CUTOFF:-$$(date -u +%Y-%m-%dT%H:%M:%SZ)}; \
	echo "Running daily update..."; \
	echo "  Bundle: $$BUNDLE"; \
	echo "  Cutoff: $$CUTOFF"; \
	python3 scripts/daily_update.py --bundle $$BUNDLE --cutoff $$CUTOFF

# Run daily update manually (interactive)
daily-manual:
	@echo "Starting interactive daily update..."; \
	read -p "Bundle path: " BUNDLE_PATH; \
	read -p "Cutoff (YYYY-MM-DDTHH:MM:SSZ): " CUTOFF_TIME; \
	python3 scripts/daily_update.py --bundle $$BUNDLE_PATH --cutoff $$CUTOFF_TIME

# Check status of most recent daily run
daily-status:
	@LATEST=$$(ls -t runs/ 2>/dev/null | grep "RUN_.*_daily" | head -1); \
	if [ -z "$$LATEST" ]; then \
		echo "No daily runs found"; \
	else \
		echo "Latest run: $$LATEST"; \
		echo ""; \
		echo "=== Run Manifest ==="; \
		cat runs/$$LATEST/run_manifest.json | python3 -m json.tool 2>/dev/null || echo "No manifest"; \
		echo ""; \
		echo "=== Coverage Status ==="; \
		cat runs/$$LATEST/coverage_report.json | python3 -c "import sys, json; r=json.load(sys.stdin); print(f\"Status: {r.get('status')}\"); print(f\"Total docs: {r.get('total_docs')}\"); print(f\"Farsi docs: {r.get('farsi_docs')}\"); print(f\"Buckets: {r.get('bucket_count')}\")" 2>/dev/null || echo "No coverage report"; \
	fi

# Generate diff between last two daily runs
daily-diff:
	@LATEST=$$(ls -t runs/ 2>/dev/null | grep "RUN_.*_daily" | head -1); \
	PREV=$$(ls -t runs/ 2>/dev/null | grep "RUN_.*_daily" | head -2 | tail -1); \
	if [ -z "$$PREV" ]; then \
		echo "Need at least 2 daily runs to compare"; \
	else \
		echo "Comparing $$PREV → $$LATEST"; \
		python3 -m src.pipeline.run_comparator runs/$$PREV runs/$$LATEST --output runs/$$LATEST/diff_report.json; \
		python3 -m src.report.generate_diff_report runs/$$LATEST/diff_report.json --output runs/$$LATEST/daily_summary.md; \
		echo ""; \
		cat runs/$$LATEST/daily_summary.md; \
	fi

# ============================================================================
# Dashboard
# ============================================================================

# Launch Mission Control dashboard
dashboard:
	@echo "Launching Mission Control dashboard..."
	streamlit run dashboard.py

# ============================================================================
# Cron Management
# ============================================================================

# Install cron job for automated daily runs
cron-install:
	@echo "Installing cron job..."
	bash scripts/setup_cron.sh

# Remove cron job
cron-remove:
	@echo "Removing cron job..."
	@crontab -l 2>/dev/null | grep -v "run_daily_cron.sh" | crontab - && echo "Cron job removed." || echo "No cron job found."

# Check cron job status
cron-status:
	@echo "Current cron jobs:"
	@crontab -l 2>/dev/null | grep -E "(daily|iran|cron)" || echo "No matching cron jobs found"
	@echo ""
	@if [ -f .daily_update.lock ]; then \
		echo "WARNING: Lock file exists (.daily_update.lock)"; \
		echo "  PID: $$(cat .daily_update.lock)"; \
	else \
		echo "No active lock file"; \
	fi

# Test cron wrapper script (runs full pipeline)
cron-test:
	@echo "Testing cron wrapper script..."
	@echo "This will run the full auto-ingest pipeline."
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] && bash scripts/run_daily_cron.sh || echo "Aborted."
