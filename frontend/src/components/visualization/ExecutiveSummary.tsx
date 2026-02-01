import { useSimulationStore } from '../../store/simulationStore';
import { formatPercent, formatNumber, formatRial } from '../../utils/formatters';
import { outcomeLabels } from '../../data/mockData';
import { Panel } from '../ui/Panel';
import { StatCard } from '../ui/StatCard';
import { Badge } from '../ui/Badge';
import { EmptyState } from '../ui/EmptyState';
import { Skeleton } from '../ui/Skeleton';
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Shield,
  Users,
  DollarSign,
  Activity,
  BarChart3,
} from 'lucide-react';

export function ExecutiveSummary() {
  const results = useSimulationStore((state) => state.results);
  const isLoading = useSimulationStore((state) => state.isLoading);

  if (isLoading && !results) {
    return <ExecutiveSummarySkeleton />;
  }

  if (!results) {
    return (
      <EmptyState
        icon={<BarChart3 className="w-10 h-10" />}
        title="No simulation data"
        description="Run a simulation to generate the executive summary."
      />
    );
  }

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

  return (
    <div className="space-y-4">
      {/* Top Line Assessment */}
      <Panel accent="blue">
        <div className="flex items-start gap-3">
          <Activity className="w-5 h-5 text-war-room-accent mt-0.5 flex-shrink-0" />
          <div>
            <h3 className="text-heading text-war-room-text-primary mb-2">
              Bottom Line Up Front (BLUF)
            </h3>
            <p className="text-body text-war-room-text-secondary leading-relaxed">
              Based on {formatNumber(results.n_runs)} Monte Carlo simulations, the most likely outcome
              is <span className="text-war-room-text-primary font-semibold">{topOutcome.label}</span> with a{' '}
              <span className="text-war-room-accent font-bold font-mono">
                {formatPercent(topOutcome.probability)}
              </span>{' '}
              probability. The regime has a{' '}
              <span className={regimeSurvival > 0.7 ? 'text-war-room-success' : 'text-war-room-warning'}>
                {formatPercent(regimeSurvival)}
              </span>{' '}
              chance of maintaining power through the simulation period.
            </p>
          </div>
        </div>
      </Panel>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard
          icon={<Shield className="w-4 h-4" />}
          label="Regime Stability"
          value={formatPercent(regimeSurvival)}
          status={regimeSurvival > 0.7 ? 'success' : regimeSurvival > 0.4 ? 'warning' : 'danger'}
        />
        <StatCard
          icon={<AlertTriangle className="w-4 h-4" />}
          label="Collapse Risk"
          value={formatPercent(collapseRisk)}
          status={collapseRisk > 0.2 ? 'danger' : collapseRisk > 0.1 ? 'warning' : 'success'}
        />
        <StatCard
          icon={<DollarSign className="w-4 h-4" />}
          label="Economic Stress"
          value={stressLevel.toUpperCase()}
          unit={`Rial: ${formatRial(results.economic_analysis.rial_rate_used)}`}
          status={stressLevel === 'critical' ? 'danger' : stressLevel === 'pressured' ? 'warning' : 'success'}
        />
      </div>

      {/* Key Event Probabilities */}
      <Panel title="Key Event Probabilities">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <EventRow
            icon={<Users className="w-4 h-4" />}
            label="Security Force Defection"
            value={formatPercent(results.key_event_rates.security_force_defection)}
          />
          <EventRow
            icon={<TrendingUp className="w-4 h-4" />}
            label="Ethnic Uprising"
            value={formatPercent(results.key_event_rates.ethnic_uprising)}
          />
          <EventRow
            icon={<AlertTriangle className="w-4 h-4" />}
            label="Supreme Leader Death"
            value={formatPercent(results.key_event_rates.khamenei_death)}
          />
          <EventRow
            icon={<TrendingDown className="w-4 h-4" />}
            label="US Intervention"
            value={formatPercent(results.key_event_rates.us_intervention)}
          />
        </div>
      </Panel>

      {/* Outcome Ranking */}
      <Panel title="Outcome Probability Ranking">
        <div className="space-y-3">
          {sortedOutcomes.map((outcome, index) => (
            <div key={outcome.key} className="flex items-center gap-3">
              <span className="text-caption text-war-room-muted w-6">{index + 1}.</span>
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-body text-war-room-text-secondary">{outcome.label}</span>
                  <span className="font-mono text-mono text-war-room-accent">
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
      </Panel>

      {/* Analyst Notes */}
      <Panel accent="yellow" title="Key Uncertainties">
        <ul className="text-body text-war-room-text-secondary space-y-2 list-disc list-inside">
          <li>Security force loyalty remains the most sensitive variable</li>
          <li>Economic stress could accelerate protest momentum unexpectedly</li>
          <li>External intervention scenarios have wide confidence intervals</li>
          <li>Supreme Leader succession planning is opaque and unpredictable</li>
        </ul>
      </Panel>
    </div>
  );
}

function EventRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between p-3 bg-war-room-bg/50 rounded-lg">
      <div className="flex items-center gap-2">
        <span className="text-war-room-text-secondary">{icon}</span>
        <span className="text-body text-war-room-text-secondary">{label}</span>
      </div>
      <span className="font-mono text-mono text-war-room-accent">{value}</span>
    </div>
  );
}

function ExecutiveSummarySkeleton() {
  return (
    <div className="space-y-4">
      <div className="panel p-5 space-y-3">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="panel p-5 space-y-3">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-8 w-20" />
          </div>
        ))}
      </div>
      <div className="panel p-5 space-y-3">
        <Skeleton className="h-4 w-36" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </div>
    </div>
  );
}
