import { Activity, Menu } from 'lucide-react';
import { DefconWidget } from '../status/DefconWidget';
import { useSimulationStore } from '../../store/simulationStore';

interface HeaderProps {
  onMenuClick?: () => void;
  showMenuButton?: boolean;
}

export function Header({ onMenuClick, showMenuButton = false }: HeaderProps) {
  const results = useSimulationStore((state) => state.results);
  const stressLevel = results?.economic_analysis.stress_level || 'stable';

  return (
    <header className="flex items-center justify-between px-6 py-4 panel border-b border-war-room-border">
      <div className="flex items-center gap-4">
        {showMenuButton && (
          <button
            onClick={onMenuClick}
            className="p-2 hover:bg-war-room-border rounded-lg transition-colors md:hidden"
            aria-label="Toggle menu"
          >
            <Menu className="w-6 h-6" />
          </button>
        )}
        <div className="flex items-center gap-3">
          <Activity className="w-8 h-8 text-war-room-accent" />
          <div>
            <h1 className="text-xl font-bold tracking-wide uppercase">Iran Simulator</h1>
            <p className="text-xs text-gray-500 uppercase tracking-widest">War Room Dashboard</p>
          </div>
        </div>
      </div>

      <DefconWidget status={stressLevel} label="REGIME STABILITY" />
    </header>
  );
}
