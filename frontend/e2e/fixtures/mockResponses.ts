import type { SimulationResults } from '../../src/types/simulation';

export const mockSimulationResponse: SimulationResults = {
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
