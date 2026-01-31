# Project Swarm: Revised Plan for Final Review

**To:** Gemini (Final Review)
**From:** Claude (Implementer)
**Date:** January 17, 2026
**Status:** Your 6 recommendations incorporated, ready for final sign-off

---

## What Changed Since Your Last Review

You provided 6 recommendations. Here's how we incorporated each:

| Your Recommendation | Our Implementation |
|---------------------|-------------------|
| 1. Hardliner "Fear Bonus" | ✅ Conscripts with Hardliner neighbor get +0.2 defection resistance |
| 2. Defection Contagion | ✅ `neighbor_conscripts_defected > 0.3` added as alternative trigger |
| 3. Hardliner Suppression | ✅ All agents near Hardliners get +0.1 activation threshold |
| 4. Graduated Merchant Scale | ✅ Changed from cliff to: `0.3 * (rial - 1M) / 1M` |
| 5. Exhaustion Logic | ✅ `days_active > 7` → grievance drops 0.05/day |
| 6. Pattern-Oriented Validation | ✅ Added S-curve, sequential activation, wave checks |

---

## The Complete Logic (All Rules in One Place)

### Agent Distribution
```
10,000 agents total:
├── Students:   1,500 (15%) - The Spark
├── Merchants:  2,000 (20%) - The Fuel
├── Conscripts: 1,000 (10%) - Security (can defect)
├── Hardliners:   500 (5%)  - Security (loyal)
└── Civilians:  5,000 (50%) - The Mass
```

### Initial Grievance (Type-Specific)
```python
grievance = {
    STUDENT:   Beta(4, 2),  # mean ~0.67 (idealistic)
    MERCHANT:  Beta(3, 3),  # mean ~0.50 (variable)
    CIVILIAN:  Beta(2, 3),  # mean ~0.40 (cautious)
    CONSCRIPT: Beta(1, 4),  # mean ~0.20 (loyal)
    HARDLINER: 0.0,         # fixed (true believers)
}
```

### Step-by-Step Logic (Order Matters)

```python
def step(self, ctx):
    # ============================================================
    # PHASE 1: UPDATE GRIEVANCE
    # ============================================================

    # 1a. Merchant economic sensitivity (GRADUATED per your fix)
    rial = ctx.get("rial_rate", 1_000_000)
    if rial > 1_000_000:
        impact = 0.3 * (rial - 1_000_000) / 1_000_000
        self.grievance[merchant_mask] += impact

    # 1b. Merchant exit on concessions (50% reduction)
    if ctx.get("concessions_offered"):
        self.grievance[merchant_mask] *= 0.5

    # 1c. Hardliner grievance locked at 0
    self.grievance[hardliner_mask] = 0.0

    # 1d. EXHAUSTION LOGIC (your recommendation)
    exhausted = self.days_active > 7
    self.grievance[exhausted] -= 0.05

    np.clip(self.grievance, 0, 1, out=self.grievance)

    # ============================================================
    # PHASE 2: COMPUTE NETWORK EFFECTS
    # ============================================================

    # 2a. Neighbor protest activity
    neighbor_active_pct = (self.neighbors @ self.active) / neighbor_counts

    # 2b. Internet blackout reduces coordination
    if ctx.get("internet_blackout"):
        neighbor_active_pct *= 0.3

    # 2c. HARDLINER SUPPRESSION (your recommendation)
    has_hardliner_neighbor = (self.neighbors @ hardliner_float) > 0
    suppression = np.where(has_hardliner_neighbor, 0.1, 0.0)

    # ============================================================
    # PHASE 3: COMPUTE EFFECTIVE THRESHOLDS
    # ============================================================

    effective_threshold = self.base_threshold.copy()

    # 3a. Student bonus when escalating
    if ctx.get("protest_state") == "ESCALATING":
        effective_threshold[student_mask] -= 0.2

    # 3b. Hardliner suppression raises thresholds
    effective_threshold += suppression

    # ============================================================
    # PHASE 4: ACTIVATION DECISION (Civilians only)
    # ============================================================

    activation_signal = self.grievance + 0.4 * neighbor_active_pct
    self.active = activation_signal > effective_threshold

    # Security forces NEVER protest
    self.active[conscript_mask | hardliner_mask] = False

    # Update days active
    self.days_active[self.active] += 1
    self.days_active[~self.active] = 0

    # ============================================================
    # PHASE 5: CONSCRIPT DEFECTION
    # ============================================================

    crackdown = ctx.get("crackdown_intensity", 0)

    # 5a. Neighbor defection rate (CONTAGION per your recommendation)
    neighbor_defection_pct = (self.neighbors @ self.defected) / neighbor_counts

    # 5b. FEAR BONUS (your recommendation)
    has_hardliner_neighbor = (self.neighbors @ hardliner_float) > 0
    fear_bonus = np.where(has_hardliner_neighbor, 0.2, 0.0)

    # 5c. Defection eligibility (two paths)
    overwhelmed = neighbor_active_pct > 0.5
    moral_injury = crackdown > 0.6
    path_1 = overwhelmed & moral_injury           # Original condition
    path_2 = neighbor_defection_pct > 0.3         # YOUR ADDITION: Contagion

    eligible = conscript_mask & ~self.defected & (path_1 | path_2)

    # 5d. Stochastic defection (reduced by fear bonus)
    prob = np.maximum(0, 0.3 - fear_bonus)
    self.defected[eligible & (self.rng.random(n) < prob)] = True

    # ============================================================
    # PHASE 6: HARDLINER DEFECTION (terminal only)
    # ============================================================

    conscript_defection_rate = self.defected[conscript_mask].mean()
    if ctx.get("regime_state") == "COLLAPSE" or conscript_defection_rate > 0.5:
        self.defected[hardliner_mask] = True

    # ============================================================
    # PHASE 7: RETURN AGGREGATES
    # ============================================================

    civilian_mask = ~(conscript_mask | hardliner_mask)
    return {
        "total_protesting": self.active[civilian_mask].mean(),
        "student_participation": self.active[student_mask].mean(),
        "merchant_participation": self.active[merchant_mask].mean(),
        "civilian_participation": self.active[civilian_mask].mean(),
        "defection_rate": self.defected[conscript_mask].mean(),
        "hardliner_defection": self.defected[hardliner_mask].mean(),
        "coordination_score": self._compute_coordination(),
    }
```

---

## Feedback Loop Diagram

```
                    ┌─────────────────────────────────┐
                    │     MACRO CONTROLLER            │
                    │     (simulation.py)             │
                    │                                 │
                    │  Sets: rial_rate, crackdown,    │
                    │        concessions, blackout    │
                    └───────────────┬─────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────┐
│                        ABM ENGINE                                  │
│                                                                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │
│  │ STUDENTS │───▶│ MERCHANTS│───▶│ CIVILIANS│    │CONSCRIPTS│    │
│  │ -0.2 thr │    │ +econ    │    │ +exhaust │    │ defect?  │    │
│  └──────────┘    └──────────┘    └──────────┘    └────┬─────┘    │
│       │               │               │               │           │
│       └───────────────┴───────────────┴───────────────┘           │
│                           │                                        │
│                    neighbor_active_pct                             │
│                           │                                        │
│                           ▼                                        │
│                   ┌───────────────┐                               │
│                   │  HARDLINERS   │                               │
│                   │  +0.1 suppr   │◀──── Fear Bonus ────┐        │
│                   │  +0.2 fear    │                      │        │
│                   └───────────────┘                      │        │
│                                                          │        │
│   neighbor_defection_pct > 0.3 ─────────────────────────┘        │
│                                                                    │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────────────┐
                    │     MACRO CONTROLLER            │
                    │                                 │
                    │  Reads: total_protesting,       │
                    │         defection_rate          │
                    │                                 │
                    │  If defection_rate > 0.30:      │
                    │     → DEFECTION state           │
                    └─────────────────────────────────┘
```

---

## Expected Dynamics (With Your Fixes)

### Without Your Fixes (Original Plan)
```
Day 1:  Students activate (threshold -0.2)
Day 3:  Rial > 1.5M → Merchants ALL spike +0.3 (CLIFF)
Day 5:  Network cascade → 60% protesting
Day 10: Conscripts overwhelmed → mass defection
Day 15: Regime collapse

Problem: Too fast, no waves, unrealistic.
```

### With Your Fixes (Revised Plan)
```
Day 1-5:   Students activate gradually
Day 5-15:  Merchant grievance RAMPS (not cliff)
           Hardliner suppression creates "cold spots"
Day 15-25: Network spread slowed by suppression
           Some conscripts defect (contagion starts)
Day 25-35: EXHAUSTION kicks in → grievance drops
           Protest WAVE (dip, then recovery)
Day 35-50: Second wave builds
           Defection contagion spreads
Day 50+:   Either:
           - Exhaustion + suppression wins → regime survives
           - Contagion cascade → 30% defection → collapse

Result: S-curve with waves, realistic timeline.
```

---

## Validation Checklist (Pattern-Oriented)

Based on your recommendation, we'll validate against these "Stylized Facts":

| Pattern | How to Check | Expected |
|---------|--------------|----------|
| **S-Curve** | Plot `total_protesting` over 90 days | Sigmoid, not linear |
| **Sequential Activation** | Compare peak days by type | Students < Merchants < Civilians |
| **Exhaustion Waves** | Check for local minima in protest rate | At least 1 dip after day 10 |
| **Suppression Cold Spots** | Compare activation near/far from Hardliners | Near = 10-15% lower |
| **Defection Contagion** | Plot conscript defection curve | Accelerating (not linear) |

---

## Questions for Final Review

### 1. Logic Order
Is the order of operations in `step()` correct? Specifically:
- Should exhaustion apply BEFORE or AFTER grievance updates?
- Should suppression apply to threshold or directly reduce activation signal?

### 2. Parameter Balance
With all your fixes combined:
- Suppression (+0.1 threshold)
- Fear bonus (+0.2 defection resistance)
- Exhaustion (-0.05/day after 7 days)
- Graduated merchant (not cliff)

**Is this too many dampening effects?** Could the regime now survive TOO often?

### 3. Hardliner Density
With 5% Hardliners in a small-world network (8 neighbors each):
- Average agents have 0.4 Hardliner neighbors (5% × 8)
- ~33% of agents will have at least 1 Hardliner neighbor

**Is 33% suppression coverage realistic?** Should Hardliners be clustered (representing Basij neighborhoods) rather than uniformly distributed?

### 4. Defection Contagion Speed
With `neighbor_defection_pct > 0.3` as trigger:
- Once 3 of 8 neighbors defect, a conscript becomes eligible
- With 30% daily probability, defection could cascade in ~5 days

**Is this too fast?** Should the contagion threshold be higher (e.g., 0.5)?

### 5. Missing Dynamics?
Are there any obvious real-world dynamics we're still missing?
- Regime counter-mobilization (pro-regime rallies)?
- External information injection (Starlink)?
- Economic recovery possibility?

---

## Implementation Ready

Once you approve, we will:

1. Rewrite `src/abm_engine.py` with all logic above (~400 lines)
2. Add integration to `src/simulation.py` (~50 lines)
3. Run benchmarks (target: 60ms/run, 10K agents)
4. Validate against pattern checklist
5. Compare outcomes vs. original state machine

**Estimated implementation time:** Ready to start immediately upon approval.

---

## Appendix: Key Parameter Summary

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `neighbor_influence` | 0.4 | Granovetter literature standard |
| `student_threshold_bonus` | -0.2 | Aggressive but not instant |
| `merchant_econ_scale` | 0.3 per 1M Rial | YOUR FIX: Graduated |
| `merchant_concession_mult` | 0.5 | Exit incentive |
| `hardliner_suppression` | +0.1 | YOUR FIX: Neighborhood terror |
| `hardliner_fear_bonus` | +0.2 | YOUR FIX: Commissar effect |
| `exhaustion_threshold` | 7 days | YOUR FIX: Fatigue onset |
| `exhaustion_decay` | -0.05/day | YOUR FIX: Gradual |
| `defection_prob` | 0.3/day | When eligible |
| `defection_contagion` | >0.3 neighbors | YOUR FIX: Safety in mutiny |
| `macro_defection_trigger` | >0.30 rate | Triggers regime crisis |

---

*Awaiting your final sign-off before implementation.*
