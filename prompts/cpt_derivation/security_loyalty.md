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

## CPT: P(Security_Loyalty | Economic_Stress, Protest_State, Regime_Response)

### Node Definitions
- **Security_Loyalty**: {LOYAL, WAVERING, DEFECTED} (3 states)
- **Economic_Stress**: {STABLE, PRESSURED, CRITICAL} (3 states)
- **Protest_State**: {DECLINING, STABLE, ESCALATING, ORGANIZED, COLLAPSED} (5 states)
- **Regime_Response**: {STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED} (4 states)

Total CPT size: 3 × 3 × 5 × 4 = 180 parameters (60 independent columns × 3 rows)

### Source Priors
```json
{
  "probability": {
    "point": 0.08,
    "low": 0.03,
    "high": 0.15,
    "dist": "beta_pert",
    "window_days": 60,
    "mode": 0.08,
    "time_basis": "window",
    "anchor": "t0",
    "start_offset_days": 30
  },
  "reasoning": {
    "base_rate_anchor": "PLACEHOLDER - No defections in 2009, 2019, 2022",
    "evidence_for_higher": [],
    "evidence_for_lower": [],
    "analogies_considered": [],
    "confidence_in_estimate": "LOW"
  }
}
```

### Economic Modifiers
```json
{
  "_comment": "Probability multipliers applied when economic stress is elevated",
  "critical_protest_escalation_multiplier": 1.2,
  "critical_elite_fracture_multiplier": 1.3,
  "critical_security_defection_multiplier": 1.15,
  "critical_regime_concession_multiplier": 1.1,
  "pressured_protest_escalation_multiplier": 1.1,
  "pressured_elite_fracture_multiplier": 1.15,
  "pressured_security_defection_multiplier": 1.08,
  "pressured_regime_concession_multiplier": 1.05
}
```

### Historical Anchor
- 0 defections in 5 major Iranian protests (1999, 2009, 2017-18, 2019, 2022)
- Current 8% estimate elevated due to unprecedented protest scale/diversity

### Modifier Rules
1. **Economic modifier**:
   - CRITICAL: multiply base by 1.15
   - PRESSURED: multiply base by 1.08
   - STABLE: no modifier

2. **Concession dampening**:
   - If Regime_Response == CONCESSIONS: multiply by 0.7

3. **Condition for defection**:
   - Only if Protest_State in {STABLE, ESCALATING, ORGANIZED}
   - If Protest_State == COLLAPSED or DECLINING: defection probability → 0

4. **Wavering**:
   - P(WAVERING) should be ~2-3× P(DEFECTED) in relevant conditions
   - P(LOYAL) is the complement

### Constraints
1. Each column must sum to 1.0
2. P(DEFECTED) must be 0 when Protest_State ∈ {COLLAPSED, DECLINING}
3. P(DEFECTED) maximum should not exceed ~0.12 (CRITICAL + no concessions)
