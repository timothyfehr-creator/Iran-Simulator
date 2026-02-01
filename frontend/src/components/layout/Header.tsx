import { Activity, Menu, Shield, AlertTriangle, DollarSign } from 'lucide-react';
import { DefconWidget } from '../status/DefconWidget';
import { useSimulationStore } from '../../store/simulationStore';
import { formatPercent } from '../../utils/formatters';

interface HeaderProps {
  onMenuClick?: () => void;
  showMenuButton?: boolean;
}

export function Header({ onMenuClick, showMenuButton = false }: HeaderProps) {
  const results = useSimulationStore((state) => state.results);
  const stressLevel = results?.economic_analysis.stress_level || 'stable';

  const regimeSurvival = results?.outcome_distribution.REGIME_SURVIVES_STATUS_QUO?.probability || 0;
  const collapseRisk =
    (results?.outcome_distribution.REGIME_COLLAPSE_CHAOTIC?.probability || 0) +
    (results?.outcome_distribution.CIVIL_WAR?.probability || 0);

  return (
    <header className="panel border-b border-war-room-border rounded-none">
      <div className="flex items-center justify-between px-5 py-3">
        <div className="flex items-center gap-4">
          {showMenuButton && (
            <button
              onClick={onMenuClick}
              className="p-2 hover:bg-war-room-border rounded-lg transition-colors md:hidden focus-visible:ring-2 focus-visible:ring-war-room-accent focus-visible:ring-offset-2 focus-visible:ring-offset-war-room-bg"
              aria-label="Toggle menu"
            >
              <Menu className="w-6 h-6" />
            </button>
          )}
          <div className="flex items-center gap-3">
            <Activity className="w-7 h-7 text-war-room-accent" />
            <div>
              <h1 className="text-display tracking-wide uppercase leading-tight">Iran Simulator</h1>
              <p className="text-caption text-war-room-muted uppercase tracking-widest">
                War Room Dashboard
              </p>
            </div>
          </div>
        </div>

        <div className="hidden lg:flex items-center gap-3">
          <MiniStat
            icon={<Shield className="w-3.5 h-3.5" />}
            label="Regime Survival"
            value={formatPercent(regimeSurvival)}
            status={regimeSurvival > 0.7 ? 'success' : regimeSurvival > 0.4 ? 'warning' : 'danger'}
          />
          <MiniStat
            icon={<AlertTriangle className="w-3.5 h-3.5" />}
            label="Collapse Risk"
            value={formatPercent(collapseRisk)}
            status={collapseRisk > 0.2 ? 'danger' : collapseRisk > 0.1 ? 'warning' : 'success'}
          />
          <MiniStat
            icon={<DollarSign className="w-3.5 h-3.5" />}
            label="Econ Stress"
            value={stressLevel.toUpperCase()}
            status={stressLevel === 'critical' ? 'danger' : stressLevel === 'pressured' ? 'warning' : 'success'}
          />
          <div className="w-px h-8 bg-war-room-border mx-1" />
          <DefconWidget status={stressLevel} label="REGIME STABILITY" />
        </div>

        <div className="lg:hidden">
          <DefconWidget status={stressLevel} label="REGIME STABILITY" />
        </div>
      </div>
    </header>
  );
}

function MiniStat({
  icon,
  label,
  value,
  status,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  status: 'success' | 'warning' | 'danger';
}) {
  const colors = {
    success: 'text-war-room-success',
    warning: 'text-war-room-warning',
    danger: 'text-war-room-danger',
  };

  return (
    <div className="bg-war-room-bg/50 rounded-lg px-3 py-1.5 flex items-center gap-2">
      <span className="text-war-room-text-secondary">{icon}</span>
      <div>
        <div className="text-[10px] text-war-room-muted uppercase tracking-wider">{label}</div>
        <div className={`text-mono font-bold ${colors[status]}`}>{value}</div>
      </div>
    </div>
  );
}
