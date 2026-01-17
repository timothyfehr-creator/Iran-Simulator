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

## CPT: P(Ethnic_Uprising | Protest_Sustained, Economic_Stress)

### Node Definitions
- **Ethnic_Uprising**: {NO, YES} (2 states)
- **Protest_Sustained**: {NO, YES} (2 states)
- **Economic_Stress**: {STABLE, PRESSURED, CRITICAL} (3 states)

Total CPT size: 2 × 2 × 3 = 12 parameters (6 columns × 2 rows)

### Source Priors
```json
{
  "probability": {
    "point": 0.25,
    "low": 0.12,
    "high": 0.4,
    "dist": "beta_pert",
    "window_days": 60,
    "mode": 0.25,
    "time_basis": "window",
    "anchor": "t0",
    "start_offset_days": 30
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

### Window-to-Marginal Conversion
Base probability: P(ethnic coordination in 60-day window starting day 30) = 25%
Marginal approximation: 25% × 0.5 ≈ 12.5%

### Rules
1. Without sustained protests, ethnic uprising is unlikely (~2%)
2. With sustained protests, base probability ~12.5%
3. CRITICAL economic stress increases by 30%
4. PRESSURED economic stress increases by 15%

### Constraints
1. Each column must sum to 1.0
2. P(YES) should be <5% when Sustained=NO
3. P(YES) should not exceed 50% in any condition
