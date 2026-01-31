# Project Swarm: ABM Implementation Review

**For Gemini Review** | Generated: 2026-01-17

---

## Implementation Summary

The ABM has been implemented according to the approved plan. This document summarizes what was built for Gemini's review.

---

## 1. Agent Type System

### Distribution (Confirmed)
| Type | Percentage | Count (n=10,000) | Grievance Distribution |
|------|------------|------------------|------------------------|
| STUDENT | 15% | 1,500 | Beta(4, 2) → mean ~0.67 |
| MERCHANT | 20% | 2,000 | Beta(3, 3) → mean ~0.50 |
| CONSCRIPT | 10% | 1,000 | Beta(1, 4) → mean ~0.20 |
| HARDLINER | 5% | 500 | Fixed 0.0 |
| CIVILIAN | 50% | 5,000 | Beta(2, 3) → mean ~0.40 |

### Implementation
```python
# Agent type constants
STUDENT = 0
MERCHANT = 1
CONSCRIPT = 2
HARDLINER = 3
CIVILIAN = 4

# Initialization shuffles types for uniform network distribution
# (Gemini V2: "Dispersed wet blanket" abstraction)
self.rng.shuffle(types)
```

---

## 2. Gemini Rulings Implementation Status

| Ruling | Status | Implementation Details |
|--------|--------|------------------------|
| **Exhaustion FIRST** | ✅ Implemented | Applied in Phase 1 of `step()`, before activation decision |
| **Suppression to THRESHOLD** | ✅ Implemented | `effective_threshold[has_hardliner_neighbor] += 0.1` |
| **Strong Regime Bias** | ✅ Implemented | 72% regime survival in test runs |
| **Uniform Hardliner Distribution** | ✅ Implemented | Types shuffled after assignment |
| **Defection Contagion >0.4** | ✅ Implemented | `defection_contagion_threshold: float = 0.4` |
| **`get_snapshot()` Debug** | ✅ Implemented | Returns full arrays + histograms + per-type breakdown |

---

## 3. Step Function Logic Order

The `step()` function follows this exact order:

```
PHASE 1: EXHAUSTION (Gemini V2: Apply BEFORE activation)
    - If days_active > 7: grievance -= 0.05
    - Clamp grievance to [0, 1]

PHASE 2: UPDATE GRIEVANCE (Type-specific)
    - Merchant: Add graduated economic impact (0 at 1M Rial, +0.3 at 2M)
    - Merchant: If concessions, grievance *= 0.5
    - Hardliner: Lock grievance at 0.0

PHASE 3: COMPUTE EFFECTIVE THRESHOLDS
    - Start from base_threshold
    - Student: If ESCALATING, threshold -= 0.2
    - Hardliner suppression: If has hardliner neighbor, threshold += 0.1

PHASE 4: COMPUTE NEIGHBOR INFLUENCE
    - Sparse matrix multiply: neighbors @ active
    - Internet blackout: influence *= 0.3

PHASE 5: ACTIVATION DECISION
    - activation_signal = grievance + 0.4 * neighbor_active_pct
    - active = activation_signal > effective_threshold
    - Security forces (CONSCRIPT | HARDLINER): Force active = False

PHASE 6: CONSCRIPT DEFECTION
    - Compute neighbor defection rate
    - Compute fear bonus (has_hardliner_neighbor → +0.2)
    - Condition 1: overwhelmed (>50% neighbors active) AND moral_injury (crackdown > 0.6)
    - Condition 2: neighbor_defection_pct > 0.4 (Gemini V2: raised from 0.3)
    - Stochastic: 30% daily probability, reduced by fear_bonus

PHASE 7: HARDLINER DEFECTION
    - If regime_state == "COLLAPSE" OR conscript_defection_rate > 50%: defect

PHASE 8: UPDATE COUNTERS
    - days_active[active] += 1
    - days_active[~active] = 0

PHASE 9: COMPUTE METRICS
    - Return dict with all metrics for simulation.py
```

---

## 4. Key Parameters (ABMConfig)

```python
@dataclass
class ABMConfig:
    n_agents: int = 10_000
    seed: Optional[int] = None

    # Network
    network_type: str = "small_world"
    avg_neighbors: int = 8
    rewire_prob: float = 0.1

    # Thresholds
    threshold_low: float = 0.3
    threshold_high: float = 0.8
    neighbor_influence: float = 0.4

    # Student
    student_threshold_reduction: float = 0.2

    # Merchant
    merchant_economic_scale: float = 0.3      # Max at 2M Rial
    merchant_concession_reduction: float = 0.5

    # Conscript Defection
    defection_base_prob: float = 0.3
    defection_overwhelmed_threshold: float = 0.5
    defection_moral_injury_threshold: float = 0.6
    defection_contagion_threshold: float = 0.4  # Gemini V2: raised from 0.3

    # Hardliner Effects
    hardliner_fear_bonus: float = 0.2
    hardliner_suppression_effect: float = 0.1
    hardliner_mass_defection_threshold: float = 0.5

    # Exhaustion
    exhaustion_threshold_days: int = 7
    exhaustion_grievance_decay: float = 0.05

    # Macro threshold
    macro_defection_threshold: float = 0.30
```

---

## 5. Output Interface

The `step()` function returns:

```python
{
    # Primary metrics for simulation.py integration
    "total_protesting": float,      # Mean of active civilians
    "defection_rate": float,        # Mean of defected conscripts
    "coordination_score": float,    # Clustering coefficient

    # Type-specific breakdown
    "student_participation": float,
    "merchant_participation": float,
    "civilian_participation": float,
    "hardliner_defection": float,

    # Extended metrics
    "avg_grievance": float,
    "avg_threshold": float,
    "n_active": int,
    "n_defected": int,
    "new_activations": int,
    "deactivations": int,
    "regional_breakdown": Dict[int, float],
}
```

---

## 6. Simulation.py Integration

### Context Passed to ABM
```python
abm_context = {
    "protest_state": state.protest_state.value.upper(),
    "regime_state": state.regime_state.value.upper(),
    "rial_rate": self._economic_data.get("rial_rate", 1_000_000),
    "crackdown_intensity": 0.8 if state.regime_state == RegimeState.CRACKDOWN else 0.2,
    "concessions_offered": state.regime_state == RegimeState.CONCESSIONS,
    "internet_blackout": state.regime_state == RegimeState.CRACKDOWN,
}
```

### ABM Output → Macro State Mapping
```python
# Protest escalation
if abm_result["total_protesting"] > 0.10:
    state.protest_state = ProtestState.ESCALATING

# Protest collapse
elif abm_result["total_protesting"] < 0.02:
    state.protest_state = ProtestState.COLLAPSED

# Security force defection (30% threshold)
if abm_result["defection_rate"] > 0.30:
    state.defection_occurred = True
    state.regime_state = RegimeState.DEFECTION
```

---

## 7. Debug Snapshot (`get_snapshot()`)

```python
def get_snapshot(self) -> Dict[str, Any]:
    return {
        # Full arrays
        "grievance": self.grievance.copy(),
        "threshold": self.base_threshold.copy(),
        "active": self.active.copy(),
        "defected": self.defected.copy(),
        "days_active": self.days_active.copy(),
        "agent_type": self.agent_type.copy(),

        # Histogram
        "grievance_histogram": {
            "bins": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
            "counts": [...]
        },

        # Per-type breakdown
        "by_type": {
            "student": {"count": int, "active_pct": float, "avg_grievance": float},
            "merchant": {"count": int, "active_pct": float, "avg_grievance": float},
            "civilian": {"count": int, "active_pct": float, "avg_grievance": float},
            "conscript": {"count": int, "defected_pct": float},
            "hardliner": {"count": int, "defected_pct": float},
        }
    }
```

---

## 8. Initial Test Results

### Agent Type Distribution
```
student     :  1500 (expected  1500) [OK]
merchant    :  2000 (expected  2000) [OK]
conscript   :  1000 (expected  1000) [OK]
hardliner   :   500 (expected   500) [OK]
civilian    :  5000 (expected  5000) [OK]
```

### Initial Grievance Means
```
student     : mean=0.670  (expected ~0.67)
merchant    : mean=0.500  (expected ~0.50)
conscript   : mean=0.197  (expected ~0.20)
hardliner   : mean=0.000  (expected 0.00)
civilian    : mean=0.399  (expected ~0.40)
```

### Performance Benchmark (10K agents, 90 days, 50 runs)
```
Mean run time: 0.0667s (+/-0.0014s)
Agent-steps/sec: 13,484,937
Total time for 50 runs: 3.34s
```

### Outcome Distribution (100 ABM runs)
```
REGIME_SURVIVES_STATUS_QUO:     72%
ETHNIC_FRAGMENTATION:            9%
REGIME_SURVIVES_WITH_CONCESSIONS: 9%
REGIME_COLLAPSE_CHAOTIC:         8%
MANAGED_TRANSITION:              2%

Security Force Defection Rate:  17%
```

---

## 9. Questions for Gemini Review

1. **Exhaustion Timing**: Exhaustion is applied at the START of each step. Is this the intended interpretation of "before activation"?

2. **Hardliner Suppression Scope**: Currently suppression affects ALL agent types with a hardliner neighbor. Should it only affect civilians/students/merchants?

3. **Economic Impact Accumulation**: Merchant economic grievance is ADDED each step (not set). This means grievance accumulates over time. Is this intended, or should it be a direct mapping?

4. **Defection Probability**: The 30% base probability is reduced by fear_bonus (0.2 near hardliners). This means conscripts near hardliners have only 10% defection probability. Is this reduction sufficient?

5. **Contagion vs Overwhelm**: Both conditions trigger defection eligibility. Should there be different probabilities for each path?

---

## 10. Files Modified

| File | Lines Changed | Description |
|------|---------------|-------------|
| `src/abm_engine.py` | ~810 | Complete rewrite with agent types |
| `src/simulation.py` | ~50 | ABM integration + `--abm` flag |

---

## 11. Next Steps for Validation

1. **Pattern-Oriented Validation**
   - S-curve protest dynamics
   - Sequential activation (students → merchants → civilians)
   - Exhaustion waves

2. **Sensitivity Analysis**
   - Which parameters most affect outcome distribution?
   - Is the 30% defection threshold calibrated correctly?

3. **Comparison with State Machine**
   - Run same scenarios with and without ABM
   - Compare outcome distributions

---

**END OF IMPLEMENTATION REVIEW**
