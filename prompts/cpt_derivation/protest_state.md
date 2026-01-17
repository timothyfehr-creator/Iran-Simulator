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

## CPT: P(Protest_State | Protest_Escalation, Protest_Sustained, Regime_Response)

### Node Definitions
- **Protest_State**: {DECLINING, STABLE, ESCALATING, ORGANIZED, COLLAPSED} (5 states)
- **Protest_Escalation**: {NO, YES} (2 states)
- **Protest_Sustained**: {NO, YES} (2 states)
- **Regime_Response**: {STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED} (4 states)

Total CPT size: 5 × 2 × 2 × 4 = 80 parameters (16 columns × 5 rows)

### Source Priors
```json
{
  "protests_escalate_14d": {
    "probability": {
        "point": 0.35,
        "low": 0.2,
        "high": 0.5,
        "dist": "beta_pert",
        "window_days": 14,
        "mode": 0.35,
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

### Logical Rules
1. **Regime_Response = SUPPRESSED** → P(COLLAPSED) high (~70%)
2. **Escalation = NO, Sustained = NO** → DECLINING most likely
3. **Escalation = YES, Sustained = YES, Response = STATUS_QUO** → ORGANIZED possible
4. **Crackdown** → Can trigger COLLAPSED or ESCALATING (backfire)
5. **Concessions** → Tends toward DECLINING or STABLE

### Constraints
1. Each column must sum to 1.0
2. ORGANIZED requires both Escalation and Sustained = YES
3. COLLAPSED requires either SUPPRESSED or CRACKDOWN (with some probability)
