# Bayesian Network Phase 2: Production Readiness

**Status:** APPROVED FOR IMPLEMENTATION
**Reviewer:** Gemini (Chief Architect)
**Date:** January 17, 2026

---

## Executive Summary

The BN prototype has been **APPROVED FOR MERGE** with a KL Divergence of 0.091 against 10,000-run Monte Carlo. This phase implements three strategic improvements to move from "Prototype" to "Production."

---

## Improvement 1: The "Surprise" Metric

### Problem
An analyst sees "Collapse: 5%" but doesn't know if this is "normal" or "shocking" compared to their priors.

### Solution
Add `surprise_score` to inference output using KL Divergence between posterior and prior.

```python
def compute_surprise(posterior: dict, prior: dict) -> float:
    """Compute KL divergence as surprise metric.

    High surprise = model found hidden correlation analyst missed.
    """
    surprise = 0.0
    for state in posterior:
        p = posterior[state]
        q = prior.get(state, 0.01)
        if p > 0:
            surprise += p * math.log2(p / q)
    return surprise
```

### Output Format
```json
{
  "posterior": {"STATUS_QUO": 0.45, "COLLAPSE": 0.30, ...},
  "surprise_score": 0.42,
  "surprise_flag": true,  // if surprise > 0.3
  "surprise_drivers": ["Security_Loyalty", "Elite_Cohesion"]
}
```

### Dashboard Integration
- Display "⚠️ Model Disagreement" badge when `surprise_flag = true`
- Highlight which variables drove the surprise

---

## Improvement 2: Automated CPT Refinement Pipeline

### Problem
7 of 10 complex CPTs still use placeholder values.

### Solution
Create `scripts/refine_cpts.py` that:
1. Iterates through placeholder CPTs
2. Generates structured prompts with constraints
3. Produces calibrated JSON files
4. Validates KL divergence didn't spike

### Target CPTs
| CPT | Current Status | Priority |
|-----|----------------|----------|
| Protest_Escalation | Placeholder | High |
| Protest_Sustained | Placeholder | High |
| Protest_State | Placeholder | Medium |
| Regime_Response | Placeholder | Medium |
| Ethnic_Uprising | Placeholder | Medium |
| Internet_Status | Placeholder | Low |
| Regional_Instability | Placeholder | Low |

### Validation Gate
After each CPT refinement:
- Run `--validate` to ensure model check passes
- Run `--compare-mc` to ensure KL < 0.15
- If validation fails, revert to previous CPT

---

## Improvement 3: Interactive "What-If" Explorer

### Problem
Static PNG visualization doesn't build trust.

### Solution
Add interactive DAG to Streamlit dashboard using `pyvis` or `streamlit-agraph`.

### Features
1. **Click to Intervene**: Click node → set state → see downstream effects
2. **Edge Highlighting**: Show which edges transmit shocks
3. **Probability Overlay**: Color nodes by current probability
4. **Surprise Indicators**: Flash nodes with high surprise scores

### Implementation
```python
# In dashboard.py
def render_interactive_dag(engine: CausalEngine, evidence: dict):
    """Render interactive DAG with pyvis."""
    from pyvis.network import Network

    net = Network(height="600px", directed=True)

    # Add nodes with probability colors
    for node, states in ALL_NODES.items():
        prob = engine.infer_single(node, evidence)
        color = probability_to_color(prob)
        net.add_node(node, color=color, title=format_probs(prob))

    # Add edges
    for src, dst in EDGES:
        net.add_edge(src, dst)

    return net.generate_html()
```

---

## Implementation Sequence

### Step 1: Surprise Metric (30 min) - COMPLETED
- [x] Add `compute_surprise()` to CausalEngine
- [x] Add `surprise_score` to `infer()` output
- [x] Add `--surprise` flag to CLI
- [x] Add `infer_with_surprise()` method

### Step 2: CPT Refinement Pipeline (45 min) - COMPLETED
- [x] Create `scripts/refine_cpts.py`
- [x] Generate calibrated values for 7 placeholder CPTs
- [x] Validate each CPT maintains KL < 0.15 (achieved 0.093)
- [x] Update responses/ directory (10 CPT files total)

### Step 3: Interactive Explorer (30 min) - COMPLETED
- [x] Add pyvis to requirements.txt
- [x] Create `render_causal_explorer()` in dashboard.py
- [x] Add "Causal" mode to dashboard
- [x] Wire up evidence/intervention functionality
- [x] Display surprise metrics in dashboard

### Step 4: Final Validation (15 min) - IN PROGRESS
- [x] Run full test suite (40/40 pass)
- [x] Run E2E validation (KL=0.093)
- [x] Update documentation
- [ ] Prepare merge

---

## Success Criteria

| Metric | Target | Achieved |
|--------|--------|----------|
| All placeholder CPTs refined | 7/7 | 7/7 ✅ |
| KL Divergence (calibrated) | < 0.10 | 0.093 ✅ |
| Surprise metric implemented | Yes | Yes ✅ |
| Interactive explorer working | Yes | Yes ✅ |
| All tests pass | 40/40 | 40/40 ✅ |

---

## Post-Merge Actions

1. **Deploy**: Push CausalEngine to production
2. **Monitor**: Track surprise scores in daily runs
3. **Iterate**: Refine CPTs based on analyst feedback

---

*Gemini Sign-Off: "Project Swarm is now fully operational."*
