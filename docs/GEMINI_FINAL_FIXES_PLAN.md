# Gemini Final Fixes Plan

**Instructions:** Run each fix in order on `src/abm_engine.py`

---

## FIX 1: Network Bug

**Find this method and REPLACE entirely:**

```python
def _build_small_world_network(self, n: int, k: int, p: float) -> sparse.csr_matrix:
    """Build Watts-Strogatz small-world network."""
    if k % 2 != 0:
        k += 1
    half_k = k // 2

    rows = []
    cols = []

    for i in range(n):
        for j in range(1, half_k + 1):
            target = (i + j) % n
            if self.rng.random() < p:
                new_target = self.rng.integers(0, n)
                while new_target == i or new_target == target:
                    new_target = self.rng.integers(0, n)
                target = new_target
            rows.append(i)
            cols.append(target)

    data = np.ones(len(rows), dtype=np.float32)
    adj = sparse.csr_matrix((data, (rows, cols)), shape=(n, n))
    return (adj + adj.T).tocsr()
```

---

## FIX 2: Merchant Non-Accumulation

**In the `step()` method, find PHASE 2 section. REPLACE this block:**

```python
# --- Merchant Economic Sensitivity (Graduated Scale - Gemini Fix) ---
merchant_mask = self.agent_type == MERCHANT
rial_rate = ctx.get("rial_rate", 1_000_000)
if rial_rate > 1_000_000:
    # Scales with severity: 0 at 1M, +0.3 at 2M
    economic_impact = cfg.merchant_economic_scale * (rial_rate - 1_000_000) / 1_000_000
    self.grievance[merchant_mask] += economic_impact
```

**WITH this:**

```python
# --- Merchant Economic Sensitivity (Non-accumulating) ---
merchant_mask = self.agent_type == MERCHANT
rial_rate = ctx.get("rial_rate", 1_000_000)
# Economic boost applied to activation_signal in Phase 5, not here
```

**Then in PHASE 5, REPLACE this line:**

```python
activation_signal = self.grievance + cfg.neighbor_influence * neighbor_active_pct
```

**WITH this:**

```python
# Economic pressure for merchants (non-accumulating)
economic_boost = np.zeros(n, dtype=np.float32)
if rial_rate > 1_000_000:
    economic_boost[merchant_mask] = cfg.merchant_economic_scale * (rial_rate - 1_000_000) / 1_000_000

activation_signal = self.grievance + cfg.neighbor_influence * neighbor_active_pct + economic_boost
```

---

## FIX 3: Add Churn Rate

**In `step()` PHASE 9, find the `result = {` dict and ADD this key:**

```python
"churn_rate": float((self.active & ~was_active).sum() + (~self.active & was_active).sum()) / n,
```

---

## FIX 4: Add Commissar Debug Metric

**In `get_snapshot()`, REPLACE the return statement with:**

```python
# Commissar metric
hardliner_vec = (self.agent_type == HARDLINER).astype(np.float32)
has_commissar = np.array(self.neighbors @ hardliner_vec).flatten() > 0

return {
    "grievance": self.grievance.copy(),
    "threshold": self.base_threshold.copy(),
    "active": self.active.copy(),
    "defected": self.defected.copy(),
    "days_active": self.days_active.copy(),
    "agent_type": self.agent_type.copy(),
    "grievance_histogram": {
        "bins": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        "counts": [
            int(((self.grievance >= lo) & (self.grievance < hi)).sum())
            for lo, hi in [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]
        ]
    },
    "by_type": {
        "student": {
            "count": int((self.agent_type == STUDENT).sum()),
            "active_pct": float(self.active[self.agent_type == STUDENT].mean()) if (self.agent_type == STUDENT).any() else 0.0,
            "avg_grievance": float(self.grievance[self.agent_type == STUDENT].mean()) if (self.agent_type == STUDENT).any() else 0.0,
        },
        "merchant": {
            "count": int((self.agent_type == MERCHANT).sum()),
            "active_pct": float(self.active[self.agent_type == MERCHANT].mean()) if (self.agent_type == MERCHANT).any() else 0.0,
            "avg_grievance": float(self.grievance[self.agent_type == MERCHANT].mean()) if (self.agent_type == MERCHANT).any() else 0.0,
        },
        "civilian": {
            "count": int((self.agent_type == CIVILIAN).sum()),
            "active_pct": float(self.active[self.agent_type == CIVILIAN].mean()) if (self.agent_type == CIVILIAN).any() else 0.0,
            "avg_grievance": float(self.grievance[self.agent_type == CIVILIAN].mean()) if (self.agent_type == CIVILIAN).any() else 0.0,
        },
        "conscript": {
            "count": int((self.agent_type == CONSCRIPT).sum()),
            "defected_pct": float(self.defected[self.agent_type == CONSCRIPT].mean()) if (self.agent_type == CONSCRIPT).any() else 0.0,
        },
        "hardliner": {
            "count": int((self.agent_type == HARDLINER).sum()),
            "defected_pct": float(self.defected[self.agent_type == HARDLINER].mean()) if (self.agent_type == HARDLINER).any() else 0.0,
        },
    },
    "debug_metrics": {
        "conscripts_under_surveillance": int((has_commissar & (self.agent_type == CONSCRIPT)).sum())
    }
}
```

---

## VERIFY

```bash
source .venv/bin/activate

# Network fix (should show ~8)
python -c "from src.abm_engine import ABMEngine; e = ABMEngine({'n_agents': 1000}); print(f'avg_neighbors={e.neighbor_counts.mean():.1f}')"

# Churn rate exists
python -c "from src.abm_engine import ABMEngine; e = ABMEngine({'n_agents': 1000}); r = e.step({}); print(f'churn_rate={r.get(\"churn_rate\", \"MISSING\")}')"

# Merchant non-accumulation (should stay < 0.9)
python -c "from src.abm_engine import ABMEngine; e = ABMEngine({'n_agents': 1000, 'seed': 42}); [e.step({'rial_rate': 2000000}) for _ in range(5)]; print(f'merchant_grievance={e.grievance[e.agent_type == 1].mean():.3f}')"

# Full test suite
python tests/test_abm_engine.py
```

---

**END OF PLAN**
