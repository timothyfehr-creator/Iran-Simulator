import { Info } from 'lucide-react';
import { useState } from 'react';

interface ConfidenceSliderProps {
  value: number;
  onChange: (value: number) => void;
  label: string;
  description?: string;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  ariaLabel?: string;
  lowLabel?: string;
  highLabel?: string;
}

export function ConfidenceSlider({
  value,
  onChange,
  label,
  description,
  min = 0,
  max = 100,
  step = 1,
  unit = '%',
  ariaLabel,
  lowLabel,
  highLabel,
}: ConfidenceSliderProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(parseFloat(e.target.value));
  };

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-1.5">
          <label className="text-body text-war-room-text-primary font-medium" htmlFor={`slider-${label}`}>
            {label}
          </label>
          {description && (
            <div className="relative">
              <button
                type="button"
                className="text-war-room-muted hover:text-war-room-text-secondary transition-colors p-0.5 min-w-[28px] min-h-[28px] flex items-center justify-center"
                onMouseEnter={() => setShowTooltip(true)}
                onMouseLeave={() => setShowTooltip(false)}
                onClick={() => setShowTooltip(!showTooltip)}
                aria-label={`Info about ${label}`}
              >
                <Info className="w-3.5 h-3.5" />
              </button>
              {showTooltip && (
                <div className="absolute left-0 bottom-full mb-2 w-56 p-3 panel-elevated border border-war-room-border z-50">
                  <p className="text-caption text-war-room-text-secondary leading-relaxed">{description}</p>
                </div>
              )}
            </div>
          )}
        </div>
        <span className="text-mono font-mono text-war-room-accent font-bold">
          {value}
          {unit}
        </span>
      </div>
      <input
        id={`slider-${label}`}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={handleChange}
        className="slider-input"
        aria-label={ariaLabel || label}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value}
      />
      <div className="flex justify-between text-caption text-war-room-muted">
        <span>{lowLabel || `${min}${unit}`}</span>
        <span>{highLabel || `${max}${unit}`}</span>
      </div>
    </div>
  );
}
