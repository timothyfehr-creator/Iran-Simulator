import { useSimulationStore } from '../../store/simulationStore';
import { RunSimulationButton } from './RunSimulationButton';
import { ConfidenceSlider } from './ConfidenceSlider';
import { Clock, Timer, CheckCircle, AlertTriangle } from 'lucide-react';
import { useState, useEffect } from 'react';

export function ControlPanel() {
  const { controls, isLoading, error, updateControl, runSimulation, lastRunTime, lastRunDuration, runCount } =
    useSimulationStore();
  const [showSuccess, setShowSuccess] = useState(false);
  const [prevRunCount, setPrevRunCount] = useState(runCount);

  // Flash success indicator when a run completes
  useEffect(() => {
    if (runCount > prevRunCount && !isLoading) {
      setShowSuccess(true);
      const timer = setTimeout(() => setShowSuccess(false), 3000);
      setPrevRunCount(runCount);
      return () => clearTimeout(timer);
    }
    if (runCount !== prevRunCount) {
      setPrevRunCount(runCount);
    }
  }, [runCount, isLoading, prevRunCount]);

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="space-y-6">
      <RunSimulationButton isLoading={isLoading} onClick={runSimulation} />

      {/* Success flash */}
      {showSuccess && (
        <div className="flex items-center gap-2 px-3 py-2 bg-war-room-success/15 border border-war-room-success/30 rounded-lg text-war-room-success text-caption animate-in">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span>Simulation complete — results updated</span>
        </div>
      )}

      {/* Error display */}
      {error && (
        <div className="flex items-center gap-2 px-3 py-2 bg-war-room-danger/15 border border-war-room-danger/30 rounded-lg text-war-room-danger text-caption">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Last Run Info */}
      {lastRunTime && (
        <div className="bg-war-room-bg/50 rounded-lg p-3 space-y-1.5">
          <div className="flex items-center gap-2 text-caption text-war-room-text-secondary">
            <Clock className="w-3.5 h-3.5" />
            <span>Last run: {formatTime(lastRunTime)}</span>
          </div>
          {lastRunDuration && (
            <div className="flex items-center gap-2 text-caption text-war-room-text-secondary">
              <Timer className="w-3.5 h-3.5" />
              <span>Duration: {formatDuration(lastRunDuration)}</span>
            </div>
          )}
        </div>
      )}

      {/* Scenario Parameters */}
      <div className="space-y-3">
        <h3 className="text-caption uppercase tracking-wider text-war-room-muted font-medium">
          Scenario Parameters
        </h3>
        <div className="space-y-5">
          <ConfidenceSlider
            label="Security Force Loyalty"
            description="How likely are IRGC and Basij forces to remain loyal to the regime? Lower values mean higher chance of defections during protests."
            value={100 - controls.defectionProbability * 100 * 10}
            onChange={(value) => updateControl('defectionProbability', (100 - value) / 1000)}
            min={0}
            max={100}
            step={1}
            unit="%"
            lowLabel="Fragile"
            highLabel="Rock Solid"
            ariaLabel="Security force loyalty percentage"
          />

          <ConfidenceSlider
            label="Protest Momentum"
            description="How quickly are protests growing and spreading? Higher values simulate faster mobilization and coordination between protest groups."
            value={Math.round((controls.protestGrowthFactor - 1) * 100)}
            onChange={(value) => updateControl('protestGrowthFactor', 1 + value / 100)}
            min={0}
            max={100}
            step={5}
            unit="%"
            lowLabel="Stalled"
            highLabel="Explosive"
            ariaLabel="Protest momentum percentage"
          />
        </div>
      </div>

      {/* Confidence */}
      <div className="space-y-3">
        <h3 className="text-caption uppercase tracking-wider text-war-room-muted font-medium">
          Analyst Settings
        </h3>
        <ConfidenceSlider
          label="Intel Confidence"
          description="How confident are analysts in the underlying data quality? Lower confidence widens uncertainty bands in the simulation."
          value={controls.analystConfidence}
          onChange={(value) => updateControl('analystConfidence', value)}
          min={0}
          max={100}
          unit="%"
          lowLabel="Low"
          highLabel="High"
          ariaLabel="Analyst confidence percentage"
        />
      </div>

      <div className="pt-4 border-t border-war-room-border">
        <div className="text-caption text-war-room-muted space-y-1">
          <p>
            <span className="text-war-room-text-secondary">Monte Carlo Runs:</span>{' '}
            <span className="font-mono">{controls.runs.toLocaleString()}</span>
          </p>
          <p className="text-[10px] leading-relaxed text-war-room-muted/70 mt-2">
            Each simulation runs {controls.runs.toLocaleString()} scenarios to calculate outcome
            probabilities.
          </p>
        </div>
      </div>
    </div>
  );
}
