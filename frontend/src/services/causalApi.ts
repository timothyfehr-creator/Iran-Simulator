import type {
  CausalGraph,
  CausalInferenceRequest,
  CausalInferenceResult,
  SensitivityResult,
  CausalStatus,
} from '../types/simulation';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Mock data for when backend is not available
const MOCK_CAUSAL_STATUS: CausalStatus = {
  available: true,
  node_count: 22,
  edge_count: 35,
  cpts_loaded: true,
};

const MOCK_CAUSAL_GRAPH: CausalGraph = {
  nodes: {
    Rial_Rate: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
    Inflation: ['LOW', 'MODERATE', 'HIGH', 'HYPERINFLATION'],
    Khamenei_Health: ['STABLE', 'DECLINING', 'INCAPACITATED'],
    US_Policy_Disposition: ['ENGAGEMENT', 'PRESSURE', 'REGIME_CHANGE'],
    Economic_Stress: ['STABLE', 'PRESSURED', 'CRITICAL'],
    Protest_Escalation: ['LOW', 'MODERATE', 'HIGH', 'MASS'],
    Regime_Response: ['CONCESSION', 'MODERATE', 'CRACKDOWN'],
    Internet_Status: ['FUNCTIONAL', 'PARTIAL', 'BLACKOUT'],
    Protest_Sustained: ['NO', 'YES'],
    Protest_State: ['DORMANT', 'SPORADIC', 'SUSTAINED', 'REVOLUTIONARY'],
    Security_Loyalty: ['LOYAL', 'WAVERING', 'FRACTURED'],
    Elite_Cohesion: ['UNITED', 'STRAINED', 'FRACTURED'],
    Ethnic_Uprising: ['NO', 'YES'],
    Fragmentation_Outcome: ['NONE', 'PARTIAL', 'FULL'],
    Succession_Type: ['ORDERLY', 'CONTESTED', 'CHAOTIC'],
    Israel_Posture: ['DETERRENCE', 'ESCALATION', 'STRIKE'],
    Regional_Instability: ['LOW', 'MODERATE', 'HIGH'],
    Iraq_Stability: ['STABLE', 'UNSTABLE'],
    Syria_Stability: ['STABLE', 'UNSTABLE'],
    Russia_Posture: ['SUPPORTIVE', 'NEUTRAL', 'WITHDRAWN'],
    Gulf_Realignment: ['STATUS_QUO', 'HEDGING', 'REALIGNED'],
    Regime_Outcome: ['STATUS_QUO', 'CONCESSIONS', 'TRANSITION', 'COLLAPSE', 'FRAGMENTATION'],
  },
  edges: [
    { source: 'Rial_Rate', target: 'Economic_Stress' },
    { source: 'Inflation', target: 'Economic_Stress' },
    { source: 'Economic_Stress', target: 'Protest_Escalation' },
    { source: 'Protest_Escalation', target: 'Protest_Sustained' },
    { source: 'Protest_Escalation', target: 'Regime_Response' },
    { source: 'Regime_Response', target: 'Internet_Status' },
    { source: 'Regime_Response', target: 'Security_Loyalty' },
    { source: 'Protest_Sustained', target: 'Protest_State' },
    { source: 'Protest_State', target: 'Ethnic_Uprising' },
    { source: 'Security_Loyalty', target: 'Protest_State' },
    { source: 'Security_Loyalty', target: 'Elite_Cohesion' },
    { source: 'Khamenei_Health', target: 'Elite_Cohesion' },
    { source: 'Khamenei_Health', target: 'Succession_Type' },
    { source: 'Elite_Cohesion', target: 'Fragmentation_Outcome' },
    { source: 'Elite_Cohesion', target: 'Regime_Outcome' },
    { source: 'Protest_State', target: 'Regime_Outcome' },
    { source: 'Security_Loyalty', target: 'Regime_Outcome' },
    { source: 'Ethnic_Uprising', target: 'Regime_Outcome' },
    { source: 'Fragmentation_Outcome', target: 'Regime_Outcome' },
    { source: 'Succession_Type', target: 'Regime_Outcome' },
    { source: 'US_Policy_Disposition', target: 'Regime_Response' },
    { source: 'US_Policy_Disposition', target: 'Israel_Posture' },
    { source: 'Israel_Posture', target: 'Regional_Instability' },
    { source: 'Iraq_Stability', target: 'Regional_Instability' },
    { source: 'Syria_Stability', target: 'Regional_Instability' },
    { source: 'Regional_Instability', target: 'Regime_Outcome' },
    { source: 'Russia_Posture', target: 'Regime_Outcome' },
    { source: 'Gulf_Realignment', target: 'Regional_Instability' },
    { source: 'Internet_Status', target: 'Protest_Sustained' },
  ],
  node_categories: {
    Rial_Rate: 'root',
    Inflation: 'root',
    Khamenei_Health: 'root',
    US_Policy_Disposition: 'root',
    Economic_Stress: 'intermediate',
    Protest_Escalation: 'intermediate',
    Regime_Response: 'intermediate',
    Internet_Status: 'intermediate',
    Protest_Sustained: 'intermediate',
    Protest_State: 'intermediate',
    Security_Loyalty: 'intermediate',
    Elite_Cohesion: 'intermediate',
    Ethnic_Uprising: 'intermediate',
    Fragmentation_Outcome: 'intermediate',
    Succession_Type: 'intermediate',
    Israel_Posture: 'intermediate',
    Regional_Instability: 'intermediate',
    Iraq_Stability: 'root',
    Syria_Stability: 'root',
    Russia_Posture: 'root',
    Gulf_Realignment: 'root',
    Regime_Outcome: 'terminal',
  },
};

function mockInfer(request: CausalInferenceRequest): CausalInferenceResult {
  // Base posterior
  const posterior: Record<string, number> = {
    STATUS_QUO: 0.45,
    CONCESSIONS: 0.20,
    TRANSITION: 0.18,
    COLLAPSE: 0.10,
    FRAGMENTATION: 0.07,
  };

  // Shift posterior based on evidence
  const ev = request.evidence;
  if (ev.Economic_Stress === 'CRITICAL' || ev.Rial_Rate === 'CRITICAL') {
    posterior.STATUS_QUO -= 0.15;
    posterior.COLLAPSE += 0.08;
    posterior.TRANSITION += 0.07;
  }
  if (ev.Security_Loyalty === 'FRACTURED') {
    posterior.STATUS_QUO -= 0.20;
    posterior.COLLAPSE += 0.12;
    posterior.FRAGMENTATION += 0.08;
  }
  if (ev.Protest_State === 'REVOLUTIONARY') {
    posterior.STATUS_QUO -= 0.25;
    posterior.TRANSITION += 0.15;
    posterior.COLLAPSE += 0.10;
  }
  if (ev.Khamenei_Health === 'INCAPACITATED') {
    posterior.STATUS_QUO -= 0.10;
    posterior.TRANSITION += 0.05;
    posterior.FRAGMENTATION += 0.05;
  }

  // Normalize
  const total = Object.values(posterior).reduce((s, v) => s + Math.max(0, v), 0);
  for (const k of Object.keys(posterior)) {
    posterior[k] = Math.max(0, posterior[k]) / total;
  }

  const hasEvidence = Object.keys(ev).length > 0;
  const surpriseScore = hasEvidence ? Math.random() * 0.5 : 0;

  return {
    posterior,
    evidence: ev,
    surprise_score: surpriseScore,
    surprise_flag: surpriseScore > 0.3,
    surprise_drivers: surpriseScore > 0.3
      ? Object.keys(ev).slice(0, 2)
      : undefined,
  };
}

function mockSensitivity(): SensitivityResult {
  return {
    target: 'Regime_Outcome',
    sensitivities: {
      Security_Loyalty: 0.182,
      Protest_State: 0.156,
      Elite_Cohesion: 0.134,
      Economic_Stress: 0.098,
      Khamenei_Health: 0.087,
      Succession_Type: 0.072,
      Ethnic_Uprising: 0.065,
      Regional_Instability: 0.043,
    },
  };
}

let useMock = false;

async function tryFetchOrMock<T>(
  fetcher: () => Promise<T>,
  mockFallback: () => T
): Promise<T> {
  if (useMock) {
    await new Promise((r) => setTimeout(r, 300));
    return mockFallback();
  }
  try {
    return await fetcher();
  } catch {
    // Backend not available — switch to mock for all subsequent calls
    useMock = true;
    console.warn('[CausalApi] Backend not available, using mock data');
    await new Promise((r) => setTimeout(r, 300));
    return mockFallback();
  }
}

export const causalApi = {
  async getGraph(): Promise<CausalGraph> {
    return tryFetchOrMock(
      async () => {
        const res = await fetch(`${API_BASE}/api/causal/graph`);
        if (!res.ok) throw new Error(`Failed to fetch causal graph: ${res.status}`);
        return res.json();
      },
      () => MOCK_CAUSAL_GRAPH
    );
  },

  async infer(request: CausalInferenceRequest): Promise<CausalInferenceResult> {
    return tryFetchOrMock(
      async () => {
        const res = await fetch(`${API_BASE}/api/causal/infer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
        });
        if (!res.ok) throw new Error(`Failed to run causal inference: ${res.status}`);
        return res.json();
      },
      () => mockInfer(request)
    );
  },

  async getSensitivity(target: string = 'Regime_Outcome'): Promise<SensitivityResult> {
    return tryFetchOrMock(
      async () => {
        const res = await fetch(`${API_BASE}/api/causal/sensitivity/${encodeURIComponent(target)}`);
        if (!res.ok) throw new Error(`Failed to get sensitivity: ${res.status}`);
        return res.json();
      },
      () => mockSensitivity()
    );
  },

  async getStatus(): Promise<CausalStatus> {
    return tryFetchOrMock(
      async () => {
        const res = await fetch(`${API_BASE}/api/causal/status`);
        if (!res.ok) throw new Error(`Failed to get causal status: ${res.status}`);
        return res.json();
      },
      () => MOCK_CAUSAL_STATUS
    );
  },
};
