export type StressLevel = 'stable' | 'pressured' | 'critical';

export interface OutcomeDistribution {
  probability: number;
  ci_low: number;
  ci_high: number;
}

export interface EconomicAnalysis {
  stress_level: StressLevel;
  rial_rate_used: number;
  inflation_used: number;
  modifiers_applied?: {
    protest_escalation: number;
    elite_fracture: number;
    security_defection: number;
  };
}

export interface KeyEventRates {
  us_soft_intervention: number;
  us_hard_intervention: number;
  security_force_defection: number;
  khamenei_death: number;
  ethnic_uprising: number;
}

export interface SimulationResults {
  n_runs: number;
  outcome_distribution: Record<string, OutcomeDistribution>;
  economic_analysis: EconomicAnalysis;
  key_event_rates: KeyEventRates;
}

export interface SimulationParams {
  runs: number;
  defectionProbability: number;
  protestGrowthFactor: number;
}

export interface SystemStatus {
  connected: boolean;
  lastUpdate: string;
}

export interface SimulationControls {
  timelineDay: number;
  analystConfidence: number;
  runs: number;
  defectionProbability: number;
  protestGrowthFactor: number;
}

export interface SimulationState {
  controls: SimulationControls;
  results: SimulationResults | null;
  isLoading: boolean;
  error: string | null;
}

// =============================================================================
// CAUSAL / BAYESIAN NETWORK TYPES
// =============================================================================

export interface CausalGraphEdge {
  source: string;
  target: string;
}

export interface CausalGraph {
  nodes: Record<string, string[]>;
  edges: CausalGraphEdge[];
  node_categories: Record<string, 'root' | 'intermediate' | 'terminal'>;
}

export interface CausalInferenceRequest {
  evidence: Record<string, string>;
  target: string;
  include_surprise?: boolean;
}

export interface CausalInferenceResult {
  posterior: Record<string, number>;
  evidence: Record<string, string>;
  surprise_score?: number;
  surprise_flag?: boolean;
  surprise_drivers?: string[];
}

export interface SensitivityResult {
  target: string;
  sensitivities: Record<string, number>;
}

export interface CausalStatus {
  available: boolean;
  node_count: number;
  edge_count: number;
  cpts_loaded: boolean;
}

export interface SimulationApi {
  getResults(): Promise<SimulationResults>;
  runSimulation(params: SimulationParams): Promise<SimulationResults>;
  getStatus(): Promise<SystemStatus>;
}
