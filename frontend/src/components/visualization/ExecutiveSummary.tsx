import { useSimulationStore } from '../../store/simulationStore';
import { formatPercent, formatNumber, formatRial } from '../../utils/formatters';
import { outcomeLabels } from '../../data/mockData';
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Shield,
  Users,
  DollarSign,
  Activity,
} from 'lucide-react';

export function ExecutiveSummary() {
  const results = useSimulationStore((state) => state.results);

  if (!results) {
    return (
      <div className="flex items-center justify-center min-h-[400px] text-gray-500">
        No simulation data available. Run a simulation to generate the executive summary.
      </div>
    );
  }

  // Sort outcomes by probability
  const sortedOutcomes = Object.entries(results.outcome_distribution)
    .map(([key, value]) => ({
      key,
      label: outcomeLabels[key] || key,
      ...value,
    }))
    .sort((a, b) => b.probability - a.probability);

  const topOutcome = sortedOutcomes[0];
  const regimeSurvival = results.outcome_distribution.REGIME_SURVIVES_STATUS_QUO?.probability || 0;
  const collapseRisk =
    (results.outcome_distribution.REGIME_COLLAPSE_CHAOTIC?.probability || 0) +
    (results.outcome_distribution.CIVIL_WAR?.probability || 0);

  const stressLevel = results.economic_analysis.stress_level;
  const stressColors = {
    stable: 'text-war-room-success',
    pressured: 'text-war-room-warning',
    critical: 'text-war-room-danger',
  };

  return (
    <div className="space-y-6 p-2">
      {/* Top Line Assessment */}
      <div className="panel p-6 border-l-4 border-war-room-accent">
        <h3 className="text-lg font-bold text-white mb-3 flex items-center gap-2">
          <Activity className="w-5 h-5 text-war-room-accent" />
          Bottom Line Up Front (BLUF)
        </h3>
        <p className="text-gray-300 leading-relaxed">
          Based on {formatNumber(results.n_runs)} Monte Carlo simulations, the most likely outcome
          is <span className="text-white font-semibold">{topOutcome.label}</span> with a{' '}
          <span className="text-war-room-accent font-bold">
            {formatPercent(topOutcome.probability)}
          </span>{' '}
          probability. The regime has a{' '}
          <span className={regimeSurvival > 0.7 ? 'text-war-room-success' : 'text-war-room-warning'}>
            {formatPercent(regimeSurvival)}
          </span>{' '}
          chance of maintaining power through the simulation period.
        </p>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Regime Stability */}
        <div className="panel p-4">
          <div className="flex items-center gap-2 mb-2">
            <Shield className="w-4 h-4 text-gray-400" />
            <span className="text-xs text-gray-400 uppercase tracking-wider">Regime Stability</span>
          </div>
          <div className="text-2xl font-bold text-white">{formatPercent(regimeSurvival)}</div>
          <div className="text-xs text-gray-500 mt-1">Probability of status quo survival</div>
        </div>

        {/* Collapse Risk */}
        <div className="panel p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-war-room-danger" />
            <span className="text-xs text-gray-400 uppercase tracking-wider">Collapse Risk</span>
          </div>
          <div className="text-2xl font-bold text-war-room-danger">{formatPercent(collapseRisk)}</div>
          <div className="text-xs text-gray-500 mt-1">Chaotic collapse + civil war combined</div>
        </div>

        {/* Economic Stress */}
        <div className="panel p-4">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-4 h-4 text-gray-400" />
            <span className="text-xs text-gray-400 uppercase tracking-wider">Economic Stress</span>
          </div>
          <div className={`text-2xl font-bold uppercase ${stressColors[stressLevel]}`}>
            {stressLevel}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            Rial: {formatRial(results.economic_analysis.rial_rate_used)}
          </div>
        </div>
      </div>

      {/* Key Event Probabilities */}
      <div className="panel p-6">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Key Event Probabilities
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="flex items-center justify-between p-3 bg-war-room-bg/50 rounded-lg">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-300">Security Force Defection</span>
            </div>
            <span className="font-mono text-war-room-accent">
              {formatPercent(results.key_event_rates.security_force_defection)}
            </span>
          </div>

          <div className="flex items-center justify-between p-3 bg-war-room-bg/50 rounded-lg">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-300">Ethnic Uprising</span>
            </div>
            <span className="font-mono text-war-room-accent">
              {formatPercent(results.key_event_rates.ethnic_uprising)}
            </span>
          </div>

          <div className="flex items-center justify-between p-3 bg-war-room-bg/50 rounded-lg">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-300">Supreme Leader Death</span>
            </div>
            <span className="font-mono text-war-room-accent">
              {formatPercent(results.key_event_rates.khamenei_death)}
            </span>
          </div>

          <div className="flex items-center justify-between p-3 bg-war-room-bg/50 rounded-lg">
            <div className="flex items-center gap-2">
              <TrendingDown className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-300">US Intervention</span>
            </div>
            <span className="font-mono text-war-room-accent">
              {formatPercent(results.key_event_rates.us_intervention)}
            </span>
          </div>
        </div>
      </div>

      {/* Outcome Ranking */}
      <div className="panel p-6">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Outcome Probability Ranking
        </h3>
        <div className="space-y-3">
          {sortedOutcomes.map((outcome, index) => (
            <div key={outcome.key} className="flex items-center gap-3">
              <span className="text-xs text-gray-500 w-6">{index + 1}.</span>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm text-gray-300">{outcome.label}</span>
                  <span className="font-mono text-sm text-war-room-accent">
                    {formatPercent(outcome.probability)}
                  </span>
                </div>
                <div className="h-1.5 bg-war-room-bg rounded-full overflow-hidden">
                  <div
                    className="h-full bg-war-room-accent rounded-full transition-all duration-500"
                    style={{ width: `${outcome.probability * 100}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Analyst Notes */}
      <div className="panel p-6 border-l-4 border-war-room-warning">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Key Uncertainties
        </h3>
        <ul className="text-sm text-gray-400 space-y-2 list-disc list-inside">
          <li>Security force loyalty remains the most sensitive variable</li>
          <li>Economic stress could accelerate protest momentum unexpectedly</li>
          <li>External intervention scenarios have wide confidence intervals</li>
          <li>Supreme Leader succession planning is opaque and unpredictable</li>
        </ul>
      </div>
    </div>
  );
}
