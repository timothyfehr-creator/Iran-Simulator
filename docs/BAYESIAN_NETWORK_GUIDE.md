# Bayesian Network Integration Guide

## Overview

The Bayesian Network (BN) prototype provides causal reasoning capabilities for the Iran crisis simulation. Unlike the Monte Carlo (MC) simulation which samples trajectories over 90 days, the BN models equilibrium states and enables "what-if" queries impossible with pure sampling.

## Quick Start

```bash
# Activate virtual environment
source .venv/bin/activate

# Validate the model with calibrated CPTs
python scripts/prototype_causal_graph.py \
    --load-cpts prompts/cpt_derivation/responses/ \
    --validate

# Run inference with evidence
python scripts/prototype_causal_graph.py \
    --load-cpts prompts/cpt_derivation/responses/ \
    --infer \
    --evidence '{"Economic_Stress": "CRITICAL"}'

# Compare to Monte Carlo results
python scripts/prototype_causal_graph.py \
    --load-cpts prompts/cpt_derivation/responses/ \
    --compare-mc runs/RUN_20260117_daily/simulation_results_10k.json

# Sensitivity analysis
python scripts/prototype_causal_graph.py \
    --load-cpts prompts/cpt_derivation/responses/ \
    --sensitivity Regime_Outcome
```

## Architecture

### Hybrid Design

The BN complements rather than replaces the MC simulation:

| Aspect | Monte Carlo | Bayesian Network |
|--------|-------------|------------------|
| **Models** | 90-day trajectories | Equilibrium states |
| **Queries** | "What outcomes occur?" | "What if X happens?" |
| **Dynamics** | Window-based probabilities | Static CPTs |
| **Output** | Distribution of trajectories | Conditional probabilities |

### DAG Structure

The BN has 22 nodes connected by 30+ edges. Key node groups:

**Root Nodes (Observable/Exogenous):**
- `Rial_Rate`, `Inflation` - Economic indicators
- `Khamenei_Health` - Succession trigger
- `US_Policy_Disposition` - External policy

**Intermediate Nodes:**
- `Economic_Stress` - Derived from Rial/Inflation
- `Protest_Escalation`, `Protest_Sustained`, `Protest_State` - Protest dynamics
- `Regime_Response`, `Internet_Status` - Regime actions
- `Security_Loyalty`, `Elite_Cohesion` - Regime stability
- `Ethnic_Uprising`, `Fragmentation_Outcome` - Ethnic dynamics
- `Succession_Type` - Post-Khamenei path

**Terminal Node:**
- `Regime_Outcome` - Final regime status (STATUS_QUO, CONCESSIONS, TRANSITION, COLLAPSE, FRAGMENTATION)

### CPT Sources

CPTs come from three sources:

1. **Simple CPTs** - Directly derived from `analyst_priors.json`
   - Economic thresholds
   - Base probabilities for root nodes

2. **Placeholder CPTs** - Built-in defaults (less accurate)
   - Used when no calibrated CPT available

3. **Calibrated CPTs** - In `prompts/cpt_derivation/responses/`
   - Refined to match MC simulation results
   - Should be used for production queries

## Key Queries

### 1. Conditional Inference

Query outcome probabilities given observed evidence:

```python
from scripts.prototype_causal_graph import CausalEngine

engine = CausalEngine(
    "data/analyst_priors.json",
    cpt_dir="prompts/cpt_derivation/responses/"
)

# What happens if security forces defect?
result = engine.infer_single("Regime_Outcome", {"Security_Loyalty": "DEFECTED"})
# Result: ~57% COLLAPSE (matches regime_collapse_given_defection prior)
```

### 2. Sensitivity Analysis

Identify which factors most affect outcomes:

```python
sensitivity = engine.sensitivity("Regime_Outcome")
# Returns: {
#   "Elite_Cohesion": 0.34,      # Most influential
#   "Security_Loyalty": 0.09,
#   "Fragmentation_Outcome": 0.03,
#   "Succession_Type": 0.02
# }
```

### 3. What-If (Causal Intervention)

Query outcomes under hypothetical interventions:

```python
# What if US goes kinetic?
result = engine.what_if(
    {"US_Policy_Disposition": "KINETIC"},
    "Regime_Outcome"
)
```

### 4. Surprise Metric (Phase 2)

Detect when model predictions significantly diverge from analyst priors:

```python
# Run inference with surprise analysis
result = engine.infer_with_surprise("Regime_Outcome", {"Security_Loyalty": "DEFECTED"})

# Returns:
# {
#   "posterior": {"STATUS_QUO": 0.12, "COLLAPSE": 0.57, ...},
#   "surprise_score": 1.02,
#   "surprise_flag": True,  # Model disagrees with analyst priors
#   "surprise_drivers": ["COLLAPSE", "STATUS_QUO"]
# }
```

**Interpretation:**
- `surprise_score` > 0.3 triggers a warning flag
- High surprise = model found hidden correlations the analyst missed
- `surprise_drivers` shows which outcomes drove the divergence

CLI usage:
```bash
python scripts/prototype_causal_graph.py \
    --load-cpts prompts/cpt_derivation/responses/ \
    --infer --surprise \
    --evidence '{"Security_Loyalty": "DEFECTED"}'
```

## Validation Metrics

The BN is validated against MC simulation results:

| Metric | Threshold | Current |
|--------|-----------|---------|
| KL Divergence | < 0.10 | 0.09 ✓ |
| Max Difference | < 0.08 | 0.08 ✓ |
| Black Swan Check | Pass | Pass ✓ |

**Black Swan Preservation**: Any outcome with analyst prior > 1% must have BN probability > 0.5%.

## CPT File Format

Calibrated CPTs are stored as JSON in `prompts/cpt_derivation/responses/`:

```json
{
  "variable": "NodeName",
  "states": ["State1", "State2", ...],
  "parents": ["Parent1", "Parent2", ...],
  "parent_states": {
    "Parent1": ["S1", "S2", ...],
    "Parent2": ["S1", "S2", ...]
  },
  "values": [
    [row1_values],  // P(State1 | parent combinations)
    [row2_values],  // P(State2 | parent combinations)
    ...
  ],
  "derivation_notes": "Explanation of how values were derived"
}
```

Column ordering follows parent order with rightmost parent varying fastest.

## Cycle Resolution

The original plan had feedback loops that BNs cannot represent:
- `Protest_State ↔ Regime_Response`
- `Regime_Outcome → Regional_Instability → ... → Regime_Outcome`

These were resolved by modeling equilibrium states:
- `Economic_Stress` serves as proxy for protest pressure
- Regional instability driven by US policy + economic stress (not regime outcome)

## CPT Refinement Pipeline (Phase 2)

Automated pipeline to refine placeholder CPTs while maintaining KL divergence:

```bash
# List CPTs needing refinement
python scripts/refine_cpts.py --list

# Refine all placeholder CPTs
python scripts/refine_cpts.py --refine-all

# Validate after refinement
python scripts/refine_cpts.py --validate

# Compare to MC and check KL divergence
python scripts/refine_cpts.py --validate --compare-mc runs/RUN_*/simulation_results_10k.json
```

**Refinement Process:**
1. Script iterates through 7 placeholder CPTs
2. Generates calibrated values using analyst priors and domain rules
3. Validates column sums and probability bounds
4. Checks KL divergence didn't spike above 0.15

## Interactive Dashboard (Phase 2)

The Streamlit dashboard now includes a **Causal Explorer** mode:

```bash
streamlit run dashboard.py
# Select "Causal" mode in the sidebar
```

**Features:**
- Interactive DAG visualization using pyvis
- Click nodes to see state definitions
- Set evidence (interventions) via sidebar dropdowns
- Real-time posterior probability updates
- Surprise metric display with warning badges
- Sensitivity analysis table

**Node Colors:**
- Green: Root nodes (observable inputs)
- Blue: Intermediate nodes
- Red: Terminal outcome (Regime_Outcome)
- Orange: Evidence nodes (your interventions)

## Future Extensions

1. **Dynamic Bayesian Network**: Model temporal evolution
2. **Probability Oracle**: Use BN to provide probabilities for MC simulation
3. **Real-time Evidence**: Update BN with daily intelligence

## Files

| File | Purpose |
|------|---------|
| `scripts/prototype_causal_graph.py` | Main BN implementation with CausalEngine class |
| `scripts/refine_cpts.py` | Automated CPT refinement pipeline |
| `tests/test_pgmpy_prototype.py` | Unit and integration tests (40 tests) |
| `prompts/cpt_derivation/*.md` | CPT derivation prompts |
| `prompts/cpt_derivation/responses/*.json` | Calibrated CPT values (10 files) |
| `outputs/dag_visualization.png` | DAG visualization |
| `dashboard.py` | Streamlit dashboard with Causal Explorer mode |

## Dependencies

```
pgmpy>=0.1.25
networkx>=3.0
numpy>=1.24.0
matplotlib>=3.7.0  # for visualization
pyvis>=0.3.0       # for interactive DAG (Phase 2)
streamlit>=1.30.0  # for dashboard
```

## Troubleshooting

**Import Error: DiscreteBayesianNetwork**
- pgmpy >= 0.1.26 renamed `BayesianNetwork` to `DiscreteBayesianNetwork`
- The script handles both versions automatically

**CPT Column Sums Not 1.0**
- Check that all rows in `values` array sum to 1.0 for each column
- Use `--validate` flag to check all CPTs

**KL Divergence Too High**
- CPTs may need recalibration
- Check that economic stress classification matches MC assumptions
