import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TimelineSlider } from '../../src/components/timeline/TimelineSlider';

describe('TimelineSlider', () => {
  it('renders day range 0-90', () => {
    render(<TimelineSlider currentDay={0} onDayChange={() => {}} />);

    const slider = screen.getByRole('slider');
    expect(slider).toHaveAttribute('min', '0');
    expect(slider).toHaveAttribute('max', '90');
  });

  it('calls onDayChange when slider moves', () => {
    const onChange = vi.fn();
    render(<TimelineSlider currentDay={0} onDayChange={onChange} />);

    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '45' } });

    expect(onChange).toHaveBeenCalledWith(45);
  });

  it('displays current day label', () => {
    render(<TimelineSlider currentDay={45} onDayChange={() => {}} />);

    expect(screen.getByText('Day 45')).toBeInTheDocument();
  });

  it('has proper ARIA attributes', () => {
    render(<TimelineSlider currentDay={30} onDayChange={() => {}} />);

    const slider = screen.getByRole('slider');
    expect(slider).toHaveAttribute('aria-valuemin', '0');
    expect(slider).toHaveAttribute('aria-valuemax', '90');
    expect(slider).toHaveAttribute('aria-valuenow', '30');
    expect(slider).toHaveAttribute('aria-label', 'Timeline day selector');
  });

  it('renders tick marks', () => {
    render(<TimelineSlider currentDay={0} onDayChange={() => {}} />);

    // Check for some tick mark labels
    expect(screen.getByText('0')).toBeInTheDocument();
    expect(screen.getByText('30')).toBeInTheDocument();
    expect(screen.getByText('60')).toBeInTheDocument();
    expect(screen.getByText('90')).toBeInTheDocument();
  });
});
