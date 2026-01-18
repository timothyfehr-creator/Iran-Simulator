import { Play, Loader2 } from 'lucide-react';

interface RunSimulationButtonProps {
  isLoading: boolean;
  onClick: () => void;
  disabled?: boolean;
}

export function RunSimulationButton({
  isLoading,
  onClick,
  disabled = false,
}: RunSimulationButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={isLoading || disabled}
      className="w-full btn-primary flex items-center justify-center gap-2 py-3"
      aria-label={isLoading ? 'Running simulation' : 'Run simulation'}
    >
      {isLoading ? (
        <>
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Running...</span>
        </>
      ) : (
        <>
          <Play className="w-5 h-5" />
          <span>Run Simulation</span>
        </>
      )}
    </button>
  );
}
