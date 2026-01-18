import type {
  CausalGraph,
  CausalInferenceRequest,
  CausalInferenceResult,
  SensitivityResult,
  CausalStatus,
} from '../types/simulation';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const causalApi = {
  /**
   * Get the Bayesian Network structure (nodes and edges)
   */
  async getGraph(): Promise<CausalGraph> {
    const res = await fetch(`${API_BASE}/api/causal/graph`);
    if (!res.ok) {
      throw new Error(`Failed to fetch causal graph: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Run Bayesian Network inference with optional evidence
   */
  async infer(request: CausalInferenceRequest): Promise<CausalInferenceResult> {
    const res = await fetch(`${API_BASE}/api/causal/infer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!res.ok) {
      throw new Error(`Failed to run causal inference: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Get sensitivity analysis for a target node
   */
  async getSensitivity(target: string = 'Regime_Outcome'): Promise<SensitivityResult> {
    const res = await fetch(`${API_BASE}/api/causal/sensitivity/${encodeURIComponent(target)}`);
    if (!res.ok) {
      throw new Error(`Failed to get sensitivity: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Check if Causal Engine is available
   */
  async getStatus(): Promise<CausalStatus> {
    const res = await fetch(`${API_BASE}/api/causal/status`);
    if (!res.ok) {
      throw new Error(`Failed to get causal status: ${res.status}`);
    }
    return res.json();
  },
};
