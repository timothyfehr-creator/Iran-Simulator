# New Agent Workflow & Prompts - Quick Reference

## What Changed (January 2026)

### Phase 1: Critical Bug Fix ✅
Fixed daily gates windowing bug that was causing false negative source coverage warnings.

### Phase 2: Full Ingestion Layer ✅
Built complete automated evidence collection system with 10+ sources.

### Phase 3: New Agent Prompts ✅
Created two new prompts for source gathering and schema extraction/analysis.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Evidence Collection (AUTOMATED or MANUAL)              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  AUTO: src/ingest/ system (RSS, web scraping)           │
│    ├─ 10+ sources (ISW, HRANA, Reuters, BBC, etc.)      │
│    ├─ GPT-4 claim extraction                            │
│    └─ Output: evidence_docs.jsonl, candidate_claims     │
│                                                          │
│  MANUAL: Prompt 03 (Deep Research conversation)         │
│    ├─ Multi-source OSINT gathering                      │
│    ├─ Manual citation and claim extraction              │
│    └─ Output: same format as auto                       │
│                                                          │
└─────────────────┬───────────────────────────────────────┘
                  │
        ┌─────────▼──────────────┐
        │  Evidence Bundle       │
        │  (JSONL + metadata)    │
        └─────────┬──────────────┘
                  │
    ┌─────────────▼─────────────────────┐
    │  Prompt 04: Claude Opus 5.2       │
    │  (Schema Extraction & Analysis)   │
    ├───────────────────────────────────┤
    │                                   │
    │  Function 1: Compile Intel        │
    │    ├─ Schema validation           │
    │    ├─ Conflict resolution         │
    │    └─ Output: compiled_intel.json │
    │                                   │
    │  Function 2: Generate Priors      │
    │    ├─ Base rate anchoring         │
    │    ├─ Probability calibration     │
    │    └─ Output: analyst_priors.json │
    │                                   │
    │  Function 3: Analyze Results      │
    │    ├─ Simulation interpretation   │
    │    ├─ Sensitivity analysis        │
    │    └─ Output: executive_summary   │
    │                                   │
    └─────────────┬─────────────────────┘
                  │
        ┌─────────▼──────────┐
        │  Monte Carlo       │
        │  Simulation        │
        │  (10,000 runs)     │
        └────────────────────┘
```

---

## Five Agent Prompts Explained

### Prompt 01: Research Agent (LEGACY)
**File:** `prompts/01_research_prompt.md`
**Purpose:** Original comprehensive intelligence collection prompt
**Status:** Still valid for single-pass Deep Research, but superseded by Prompts 03+04 for production pipeline
**Output:** Complete `iran_crisis_intel.json` in one go

**When to use:**
- Quick manual intelligence gathering
- Single-source comprehensive analysis
- Educational/testing purposes

### Prompt 02: Security Analyst Agent
**File:** `prompts/02_security_analyst_prompt.md`
**Purpose:** Convert intelligence into calibrated probability estimates
**Status:** Core production prompt (unchanged)
**Output:** `analyst_priors.json` with base rate anchoring

**When to use:**
- Always after intel compilation
- For probability calibration and prior generation
- Requires both `compiled_intel.json` and `compiled_baseline.json`

### Prompt 03: Deep Research Source Gathering (NEW)
**File:** `prompts/03_deep_research_source_gathering.md`
**Purpose:** Multi-source OSINT collection with proper citations
**Status:** NEW production prompt for evidence gathering
**Output:** Evidence bundle (evidence_docs.jsonl, candidate_claims.jsonl, source_index.json)

**When to use:**
- Manual evidence collection in Deep Research conversation
- Custom source gathering when automated system can't access a source
- Quality control / validation of automated ingestion

**Key Features:**
- Source diversity requirements (3+ buckets)
- Proper access/bias grading ([A-D][1-4])
- Conflict preservation (don't reconcile contradictions)
- Citation discipline (every claim traceable to source)

### Prompt 04: Schema Extraction & Analysis (NEW)
**File:** `prompts/04_schema_extraction_and_analysis.md`
**Purpose:** THREE-IN-ONE prompt for Claude Opus 5.2
**Status:** NEW production prompt (replaces manual compilation + analysis)
**Output:** Multiple deliverables depending on function

**Function 1: Schema-Compliant Intel Compilation**
- Input: Evidence bundle + baseline knowledge
- Output: `compiled_intel.json` (strictly schema-compliant)
- Key: Conflict resolution, gap documentation, NO fabrication

**Function 2: Calibrated Prior Generation**
- Input: `compiled_intel.json` + `compiled_baseline.json`
- Output: `analyst_priors.json` (probability estimates)
- Key: Base rate anchoring, transparent reasoning chains

**Function 3: Simulation Results Analysis**
- Input: `simulation_results.json` + intel + priors
- Output: `simulation_analysis.md`, `executive_summary.md`, sensitivity notes
- Key: Decision-relevant insights, uncertainty transparency

**Why Opus 5.2:**
- Superior schema adherence (critical for Function 1)
- Strong probabilistic reasoning (critical for Function 2)
- Long-context handling (100k+ token evidence bundles)
- Analytical depth for multi-factor simulation interpretation

### Prompt 05: Simulation Engine
**Not a prompt, but included for completeness**
**File:** `src/simulation.py`
**Purpose:** Run Monte Carlo simulation
**Input:** `compiled_intel.json` + `analyst_priors.json`
**Output:** `simulation_results.json`

---

## Workflow Comparison: Old vs New

### OLD Workflow (Pre-January 2026)

```
1. Manual Deep Research with Prompt 01
   └─> iran_crisis_intel.json (comprehensive, single-pass)

2. Manual Analyst Priors with Prompt 02
   └─> analyst_priors.json

3. Run Simulation (Python)
   └─> simulation_results.json

4. Manual interpretation (no structured prompt)
```

**Problems:**
- Single-pass research limited source diversity
- No automated updates
- Manual claim extraction error-prone
- No standardized results analysis

### NEW Workflow: Automated

```
1. Automated Evidence Fetching (src/ingest/)
   ├─> Fetches from 10+ sources automatically
   ├─> GPT-4 extracts claims
   └─> evidence_docs.jsonl, candidate_claims.jsonl

2. Prompt 04 Function 1: Compile Intel (Opus 5.2)
   ├─> Validates schema
   ├─> Resolves conflicts
   └─> compiled_intel.json

3. Prompt 04 Function 2: Generate Priors (Opus 5.2)
   ├─> Anchors to base rates
   ├─> Documents reasoning
   └─> analyst_priors.json

4. Run Simulation (Python)
   └─> simulation_results.json

5. Prompt 04 Function 3: Analyze Results (Opus 5.2)
   ├─> Interprets outcomes
   ├─> Sensitivity analysis
   └─> executive_summary.md
```

**Advantages:**
- Source diversity (10+ sources, 3+ buckets)
- Daily automation (cron-compatible)
- Conflict preservation (regime vs opposition sources)
- Structured analysis output (policymaker-ready)

### NEW Workflow: Manual (for custom collection)

```
1. Prompt 03: Manual Evidence Gathering (Deep Research)
   ├─> User gathers from custom sources
   ├─> Follows citation standards
   └─> evidence_docs.jsonl, candidate_claims.jsonl

2. Prompt 04 Functions 1-3: Same as automated
   └─> (Same outputs as automated workflow)
```

---

## Command Reference

### Automated Daily Update
```bash
# Set API key for claim extraction
export OPENAI_API_KEY=sk-your-key-here

# Run full automated pipeline
python scripts/daily_update.py --auto-ingest --cutoff 2026-01-11T23:59:59Z

# Skip simulation (compile only)
python scripts/daily_update.py --auto-ingest --no-simulate
```

### Manual Evidence Fetching (Test)
```bash
# Fetch from all sources (last 24 hours)
python -m src.ingest.coordinator --since-hours 24 --output ingest/test

# Extract claims from fetched evidence
python -m src.ingest.extract_claims \
    --evidence ingest/test/evidence_docs.jsonl \
    --output ingest/test/claims_extracted.jsonl \
    --model gpt-4
```

### Using Prompts 03 and 04

**For Prompt 03 (Deep Research conversation):**
1. Open Deep Research conversation
2. Load `prompts/03_deep_research_source_gathering.md`
3. Follow workflow to generate evidence bundle
4. Download: evidence_docs.jsonl, candidate_claims.jsonl, source_index.json

**For Prompt 04 (Claude Opus 5.2 or Claude Code):**
```
# In Claude conversation or Projects:
1. Load `prompts/04_schema_extraction_and_analysis.md`
2. Provide evidence bundle + compiled_baseline.json
3. Request Function 1 (compile intel)
4. Request Function 2 (generate priors)
5. After simulation, request Function 3 (analyze results)
```

---

## Source Configuration

Edit `config/sources.yaml` to add/modify sources:

```yaml
sources:
  - id: custom_source
    name: "Custom News Agency"
    type: rss  # or 'web'
    bucket: wires  # osint_think_tank, ngos, regime_outlets, persian_services, wires
    urls:
      - https://example.com/rss
    access_grade: B  # A/B/C/D
    bias_grade: 2    # 1/2/3/4
    language: en     # en, fa, ar
    fetcher: src.ingest.fetch_rss  # or src.ingest.fetch_web
    enabled: true
```

For web scrapers, add CSS selectors:
```yaml
  - id: custom_scraper
    type: web
    selectors:
      article: ".article-container"
      title: "h1.title"
      date: "time.published"
      content: ".article-body"
```

---

## Quality Gates

### Evidence Bundle Quality (Prompt 03 or Auto)
- ✅ Minimum 10 evidence_docs (ideally 15-20)
- ✅ Minimum 30 candidate_claims (ideally 50-100)
- ✅ At least 3 source buckets covered
- ✅ All source_grades follow [A-D][1-4] format
- ✅ Conflicting claims preserved (not reconciled)

### Schema Compliance (Prompt 04 Function 1)
- ✅ All paths exist in `01_research_prompt.md` schema
- ✅ All enum values match exactly (case-sensitive)
- ✅ All field types correct (int vs string vs bool)
- ✅ No fabricated data (use `null` for unknowns)

### Prior Calibration (Prompt 04 Function 2)
- ✅ Every estimate anchored to base rate from `compiled_baseline.json`
- ✅ Reasoning chains transparent and auditable
- ✅ Wide confidence intervals where uncertainty high
- ✅ Regime outcomes sum exactly to 1.0

---

## FAQ

**Q: Do I need both Prompt 03 and Prompt 04?**
A: For automated pipeline: NO (system uses auto-ingest). For manual: YES (03 for gathering, 04 for compilation/analysis).

**Q: Can I use Prompt 01 instead of Prompt 03?**
A: Yes, but Prompt 03 is better for:
- Multi-source diversity requirements
- Proper citation discipline
- Integration with automated pipeline

**Q: Why Claude Opus 5.2 for Prompt 04?**
A: Superior schema adherence, probabilistic reasoning, long-context handling. Sonnet can work but may have more schema errors.

**Q: What if automated ingestion fails for a source?**
A: Use Prompt 03 to manually gather from that source, then merge with auto-fetched data.

**Q: How often to run automated daily updates?**
A: Daily (via cron). Default cutoff is end-of-day UTC to capture all same-day docs.

**Q: Can I add custom sources to automated pipeline?**
A: Yes! Edit `config/sources.yaml` and add RSS feed or web scraper config.

---

## Troubleshooting

**Issue: "No ISW update for date" warning**
**Fix:** This was the windowing bug. Now fixed with 24-hour window logic.

**Issue: Claim extraction fails (no OpenAI key)**
**Fix:** `export OPENAI_API_KEY=sk-...` or pipeline will skip claim extraction gracefully.

**Issue: Schema validation errors in compiled_intel.json**
**Fix:** Use Prompt 04 with Claude Opus 5.2 (better schema adherence than Sonnet).

**Issue: Web scraper breaks (site changed)**
**Fix:** Update CSS selectors in `config/sources.yaml` for that source.

**Issue: Conflicting casualty figures**
**Fix:** This is expected. Prompt 04 Function 1 will triangulate and document in methodology.

---

## Next Steps

1. **Test automated pipeline**: `python scripts/daily_update.py --auto-ingest`
2. **Review Prompt 03**: Understand manual evidence gathering workflow
3. **Experiment with Prompt 04**: Try all three functions with sample evidence bundle
4. **Add custom sources**: Edit `config/sources.yaml` for your specific intel needs
5. **Set up cron**: Schedule daily automated updates

Questions? Check `CLAUDE.md` for detailed Claude Code instructions or review individual prompt files for full specifications.
