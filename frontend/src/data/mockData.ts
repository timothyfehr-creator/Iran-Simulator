import type { SimulationResults } from '../types/simulation';

export const mockResults: SimulationResults = {
  n_runs: 10000,
  outcome_distribution: {
    REGIME_SURVIVES_STATUS_QUO: { probability: 0.83, ci_low: 0.82, ci_high: 0.84 },
    MANAGED_TRANSITION: { probability: 0.054, ci_low: 0.05, ci_high: 0.06 },
    REGIME_COLLAPSE_CHAOTIC: { probability: 0.04, ci_low: 0.037, ci_high: 0.044 },
    MILITARY_COUP: { probability: 0.031, ci_low: 0.028, ci_high: 0.035 },
    CIVIL_WAR: { probability: 0.025, ci_low: 0.022, ci_high: 0.029 },
    FOREIGN_INTERVENTION: { probability: 0.02, ci_low: 0.017, ci_high: 0.024 },
  },
  economic_analysis: {
    stress_level: 'critical',
    rial_rate_used: 1429000,
    inflation_used: 35,
    modifiers_applied: {
      protest_escalation: 1.2,
      elite_fracture: 1.3,
      security_defection: 1.15,
    },
  },
  key_event_rates: {
    us_soft_intervention: 0.70,
    us_hard_intervention: 0.25,
    security_force_defection: 0.028,
    khamenei_death: 0.077,
    ethnic_uprising: 0.088,
  },
};

export const outcomeLabels: Record<string, string> = {
  REGIME_SURVIVES_STATUS_QUO: 'Regime Survives (Status Quo)',
  MANAGED_TRANSITION: 'Managed Transition',
  REGIME_COLLAPSE_CHAOTIC: 'Chaotic Collapse',
  MILITARY_COUP: 'Military Coup',
  CIVIL_WAR: 'Civil War',
  FOREIGN_INTERVENTION: 'Foreign Intervention',
};

export const outcomeColors: Record<string, string> = {
  REGIME_SURVIVES_STATUS_QUO: '#10b981',
  MANAGED_TRANSITION: '#3b82f6',
  REGIME_COLLAPSE_CHAOTIC: '#ef4444',
  MILITARY_COUP: '#f59e0b',
  CIVIL_WAR: '#dc2626',
  FOREIGN_INTERVENTION: '#8b5cf6',
};
