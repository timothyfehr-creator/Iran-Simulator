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

## CPT: P(Regime_Response | Protest_State, Regional_Instability)

### Node Definitions
- **Regime_Response**: {STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED} (4 states)
- **Protest_State**: {DECLINING, STABLE, ESCALATING, ORGANIZED, COLLAPSED} (5 states)
- **Regional_Instability**: {NONE, MODERATE, SEVERE} (3 states)

Total CPT size: 4 × 5 × 3 = 60 parameters (15 columns × 4 rows)

### Source Priors
```json
{
  "mass_casualty_crackdown_given_escalation": {
    "probability": {
        "point": 0.4,
        "low": 0.25,
        "high": 0.6,
        "dist": "beta_pert",
        "window_days": 30,
        "mode": 0.4,
        "time_basis": "window",
        "anchor": "escalation_start",
        "start_offset_days": 0
    },
    "reasoning": {
        "base_rate_anchor": "PLACEHOLDER - 2019 November crackdown killed 1,500",
        "evidence_for_higher": [],
        "evidence_for_lower": [],
        "analogies_considered": [],
        "confidence_in_estimate": "LOW"
    }
},
  "meaningful_concessions_given_protests_30d": {
    "probability": {
        "point": 0.15,
        "low": 0.07,
        "high": 0.3,
        "window_days": 30,
        "dist": "beta_pert",
        "mode": 0.15,
        "time_basis": "window",
        "anchor": "t0",
        "start_offset_days": 30
    },
    "reasoning": {
        "base_rate_anchor": "PLACEHOLDER - Iranian concession patterns under sustained unrest",
        "evidence_for_higher": [],
        "evidence_for_lower": [],
        "analogies_considered": [],
        "confidence_in_estimate": "LOW"
    }
}
}
```

### Logical Rules
1. **Protest_State = COLLAPSED** → SUPPRESSED most likely (~90%)
2. **Protest_State = DECLINING** → STATUS_QUO most likely
3. **Protest_State in {ESCALATING, ORGANIZED}** → CRACKDOWN more likely
4. **Regional_Instability = SEVERE** → increases CRACKDOWN probability (20% boost)
5. **CONCESSIONS** are rare but possible when protests are stable/organized

### Constraints
1. Each column must sum to 1.0
2. SUPPRESSED requires prior protest collapse
3. CRACKDOWN probability ≈ 40% for escalating protests
4. CONCESSIONS probability ≈ 15% for sustained protests
