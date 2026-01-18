import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DefconWidget } from '../../src/components/status/DefconWidget';

describe('DefconWidget', () => {
  it('renders with stable status (green)', () => {
    render(<DefconWidget status="stable" label="REGIME STABILITY" />);

    expect(screen.getByText(/REGIME STABILITY:/)).toBeInTheDocument();
    expect(screen.getByText('STABLE')).toBeInTheDocument();
    expect(screen.getByTestId('defcon-widget')).toHaveClass('status-stable');
  });

  it('renders with pressured status (amber)', () => {
    render(<DefconWidget status="pressured" label="REGIME STABILITY" />);

    expect(screen.getByText('PRESSURED')).toBeInTheDocument();
    expect(screen.getByTestId('defcon-widget')).toHaveClass('status-pressured');
  });

  it('renders with critical status (red)', () => {
    render(<DefconWidget status="critical" label="REGIME STABILITY" />);

    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
    expect(screen.getByTestId('defcon-widget')).toHaveClass('status-critical');
  });

  it('is accessible with proper ARIA attributes', () => {
    render(<DefconWidget status="critical" label="REGIME STABILITY" />);

    const widget = screen.getByRole('status');
    expect(widget).toHaveAttribute('aria-live', 'polite');
    expect(widget).toHaveAttribute('aria-label', 'REGIME STABILITY: CRITICAL');
  });

  it('displays the correct label', () => {
    render(<DefconWidget status="stable" label="TEST LABEL" />);

    expect(screen.getByText(/TEST LABEL:/)).toBeInTheDocument();
  });
});
