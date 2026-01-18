import { mockResults } from '../data/mockData';
import type { SimulationApi, SimulationResults, SimulationParams, SystemStatus } from '../types/simulation';

export const mockApi: SimulationApi = {
  async getResults(): Promise<SimulationResults> {
    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 500));
    return mockResults;
  },

  async runSimulation(params: SimulationParams): Promise<SimulationResults> {
    // Simulate longer delay for running simulation
    await new Promise((resolve) => setTimeout(resolve, 1500));

    // Apply more dramatic variation based on params for visual feedback
    const defectionFactor = params.defectionProbability / 0.05;
    const growthFactor = params.protestGrowthFactor / 1.5;

    // Add randomness to make each run visibly different
    const randomVariation = () => (Math.random() - 0.5) * 0.1;

    // Calculate base survival probability (decreases with higher growth/defection)
    const baseSurvival = Math.max(
      0.4,
      0.83 - (growthFactor - 1) * 0.3 - (defectionFactor - 1) * 0.15 + randomVariation()
    );

    const adjustedResults: SimulationResults = {
      ...mockResults,
      n_runs: params.runs,
      key_event_rates: {
        ...mockResults.key_event_rates,
        security_force_defection: Math.min(
          0.5,
          mockResults.key_event_rates.security_force_defection * defectionFactor + randomVariation() * 0.1
        ),
        ethnic_uprising: Math.min(0.3, 0.088 * growthFactor + randomVariation() * 0.05),
      },
      outcome_distribution: {
        REGIME_SURVIVES_STATUS_QUO: {
          probability: baseSurvival,
          ci_low: baseSurvival - 0.02,
          ci_high: baseSurvival + 0.02,
        },
        MANAGED_TRANSITION: {
          probability: Math.min(0.2, 0.054 + (1 - baseSurvival) * 0.3 + randomVariation() * 0.02),
          ci_low: 0.04,
          ci_high: 0.08,
        },
        REGIME_COLLAPSE_CHAOTIC: {
          probability: Math.min(0.25, 0.04 + (1 - baseSurvival) * 0.25 + randomVariation() * 0.02),
          ci_low: 0.03,
          ci_high: 0.06,
        },
        MILITARY_COUP: {
          probability: Math.min(0.15, 0.031 + defectionFactor * 0.02 + randomVariation() * 0.01),
          ci_low: 0.02,
          ci_high: 0.05,
        },
        CIVIL_WAR: {
          probability: Math.min(0.15, 0.025 + (1 - baseSurvival) * 0.1 + randomVariation() * 0.01),
          ci_low: 0.02,
          ci_high: 0.04,
        },
        FOREIGN_INTERVENTION: {
          probability: Math.min(0.1, 0.02 + randomVariation() * 0.01),
          ci_low: 0.01,
          ci_high: 0.03,
        },
      },
      // Update stress level based on parameters
      economic_analysis: {
        ...mockResults.economic_analysis,
        stress_level: growthFactor > 1.7 || defectionFactor > 3 ? 'critical' :
                      growthFactor > 1.3 || defectionFactor > 2 ? 'pressured' : 'stable',
      },
    };

    return adjustedResults;
  },

  async getStatus(): Promise<SystemStatus> {
    return {
      connected: true,
      lastUpdate: new Date().toISOString(),
    };
  },
};
