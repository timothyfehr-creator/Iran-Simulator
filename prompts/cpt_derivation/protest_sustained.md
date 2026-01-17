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

## CPT: P(Protest_Sustained | Protest_Escalation, Regime_Response, Internet_Status)

### Node Definitions
- **Protest_Sustained**: {NO, YES} (2 states)
- **Protest_Escalation**: {NO, YES} (2 states)
- **Regime_Response**: {STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED} (4 states)
- **Internet_Status**: {ON, THROTTLED, OFF} (3 states)

Total CPT size: 2 × 2 × 4 × 3 = 48 parameters (24 columns × 2 rows)

### Source Priors
```json
{
  "protests_sustain_30d": {
    "probability": {
        "point": 0.45,
        "low": 0.3,
        "high": 0.6,
        "dist": "beta_pert",
        "window_days": 30,
        "mode": 0.45,
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
},
  "protests_collapse_given_crackdown_30d": {
    "probability": {
        "point": 0.55,
        "low": 0.35,
        "high": 0.75,
        "window_days": 30,
        "dist": "beta_pert",
        "mode": 0.55,
        "time_basis": "window",
        "anchor": "crackdown_start",
        "start_offset_days": 0
    },
    "reasoning": {
        "base_rate_anchor": "PLACEHOLDER - protest survival vs repression outcomes (e.g., Iran 2019, 2022; Belarus 2020)",
        "evidence_for_higher": [],
        "evidence_for_lower": [],
        "analogies_considered": [],
        "confidence_in_estimate": "LOW"
    }
},
  "protests_collapse_given_concessions_30d": {
    "probability": {
        "point": 0.65,
        "low": 0.45,
        "high": 0.82,
        "dist": "beta_pert",
        "window_days": 30,
        "mode": 0.65,
        "time_basis": "window",
        "anchor": "concessions_start",
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
}
```

### Internet Blackout Effects
Internet blackouts fundamentally change protest coordination:
- **ON**: Full coordination capability
- **THROTTLED**: Reduced coordination (~70% effectiveness)
- **OFF**: Severely impaired coordination (~30% effectiveness)

### Rules
1. No Escalation → very low sustained probability (~10%)
2. CRACKDOWN → reduces sustained by collapse_given_crackdown rate
3. CONCESSIONS → reduces sustained by collapse_given_concessions rate
4. SUPPRESSED → very low sustained (~5%)
5. Internet OFF → multiply sustained probability by 0.3

### Constraints
1. Each column must sum to 1.0
2. P(Sustained=YES) should be <0.15 when Escalation=NO
3. Internet blackout should reduce sustained probability significantly
