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

## CPT: P(Regime_Outcome | Security_Loyalty, Succession_Type, Fragmentation_Outcome, Elite_Cohesion)

### Node Definitions
- **Regime_Outcome**: {STATUS_QUO, CONCESSIONS, TRANSITION, COLLAPSE, FRAGMENTATION} (5 states)
- **Security_Loyalty**: {LOYAL, WAVERING, DEFECTED} (3 states)
- **Succession_Type**: {ORDERLY, CHAOTIC} (2 states)
- **Fragmentation_Outcome**: {NO, YES} (2 states)
- **Elite_Cohesion**: {COHESIVE, FRACTURED, COLLAPSED} (3 states)

Total CPT size: 5 × 3 × 2 × 2 × 3 = 180 parameters (36 columns × 5 rows)

### Source Priors (Regime Outcomes)
```json
{
  "time_horizon_days": 90,
  "must_sum_to_one": true,
  "REGIME_SURVIVES_STATUS_QUO": {
    "probability": {
      "point": 0.55,
      "low": 0.4,
      "high": 0.7,
      "dist": "beta_pert",
      "window_days": 90,
      "mode": 0.55
    },
    "reasoning": {
      "base_rate_anchor": "PLACEHOLDER - Historical Iranian protest suppression rate",
      "evidence_for_higher": [],
      "evidence_for_lower": [],
      "analogies_considered": [],
      "confidence_in_estimate": "LOW"
    }
  },
  "REGIME_SURVIVES_WITH_CONCESSIONS": {
    "probability": {
      "point": 0.15,
      "low": 0.08,
      "high": 0.25,
      "dist": "beta_pert",
      "window_days": 90,
      "mode": 0.15
    },
    "reasoning": {
      "base_rate_anchor": "PLACEHOLDER",
      "evidence_for_higher": [],
      "evidence_for_lower": [],
      "analogies_considered": [],
      "confidence_in_estimate": "LOW"
    }
  },
  "MANAGED_TRANSITION": {
    "probability": {
      "point": 0.1,
      "low": 0.05,
      "high": 0.18,
      "dist": "beta_pert",
      "window_days": 90,
      "mode": 0.1
    },
    "reasoning": {
      "base_rate_anchor": "PLACEHOLDER - Khamenei age/health actuarial estimate",
      "evidence_for_higher": [],
      "evidence_for_lower": [],
      "analogies_considered": [],
      "confidence_in_estimate": "LOW"
    }
  },
  "REGIME_COLLAPSE_CHAOTIC": {
    "probability": {
      "point": 0.12,
      "low": 0.05,
      "high": 0.22,
      "dist": "beta_pert",
      "window_days": 90,
      "mode": 0.12
    },
    "reasoning": {
      "base_rate_anchor": "PLACEHOLDER - Authoritarian collapse base rate",
      "evidence_for_higher": [],
      "evidence_for_lower": [],
      "analogies_considered": [],
      "confidence_in_estimate": "LOW"
    }
  },
  "ETHNIC_FRAGMENTATION": {
    "probability": {
      "point": 0.08,
      "low": 0.03,
      "high": 0.15,
      "dist": "beta_pert",
      "window_days": 90,
      "mode": 0.08
    },
    "reasoning": {
      "base_rate_anchor": "PLACEHOLDER",
      "evidence_for_higher": [],
      "evidence_for_lower": [],
      "analogies_considered": [],
      "confidence_in_estimate": "LOW"
    }
  },
  "sum_check": 1.0,
  "sampling": {
    "method": "dirichlet",
    "concentration": 30,
    "alpha": null,
    "notes": "If alpha is null, alpha_i is derived from point estimates and concentration."
  },
  "role": "diagnostic_only"
}
```

### Key Conditional Probabilities
```json
{
  "regime_collapse_given_defection": {
    "probability": {
        "point": 0.65,
        "low": 0.45,
        "high": 0.8,
        "dist": "beta_pert",
        "window_days": 14,
        "mode": 0.65,
        "time_basis": "window",
        "anchor": "defection_day",
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

### Causal Priority Rules
1. **Fragmentation_Outcome = YES** → FRAGMENTATION outcome most likely (~70%)
2. **Security_Loyalty = DEFECTED** → COLLAPSE highly likely (65% per prior)
3. **Elite_Cohesion = COLLAPSED** → COLLAPSE or TRANSITION
4. **Succession_Type = CHAOTIC** → TRANSITION more likely than STATUS_QUO
5. **All stable** → STATUS_QUO most likely, with some CONCESSIONS

### Constraints
1. Each column must sum to 1.0
2. When Fragmentation_Outcome = YES: P(FRAGMENTATION) > 0.5
3. When Security_Loyalty = DEFECTED: P(COLLAPSE) ≈ 0.65
4. Base case (all favorable): P(STATUS_QUO) > 0.5
