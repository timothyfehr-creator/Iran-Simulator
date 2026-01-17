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

## CPT: P(Internet_Status | Regime_Response)

### Node Definitions
- **Internet_Status**: {ON, THROTTLED, OFF} (3 states)
- **Regime_Response**: {STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED} (4 states)

Total CPT size: 3 × 4 = 12 parameters (4 columns × 3 rows)

### Historical Context
- Iran has repeatedly used internet blackouts during protests (2019 November, 2022)
- Throttling is common during unrest
- Full blackouts are reserved for severe crackdowns

### Rules
1. **STATUS_QUO**: Internet mostly ON (~90%)
2. **CRACKDOWN**: High probability of throttling (~40%) or blackout (~30%)
3. **CONCESSIONS**: Internet mostly ON (~80%), some throttling
4. **SUPPRESSED**: High probability of blackout (~60%), throttling (~30%)

### Constraints
1. Each column must sum to 1.0
2. P(OFF) should be highest for CRACKDOWN and SUPPRESSED
3. P(ON) should be highest for STATUS_QUO and CONCESSIONS
