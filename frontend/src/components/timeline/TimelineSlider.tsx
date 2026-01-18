import { useSimulationStore } from '../../store/simulationStore';
import { formatDay } from '../../utils/formatters';

interface TimelineSliderProps {
  currentDay?: number;
  onDayChange?: (day: number) => void;
}

export function TimelineSlider({ currentDay, onDayChange }: TimelineSliderProps) {
  const { controls, setTimelineDay } = useSimulationStore();

  const day = currentDay ?? controls.timelineDay;
  const handleChange = onDayChange ?? setTimelineDay;

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleChange(parseInt(e.target.value, 10));
  };

  // Generate tick marks every 10 days
  const ticks = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90];

  return (
    <div data-testid="timeline-slider" className="space-y-3">
      <div className="flex justify-between items-center">
        <span className="text-sm text-gray-400 uppercase tracking-wider">Timeline</span>
        <span className="text-sm font-mono text-war-room-accent">{formatDay(day)}</span>
      </div>

      <div className="relative">
        <input
          type="range"
          min={0}
          max={90}
          step={1}
          value={day}
          onChange={handleSliderChange}
          className="slider-input w-full"
          aria-label="Timeline day selector"
          aria-valuemin={0}
          aria-valuemax={90}
          aria-valuenow={day}
        />

        {/* Tick marks */}
        <div className="flex justify-between mt-1 px-1">
          {ticks.map((tick) => (
            <div key={tick} className="flex flex-col items-center">
              <div className="w-px h-2 bg-war-room-border" />
              <span className="text-xs text-gray-600 mt-1">{tick}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex justify-between text-xs text-gray-500">
        <span>Simulation Start</span>
        <span>Day 90</span>
      </div>
    </div>
  );
}
