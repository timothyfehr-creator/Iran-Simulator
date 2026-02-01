import { ControlPanel } from '../controls/ControlPanel';
import { useSimulationStore } from '../../store/simulationStore';
import { formatNumber } from '../../utils/formatters';

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export function Sidebar({ isOpen = true, onClose }: SidebarProps) {
  const { results, runCount } = useSimulationStore();

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        data-testid="sidebar"
        className={`
          fixed md:relative inset-y-0 left-0 z-50
          w-72 md:w-64 lg:w-72
          bg-war-room-panel border-r border-war-room-border
          transform transition-transform duration-300 ease-in-out
          ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
          flex flex-col
        `}
      >
        <div className="px-5 py-3 border-b border-war-room-border">
          <h2 className="text-heading uppercase tracking-wider text-war-room-text-secondary">
            Simulation Controls
          </h2>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          <ControlPanel />
        </div>

        <div className="px-5 py-3 border-t border-war-room-border bg-war-room-bg/30">
          <div className="text-caption text-war-room-muted space-y-1.5">
            <div className="flex justify-between">
              <span>Total Runs</span>
              <span className="font-mono font-medium text-war-room-text-primary">
                {formatNumber(results?.n_runs || 0)}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Session Runs</span>
              <span className="font-mono font-medium text-war-room-text-primary">{runCount}</span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
