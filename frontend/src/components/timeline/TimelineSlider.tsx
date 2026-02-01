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

  const ticks = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90];
  const progress = (day / 90) * 100;

  return (
    <div data-testid="timeline-slider" className="space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-caption text-war-room-text-secondary uppercase tracking-wider">
          Timeline
        </span>
        <div className="flex items-center gap-2">
          <span className="text-mono font-mono text-war-room-accent font-bold">{formatDay(day)}</span>
          {day > 0 && (
            <div
              className="h-1.5 w-16 bg-war-room-border rounded-full overflow-hidden"
              aria-hidden="true"
            >
              <div
                className="h-full bg-war-room-accent rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}
        </div>
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

        <div className="flex justify-between mt-1 px-0.5">
          {ticks.map((tick) => (
            <div key={tick} className="flex flex-col items-center">
              <div
                className={`w-px h-2 ${
                  tick === day ? 'bg-war-room-accent' : 'bg-war-room-border'
                }`}
              />
              <span
                className={`text-[10px] mt-0.5 ${
                  tick === day
                    ? 'text-war-room-accent font-medium'
                    : 'text-war-room-muted'
                }`}
              >
                {tick}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex justify-between text-caption text-war-room-muted">
        <span>Simulation Start</span>
        <span>Day 90</span>
      </div>
    </div>
  );
}
