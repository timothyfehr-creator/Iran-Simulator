# CPT Derivation Request

You are a Geopolitical Actuary. Your task is to fill a Conditional Probability Table (CPT)
for a Bayesian Network modeling the Iran crisis simulation.

## Window-to-Marginal Conversion Formula

For converting window probabilities to BN marginals:
```python
def window_to_marginal(p_window, window_days, total_days=90):
    expected_onset = window_days / 2
    duration_if_occurs = total_days - expected_onset
    return p_window * (duration_if_occurs / total_days)
```

## Output Format Requirements

Return your CPT as a JSON object with this structure:
```json
{
  "cpt_values": {
    "columns": [
      {"Parent1": "State1", "Parent2": "State1"},
      ...
    ],
    "rows": ["ChildState1", "ChildState2", ...],
    "matrix": [[...], [...], ...]
  },
  "derivation_steps": [
    "Step 1: ...",
    "Step 2: ...",
    ...
  ],
  "validation": {
    "column_sums": "all 1.0",
    "probability_range": [min, max]
  }
}
```

## Constraints
1. Each column must sum to exactly 1.0
2. All probabilities must be in [0, 1]
3. Provide reasoning for each probability assignment

## CPT: P(Elite_Cohesion | Economic_Stress, Security_Loyalty)

### Node Definitions
- **Elite_Cohesion**: {COHESIVE, FRACTURED, COLLAPSED} (3 states)
- **Economic_Stress**: {STABLE, PRESSURED, CRITICAL} (3 states)
- **Security_Loyalty**: {LOYAL, WAVERING, DEFECTED} (3 states)

Total CPT size: 3 × 3 × 3 = 27 parameters (9 columns × 3 rows)

### Source Priors
```json
{
  "probability": {
    "point": 0.3,
    "low": 0.15,
    "high": 0.45,
    "dist": "beta_pert",
    "window_days": 90,
    "mode": 0.3,
    "time_basis": "window",
    "anchor": "t0",
    "start_offset_days": 0
  },
  "reasoning": {
    "base_rate_anchor": "PLACEHOLDER",
    "evidence_for_higher": [],
    "evidence_for_lower": [],
    "analogies_considered": [],
    "confidence_in_estimate": "LOW"
  }
}
```

### CRITICAL: Tipping Point Model

Elite fractures are rare but catastrophic. This CPT should NOT be linear.

**The correct model:**
- Elite Cohesion remains HIGH even under stress
- UNTIL a "Tipping Point" of Defection + Critical Economy is reached
- THEN it collapses instantly to COLLAPSED

**Example distribution:**
- (STABLE, LOYAL): [0.90, 0.08, 0.02]
- (CRITICAL, WAVERING): [0.40, 0.35, 0.25]
- (CRITICAL, DEFECTED): [0.05, 0.25, 0.70]  ← Tipping point crossed

### Constraints
1. Each column must sum to 1.0
2. P(COLLAPSED) should be <5% unless both stress and loyalty problems exist
3. Security defection is the primary trigger for elite collapse
