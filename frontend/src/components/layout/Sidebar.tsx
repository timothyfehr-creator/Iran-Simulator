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
        <div className="p-4 border-b border-war-room-border">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
            Simulation Controls
          </h2>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <ControlPanel />
        </div>

        <div className="p-4 border-t border-war-room-border">
          <div className="text-xs text-gray-500 space-y-1">
            <div className="flex justify-between">
              <span>Total Runs:</span>
              <span className="text-gray-300">{formatNumber(results?.n_runs || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span>Session Runs:</span>
              <span className="text-gray-300">{runCount}</span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
