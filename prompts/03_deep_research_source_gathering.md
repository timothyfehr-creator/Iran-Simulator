# IRAN CRISIS EVIDENCE COLLECTION & BUNDLE GENERATION
## Deep Research Query for Multi-Source OSINT Gathering

**Classification:** UNCLASSIFIED // FOR SIMULATION USE
**Requirement ID:** IRAN-2026-EVIDENCE-001
**Date:** January 10, 2026
**Purpose:** Gather raw evidence from multiple sources, create structured citations, and generate evidence bundle for downstream intelligence compilation

---

## SECTION 1: COLLECTION MISSION

### Your Role

You are an OSINT collection specialist tasked with:
1. **Gathering raw evidence** from authoritative sources across multiple buckets
2. **Creating structured citations** with proper source grading
3. **Extracting discrete factual claims** from each evidence document
4. **Building evidence bundles** in the required schema for pipeline ingestion

### Collection Philosophy

- **Breadth over depth initially** - Cover all source buckets before deep-diving
- **Primary sources preferred** - Official statements, firsthand observation, leaked documents
- **Triangulation required** - Cross-verify factual claims across 2+ sources when possible
- **Bias transparent** - Document source positioning, don't hide it
- **Uncertainty explicit** - Conflicting reports are valuable data, not problems to resolve

### Output Products

1. **evidence_docs.jsonl** - One document per source article/report
2. **candidate_claims.jsonl** - Discrete factual claims extracted from evidence
3. **source_index.json** - Registry of all sources used with access/bias grades

---

## SECTION 2: SOURCE BUCKETS & GRADING SYSTEM

### Required Source Diversity

Your evidence bundle MUST include documents from at least 3 of 5 buckets:

**BUCKET 1: OSINT Think Tanks**
- Institute for the Study of War (ISW) / Critical Threats Project (CTP)
- Carnegie Endowment, CSIS, RAND, Brookings
- **Access Grade:** Typically B (informed analysis, not direct access)
- **Bias Grade:** Typically 2 (positioned but professional)

**BUCKET 2: NGOs / Rights Monitors**
- Human Rights Activists News Agency (HRANA)
- Iran Human Rights (NGO)
- Amnesty International, Human Rights Watch
- **Access Grade:** A-B (direct witness accounts, on-ground networks)
- **Bias Grade:** 2-3 (advocacy-adjacent but fact-focused)

**BUCKET 3: Wire Services**
- Reuters, Associated Press (AP), Agence France-Presse (AFP)
- Bloomberg (for economic data)
- **Access Grade:** A-B (bureau reporters, official statements)
- **Bias Grade:** 1 (neutral professional standards)

**BUCKET 4: Persian-Language Services**
- BBC Persian, Radio Farda, Voice of America Persian
- Iran International
- **Access Grade:** B (regional sources, exile networks)
- **Bias Grade:** 2-3 (opposition-leaning but journalistic)

**BUCKET 5: Regime Outlets**
- Islamic Republic News Agency (IRNA)
- Fars News, Tasnim, Mehr News, PressTV
- **Access Grade:** A (official statements, regime perspective)
- **Bias Grade:** 4 (state propaganda, but reveals regime narrative)

### Source Grading Framework

**ACCESS QUALITY** (How do they know?)
- **A - Direct**: Official statements, on-scene reporting, leaked documents, verified footage
- **B - Informed**: Well-placed sources, expert analysis with access, regional networks
- **C - Derived**: Open-source analysis, inference from patterns, satellite imagery analysis
- **D - Speculative**: Opinion, prediction, single anonymous source, unverified claims

**BIAS ASSESSMENT** (What's their agenda?)
- **1 - Neutral**: Wire services with editorial standards, peer-reviewed academic work
- **2 - Positioned but professional**: Think tanks, quality regional media, NGOs with methodology
- **3 - Advocacy-adjacent**: Opposition-linked outlets, government-friendly media, partisan experts
- **4 - Propaganda**: State outlets (IRNA, Fars), MEK-affiliated, regime-change advocacy groups

**Combined Notation:** [A1] = Direct access, neutral | [B3] = Informed, advocacy-adjacent | [C4] = Derived, propaganda

### Source Grading Rules

1. **Default to organization baseline** - ISW defaults to B2, Reuters to A1, IRNA to A4
2. **Upgrade for exceptional access** - Leaked document from regime outlet = A4 (not C4)
3. **Downgrade for poor methodology** - NGO citing "activists say" without verification = C3
4. **Grade the claim, not the org** - Same source can produce A1 and C3 claims in same article

---

## SECTION 3: EVIDENCE DOCUMENT SCHEMA

For each source article/report, create one evidence_doc entry:

```json
{
  "doc_id": "ISW_20260110_1830_a3f9d2c1",
  "source_id": "SRC_ISW",
  "organization": "Institute for the Study of War",
  "title": "Iran Update, January 10, 2026",
  "url": "https://understandingwar.org/backgrounder/iran-update-january-10-2026",
  "published_at_utc": "2026-01-10T18:30:00Z",
  "retrieved_at_utc": "2026-01-10T20:15:00Z",
  "language": "en",
  "raw_text": "Full text of article here (up to 50KB)...",
  "translation_en": null,
  "translation_confidence": null,
  "access_grade": "B",
  "bias_grade": 2,
  "kiq_tags": ["KIQ-1", "KIQ-2"],
  "topic_tags": ["protest_metrics", "regime_response"],
  "key_excerpts": [
    {
      "excerpt": "IRGC sources report 12 casualties among Basij forces in Tehran clashes",
      "relevance": "First official admission of security force casualties",
      "confidence": "HIGH"
    }
  ]
}
```

### Field Requirements

**Mandatory:**
- `doc_id`: Unique identifier (format: SOURCEID_YYYYMMDD_HHMM_HASH)
- `source_id`: Standardized source ID (e.g., SRC_ISW, SRC_REUTERS, SRC_HRANA)
- `organization`: Full organization name
- `title`: Article/report title
- `url`: Permanent link (archive.org link if original may disappear)
- `published_at_utc`: When source published (ISO 8601)
- `retrieved_at_utc`: When you accessed it (ISO 8601)
- `language`: ISO 639-1 code (en, fa, ar, etc.)
- `raw_text`: Full article text (truncate at 50KB if needed)
- `access_grade`: A/B/C/D
- `bias_grade`: 1/2/3/4

**Optional but encouraged:**
- `translation_en`: English translation if source is non-English
- `kiq_tags`: Which Key Intelligence Questions this addresses
- `topic_tags`: Relevant data categories
- `key_excerpts`: Notable quotes with relevance notes

### Collection Standards

1. **Capture full text** - Don't summarize, include complete article text in `raw_text`
2. **Preserve timestamps** - Use exact publication times, not "today" or "recently"
3. **Archive links** - For ephemeral sources, use archive.org or similar
4. **Language handling** - If Farsi/Arabic, include original in `raw_text` and translation in `translation_en`
5. **Version control** - If article is updated, create new doc_id with same source

---

## SECTION 4: CLAIM EXTRACTION SCHEMA

For each discrete factual claim, create one candidate_claim entry:

```json
{
  "claim_id": "CLM_20260110_0001",
  "claim_class": "HARD_FACT",
  "path": "current_state.casualties.security_forces.killed.basij",
  "value": 12,
  "value_type": "integer",
  "as_of_utc": "2026-01-10T12:00:00Z",
  "source_doc_refs": ["ISW_20260110_1830_a3f9d2c1"],
  "source_grade": "B2",
  "confidence": "MEDIUM",
  "triangulated": false,
  "notes": "ISW citing IRGC sources; regime typically underreports casualties but first official admission",
  "conflicts_with": null,
  "supersedes": null
}
```

### Claim Classification

**HARD_FACT** - Objectively verifiable, specific
- Examples: "12 protesters killed in Tehran on Jan 8", "Rial hit 850,000 to USD", "Khamenei appeared on TV Jan 9"
- Requirements: Specific numbers, dates, locations, named individuals
- Source grade: Requires A1/A2/B1 OR triangulation from 2+ B2 sources

**STRUCTURAL** - Background/contextual facts (slower-changing)
- Examples: "IRGC controls ~40% of Iranian economy", "Kurds comprise 10% of population"
- Requirements: Documented in authoritative sources, less time-sensitive
- Source grade: B1/B2/C1 acceptable with date noted

**SOFT_FACT** - Observed but ambiguous
- Examples: "Protests appear to be growing in intensity", "Morale among Basij seems low"
- Requirements: Qualitative observation, clear methodology for assessment
- Source grade: Flag as assessment, document observer's access level

**ASSESSMENT** - Expert judgment/inference
- Examples: "Regime cohesion appears to be fraying", "US unlikely to intervene militarily"
- Requirements: Clearly labeled as analysis, document expert credentials
- Source grade: Acceptable from B1/B2 only if reasoning is transparent

### Path Registry

All `path` values must map to the intelligence schema from `01_research_prompt.md`:

**Protest Metrics:**
- `current_state.protest_metrics.time_series[*].cities_affected`
- `current_state.protest_metrics.current_snapshot.provinces_affected`
- `current_state.protest_metrics.current_snapshot.intensity_trend`
- `current_state.protest_metrics.protest_character.organizational_level`

**Casualties:**
- `current_state.casualties.protesters.killed.{low|mid|high}`
- `current_state.casualties.security_forces.killed.{total|irgc|basij|police}`
- `current_state.casualties.children.killed`

**Economic:**
- `current_state.economic_conditions.rial_usd_rate.{official|market}`
- `current_state.economic_conditions.inflation.official_annual_percent`
- `current_state.economic_conditions.oil_exports_bpd`

**Security Posture:**
- `current_state.security_posture.force_deployment.level`
- `current_state.security_posture.rules_of_engagement_observed.live_fire`

**Regime Analysis:**
- `regime_analysis.elite_cohesion.assessment`
- `regime_analysis.security_force_loyalty.irgc.assessment`
- `regime_analysis.khamenei.health_indicators.public_appearances_last_30_days`

**External Actors:**
- `external_actors.united_states.force_posture.troops_in_region`
- `external_actors.israel.recent_actions[*]`

### Claim Extraction Rules

1. **One claim, one path** - Don't bundle multiple facts into single claim
2. **Atomic values** - Break down complex statements into discrete claims
3. **Timestamp precision** - Use `as_of_utc` for when claim was true, not when reported
4. **Conflicting claims preserved** - Don't reconcile contradictions; document both
5. **Update chains tracked** - Use `supersedes` to link newer data to older claims

**Example Decomposition:**
```
Source text: "Protests in Tehran on Jan 9 drew an estimated 50,000-100,000 participants,
marking the largest gathering since the movement began."

Decompose into:
CLM_001: path=current_state.protest_metrics.time_series[9].estimated_participants.low, value=50000
CLM_002: path=current_state.protest_metrics.time_series[9].estimated_participants.high, value=100000
CLM_003: path=current_state.protest_metrics.time_series[9].cities_affected, value=["Tehran"]
CLM_004: path=current_state.protest_metrics.current_snapshot.intensity_trend, value="ESCALATING"
```

---

## SECTION 5: COLLECTION WORKFLOW

### Phase 1: Rapid Source Survey (30 min)

**Goal:** Identify what's available across all buckets

1. Check ISW/CTP daily update (if published today)
2. Query wire services (Reuters, AP) for "Iran protests" in last 24h
3. Check HRANA front page for casualty reports
4. Scan BBC Persian / Radio Farda headlines
5. Check IRNA / Fars for regime narrative

**Output:** Mental map of coverage landscape, identify gaps

### Phase 2: Priority Evidence Collection (60 min)

**Goal:** Gather documents covering Priority 1 requirements from `01_research_prompt.md`

**Critical data points to cover:**
- Current protest locations and intensity (TODAY's status)
- Latest casualty figures (triangulated across sources)
- Security force deployment/rules of engagement
- Internet/blackout status
- Economic indicators (rial rate, if updated)
- Key actor statements (Khamenei, US officials, IRGC)

**Collection targets:**
- 3-5 documents from OSINT think tanks (ISW, CSIS, etc.)
- 2-3 documents from NGOs/rights monitors (HRANA, IHR, Amnesty)
- 3-5 documents from wire services (Reuters, AP for factual grounding)
- 2-3 documents from Persian services (BBC Persian, Radio Farda)
- 1-2 documents from regime outlets (IRNA, Fars for regime perspective)

**Minimum acceptable bundle:** 10 evidence_docs covering at least 3 buckets

### Phase 3: Claim Extraction (45 min)

**Goal:** Extract 30-100 discrete factual claims from collected evidence

**Extraction priorities:**
1. **Time-series data** - Daily protest metrics (participants, cities, casualties)
2. **Current snapshot** - Latest intensity assessment, geographic spread
3. **Actor statements** - Direct quotes with timestamps
4. **Economic metrics** - Rial rate, inflation, oil exports
5. **Security indicators** - Force deployments, ROE changes, defection signals

**Quality controls:**
- Every claim must cite at least one source_doc_ref
- Every claim must have source_grade (derived from doc's access_grade + bias_grade)
- Conflicting claims preserved (don't pick "winners")
- Ranges preferred over point estimates (low/mid/high for casualties)

### Phase 4: Source Index & QA (15 min)

**Goal:** Create source_index.json and validate bundle quality

**source_index.json format:**
```json
[
  {
    "source_id": "SRC_ISW",
    "organization": "Institute for the Study of War",
    "default_access_grade": "B",
    "default_bias_grade": 2,
    "language": "en",
    "notes": "OSINT think tank - daily Iran updates"
  },
  {
    "source_id": "SRC_HRANA",
    "organization": "Human Rights Activists News Agency",
    "default_access_grade": "B",
    "default_bias_grade": 3,
    "language": "fa",
    "notes": "Iran-based human rights monitor - strong on casualty data"
  }
]
```

**Quality gates:**
- [ ] At least 10 evidence_docs
- [ ] At least 3 source buckets represented
- [ ] At least 30 candidate_claims
- [ ] All claims have valid paths from schema
- [ ] All source_grades follow [A-D][1-4] format
- [ ] All timestamps in ISO 8601 UTC
- [ ] source_index includes all cited sources

---

## SECTION 6: SOURCE-SPECIFIC GUIDANCE

### ISW / Critical Threats Project

**What they're good for:**
- Daily aggregation of protest activity across Iran
- Geolocation of incidents via social media analysis
- Assessment of regime response patterns
- Historical context and trend analysis

**What to watch for:**
- Access grade = B (they aggregate, rarely have direct access)
- Bias grade = 2 (pro-US foreign policy establishment, but professional)
- They cite sources - trace back to primary sources when possible
- Their casualty figures come from other NGOs (cite the NGO, not ISW)

**Collection tip:** ISW daily updates are comprehensive but derivative. Use them to identify other sources to pursue.

### HRANA (Human Rights Activists News Agency)

**What they're good for:**
- Granular casualty data (names, ages, cities)
- Detention figures
- Direct witness accounts from inside Iran
- Documentation of security force actions

**What to watch for:**
- Access grade = A-B (on-ground networks, firsthand accounts)
- Bias grade = 3 (opposition-aligned, but fact-focused)
- Persian language primary, English sometimes delayed
- Casualty figures may be incomplete (not inflated, but undercount likely)

**Collection tip:** HRANA is the gold standard for casualty data. Cross-reference their figures with regime sources for triangulation.

### Reuters / Associated Press

**What they're good for:**
- Factual grounding (locations, dates, official statements)
- Economic data (rial rates, oil prices)
- International response (UN, EU, US statements)
- Neutral framing (less useful for trend assessment)

**What to watch for:**
- Access grade = A-B (bureau reporters, official sources)
- Bias grade = 1 (neutral wire service standards)
- Limited on-ground access in Iran (bureau closed)
- Strong on economic metrics, weaker on protest intensity

**Collection tip:** Use for hard facts (numbers, quotes, dates). Don't rely on for trend assessments.

### BBC Persian / Radio Farda

**What they're good for:**
- Aggregation of Persian-language social media
- Interviews with opposition figures
- Regional context (Turkey, Iraq, Azerbaijan angles)
- Information environment analysis (what Iranians are seeing)

**What to watch for:**
- Access grade = B (exile networks, social media monitoring)
- Bias grade = 2-3 (opposition-leaning, but journalistic standards)
- English summaries available, full content in Farsi
- Strong on diaspora perspectives, weaker on regime internal dynamics

**Collection tip:** Useful for understanding protest movement narratives and diaspora coordination.

### IRNA / Fars / Tasnim (Regime Outlets)

**What they're good for:**
- Official regime narrative and framing
- Statements by regime officials (Khamenei, IRGC, government)
- Regime's version of casualty figures (for comparison)
- Indicators of regime confidence/concern (what they choose to report)

**What to watch for:**
- Access grade = A (official statements, regime perspective)
- Bias grade = 4 (state propaganda)
- Systematic undercount of protester casualties
- Systematic overcount (or invention) of "rioter" violence
- What they DON'T report is as revealing as what they do

**Collection tip:** Don't dismiss regime sources. Their framing and omissions are valuable intelligence. Treat casualty claims skeptically but document them.

---

## SECTION 7: COMMON COLLECTION ERRORS

### Error 1: Single-Source Factual Claims

**Problem:** "Protesters killed in Tehran: 47 [B3]"

**Why it's wrong:** Hard facts (casualty numbers) require triangulation or A1/A2/B1 sourcing

**Fix:** Either find corroborating source OR downgrade claim to "CLM_CLASS: SOFT_FACT" with note about single-source limitation

### Error 2: Bundling Multiple Facts

**Problem:**
```json
{
  "path": "current_state.protest_metrics",
  "value": {"cities": 23, "participants": 100000, "trend": "ESCALATING"}
}
```

**Why it's wrong:** One claim per path, atomic values only

**Fix:** Create three separate claims with specific paths

### Error 3: Mixing Observation and Analysis

**Problem:** "IRGC deployed heavy presence in Tehran, indicating regime concern [B2]"

**Why it's wrong:** "IRGC deployed" is HARD_FACT, "indicating concern" is ASSESSMENT

**Fix:** Two claims:
- CLM_001: path=security_posture.deployment, value="heavy", class=HARD_FACT
- CLM_002: path=regime_analysis.elite_cohesion, value="strained", class=ASSESSMENT, notes="inferred from deployment"

### Error 4: Imprecise Timestamps

**Problem:** `"as_of_utc": "2026-01-10T00:00:00Z"` for data that's actually "sometime on Jan 10"

**Why it's wrong:** 00:00:00 implies precision we don't have; downstream systems interpret this literally

**Fix:** Use midpoint or end-of-day: `"as_of_utc": "2026-01-10T12:00:00Z"` with note "exact time unknown, using midday"

### Error 5: Failing to Preserve Conflicts

**Problem:** HRANA says 47 dead, IRNA says 12 dead → average to 30

**Why it's wrong:** Contradiction is valuable data about bias and information environment

**Fix:** Two claims:
- CLM_001: value=47, source_doc_refs=[HRANA], conflicts_with=[CLM_002]
- CLM_002: value=12, source_doc_refs=[IRNA], conflicts_with=[CLM_001]

### Error 6: Path Invention

**Problem:** `"path": "regime_analysis.irgc_morale_index"`

**Why it's wrong:** Path doesn't exist in schema; downstream compilation will fail

**Fix:** Use closest valid path: `regime_analysis.security_force_loyalty.irgc.morale_indicators` (string type, not numeric)

---

## SECTION 8: OUTPUT DELIVERABLES

### Bundle Structure

```
iran_crisis_evidence_bundle/
├── metadata.json
├── evidence_docs.jsonl
├── candidate_claims.jsonl
├── source_index.json
└── collection_notes.md
```

### metadata.json

```json
{
  "bundle_id": "BUNDLE_20260110_2145",
  "generated_at": "2026-01-10T21:45:00Z",
  "data_cutoff_utc": "2026-01-10T12:00:00Z",
  "collection_window": {
    "start": "2026-01-09T12:00:00Z",
    "end": "2026-01-10T12:00:00Z"
  },
  "crisis_day": 14,
  "collector_id": "DEEP_RESEARCH_AGENT",
  "summary": {
    "total_evidence_docs": 12,
    "total_candidate_claims": 47,
    "source_buckets_covered": ["osint_think_tank", "ngos", "wires", "persian_services", "regime_outlets"],
    "languages": ["en", "fa"],
    "kiq_coverage": ["KIQ-1", "KIQ-2", "KIQ-3", "KIQ-5"]
  },
  "collection_notes": "Strong coverage of protest metrics and regime response. Weak on US force posture (no new data). Conflicting casualty figures preserved for triangulation.",
  "known_gaps": [
    "No ISW update published today (used yesterday's)",
    "Limited Baloch region coverage (language barrier)",
    "No direct elite faction statements (no leaks detected)"
  ]
}
```

### evidence_docs.jsonl

One JSON object per line (not an array):

```jsonl
{"doc_id": "ISW_20260110_1830_a3f9d2c1", "source_id": "SRC_ISW", ...}
{"doc_id": "HRANA_20260110_1200_f8e2b4a7", "source_id": "SRC_HRANA", ...}
{"doc_id": "REUTERS_20260110_0930_c4d6e1f2", "source_id": "SRC_REUTERS", ...}
```

### candidate_claims.jsonl

One JSON object per line:

```jsonl
{"claim_id": "CLM_20260110_0001", "path": "current_state.casualties.protesters.killed.mid", ...}
{"claim_id": "CLM_20260110_0002", "path": "current_state.protest_metrics.current_snapshot.intensity_trend", ...}
```

### collection_notes.md (optional)

Narrative summary for human reviewers:

```markdown
# Collection Notes - January 10, 2026

## Sources Accessed

- ISW daily update (Jan 9, no Jan 10 update yet)
- HRANA casualty tracker (updated Jan 10 12:00 UTC)
- Reuters: 3 articles on Iran protests
- BBC Persian: Front page scan
- IRNA: Official casualty statement from IRGC

## Key Findings

- Casualty figures diverging significantly (HRANA: 47 dead, IRNA: 12 dead)
- First regime admission of Basij casualties (12 killed)
- Protest intensity appears to be escalating in northwestern cities
- No new US policy statements (using Jan 8 SecState remarks)

## Collection Challenges

- ISW update delayed (using yesterday's analysis)
- Limited Baloch coverage (few English sources, Farsi sources inaccessible)
- No direct IRGC internal communications (no leaks detected)

## Triangulation Status

- Casualty figures: 3 sources (HRANA, Iran HR, IRNA) - conflicting
- Protest locations: 4 sources (ISW, Reuters, BBC Persian, HRANA) - aligned
- Economic data: 2 sources (Reuters, IRNA) - aligned on rial rate
```

---

## SECTION 9: VALIDATION CHECKLIST

Before submitting bundle:

**Completeness:**
- [ ] At least 10 evidence_docs (ideally 15-20)
- [ ] At least 30 candidate_claims (ideally 50-100)
- [ ] At least 3 source buckets represented
- [ ] At least 2 Farsi-language sources included
- [ ] metadata.json generated with summary stats

**Schema Compliance:**
- [ ] All evidence_doc fields present and valid types
- [ ] All claim paths exist in intel schema from prompt 01
- [ ] All source_grades follow [A-D][1-4] format
- [ ] All timestamps in ISO 8601 UTC format
- [ ] All doc_ids and claim_ids are unique

**Source Quality:**
- [ ] No sources below C2 used for HARD_FACT claims (unless triangulated)
- [ ] Regime sources (grade 4) balanced with opposition sources (grade 3)
- [ ] At least one A1 or B1 source included
- [ ] source_index.json includes all cited sources

**Analytical Rigor:**
- [ ] Conflicting claims preserved (not resolved)
- [ ] Ranges used for uncertain quantities (casualties, participants)
- [ ] Assessment claims clearly labeled (not presented as facts)
- [ ] Known gaps explicitly documented in metadata

**Traceability:**
- [ ] Every claim cites at least one source_doc_ref
- [ ] Every cited doc_id exists in evidence_docs.jsonl
- [ ] Key excerpts captured for important claims
- [ ] Superseded claims linked via supersedes field

---

## SECTION 10: EXAMPLE BUNDLE

### Example: Single Evidence Doc + Extracted Claims

**evidence_docs.jsonl entry:**
```json
{
  "doc_id": "HRANA_20260110_1200_f8e2b4a7",
  "source_id": "SRC_HRANA",
  "organization": "Human Rights Activists News Agency",
  "title": "Protest Casualties Update - January 10, 2026",
  "url": "https://en-hrana.org/protest-casualties-january-10-2026",
  "published_at_utc": "2026-01-10T12:00:00Z",
  "retrieved_at_utc": "2026-01-10T14:30:00Z",
  "language": "en",
  "raw_text": "According to reports gathered by HRANA, as of January 10, 2026, at least 47 individuals have been killed during protests across Iran since December 28, 2025. This includes 3 children under the age of 18. HRANA has verified the identities of 31 of these individuals through family members and eyewitness accounts. An additional 16 deaths have been reported but not yet verified. Security forces have primarily used live ammunition in Tehran, Tabriz, and Kermanshah. Approximately 320 protesters remain in detention according to families contacted by HRANA.",
  "access_grade": "B",
  "bias_grade": 3,
  "kiq_tags": ["KIQ-1", "KIQ-2"],
  "topic_tags": ["casualties", "protest_metrics"],
  "key_excerpts": [
    {
      "excerpt": "at least 47 individuals have been killed during protests across Iran since December 28, 2025",
      "relevance": "Total casualty figure with clear methodology",
      "confidence": "HIGH"
    },
    {
      "excerpt": "HRANA has verified the identities of 31 of these individuals through family members and eyewitness accounts",
      "relevance": "Distinguishes verified vs unverified casualties",
      "confidence": "HIGH"
    }
  ]
}
```

**Extracted candidate_claims:**

```json
{
  "claim_id": "CLM_20260110_0101",
  "claim_class": "HARD_FACT",
  "path": "current_state.casualties.protesters.killed.mid",
  "value": 47,
  "value_type": "integer",
  "as_of_utc": "2026-01-10T12:00:00Z",
  "source_doc_refs": ["HRANA_20260110_1200_f8e2b4a7"],
  "source_grade": "B3",
  "confidence": "MEDIUM",
  "triangulated": false,
  "notes": "HRANA verified 31, additional 16 unverified. Total 47 represents cumulative deaths since Day 1. Likely undercount due to information restrictions.",
  "conflicts_with": ["CLM_20260110_0087"],
  "supersedes": "CLM_20260109_0156"
}
```

```json
{
  "claim_id": "CLM_20260110_0102",
  "claim_class": "HARD_FACT",
  "path": "current_state.casualties.children.killed",
  "value": 3,
  "value_type": "integer",
  "as_of_utc": "2026-01-10T12:00:00Z",
  "source_doc_refs": ["HRANA_20260110_1200_f8e2b4a7"],
  "source_grade": "B3",
  "confidence": "MEDIUM",
  "triangulated": false,
  "notes": "Children defined as under 18. Subset of 47 total casualties.",
  "conflicts_with": null,
  "supersedes": null
}
```

```json
{
  "claim_id": "CLM_20260110_0103",
  "claim_class": "HARD_FACT",
  "path": "current_state.security_posture.rules_of_engagement_observed.live_fire",
  "value": true,
  "value_type": "boolean",
  "as_of_utc": "2026-01-10T12:00:00Z",
  "source_doc_refs": ["HRANA_20260110_1200_f8e2b4a7"],
  "source_grade": "B3",
  "confidence": "HIGH",
  "triangulated": true,
  "notes": "Live fire confirmed in Tehran, Tabriz, Kermanshah. Multiple sources corroborate.",
  "conflicts_with": null,
  "supersedes": null
}
```

```json
{
  "claim_id": "CLM_20260110_0104",
  "claim_class": "HARD_FACT",
  "path": "current_state.casualties.protesters.detained",
  "value": 320,
  "value_type": "integer",
  "as_of_utc": "2026-01-10T12:00:00Z",
  "source_doc_refs": ["HRANA_20260110_1200_f8e2b4a7"],
  "source_grade": "B3",
  "confidence": "LOW",
  "triangulated": false,
  "notes": "Based on family contacts, likely significant undercount. Regime rarely discloses detention figures.",
  "conflicts_with": null,
  "supersedes": null
}
```

---

## FINAL INSTRUCTIONS

1. **Execute collection workflow** (Phases 1-4 above)
2. **Generate bundle deliverables** (evidence_docs.jsonl, candidate_claims.jsonl, source_index.json, metadata.json)
3. **Run validation checklist** (Section 9)
4. **Submit complete bundle** as a downloadable package

**Success criteria:**
- Bundle passes all validation checks
- At least 3 source buckets covered
- At least 30 high-quality candidate_claims
- Conflicting data preserved (not reconciled)
- Known gaps explicitly documented

**Remember:** Your job is **collection and citation**, not analysis. Preserve ambiguity, document conflicts, admit unknowns. The compilation and analysis stages (handled by downstream agents) will reconcile conflicts and generate assessments. Your role is to provide the raw, well-cited evidence they need.

---

## SECTION 11: CRITICAL EVIDENCE QUALITY GATE

**Before finalizing your evidence bundle**, apply this mandatory quality gate to flag weak claims.

### Source Grade Threshold Rules

For each claim in your `candidate_claims.jsonl`, check the source grades:

| Best Source Grade | Claim Class | Action Required |
|------------------|-------------|-----------------|
| A1, A2, B1 | HARD_FACT | No flag needed |
| B2, B3 | HARD_FACT | Add triangulation note if single-source |
| C1, C2, C3 | HARD_FACT | **FLAG as LOW_CONFIDENCE** |
| D1-D4 | HARD_FACT | **FLAG as LOW_CONFIDENCE + suggest verification** |
| C or D | SOFT_FACT | Add note about evidence quality |
| C or D | ASSESSMENT | Acceptable with explicit caveats |

### Implementation

When flagging a claim, add these fields:

```json
{
  "claim_id": "CLM_20260110_0042",
  "path": "current_state.casualties.protesters.killed.mid",
  "value": 85,
  "source_grade": "C3",
  "confidence": "LOW",
  "confidence_flag": "LOW_SOURCE_QUALITY",
  "quality_gate_notes": "Best available source is grade C3. Claim requires verification from higher-grade source before use in critical assessments.",
  "suggested_followup": "Query HRANA or Iran Human Rights for corroboration; check Reuters/AP for independent casualty counts"
}
```

### Quality Gate Checklist

Before bundle submission, verify:

- [ ] Every HARD_FACT claim with best source C or D is flagged as `"confidence_flag": "LOW_SOURCE_QUALITY"`
- [ ] Every flagged claim has a `suggested_followup` field with specific verification guidance
- [ ] Claims relying solely on regime sources (grade 4 bias) are flagged with `"confidence_flag": "REGIME_SOURCE_ONLY"`
- [ ] Claims relying solely on opposition sources (grade 3 bias) without corroboration are flagged with `"confidence_flag": "OPPOSITION_SOURCE_ONLY"`
- [ ] Bundle metadata includes count of flagged claims in `summary.low_confidence_claims`

### Metadata Update

Add to your `metadata.json`:

```json
{
  "summary": {
    "total_candidate_claims": 47,
    "low_confidence_claims": 8,
    "regime_source_only_claims": 3,
    "opposition_source_only_claims": 5,
    "fully_triangulated_claims": 12
  },
  "quality_gate_status": "PASSED|WARNING|FAILED",
  "quality_gate_notes": "8 claims flagged for low source quality; suggest follow-up collection targeting these gaps"
}
```

**Warning Status:** If >30% of HARD_FACT claims are flagged, bundle receives WARNING status
**Failed Status:** If >50% of HARD_FACT claims are flagged, bundle receives FAILED status and should not proceed to compilation without additional collection

---

Good hunting. 🔍
