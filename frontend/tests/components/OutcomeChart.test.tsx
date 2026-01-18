import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { OutcomeChart } from '../../src/components/visualization/OutcomeChart';
import { useSimulationStore, initialControls } from '../../src/store/simulationStore';
import { mockResults } from '../../src/data/mockData';

describe('OutcomeChart', () => {
  beforeEach(() => {
    useSimulationStore.setState({
      controls: { ...initialControls },
      results: mockResults,
      isLoading: false,
      error: null,
      runCount: 0,
    });
  });

  it('renders chart when results are available', () => {
    render(<OutcomeChart />);

    // The chart should be rendered (Recharts creates SVG elements)
    const container = document.querySelector('.recharts-responsive-container');
    expect(container).toBeInTheDocument();
  });

  it('shows message when no results available', () => {
    useSimulationStore.setState({ results: null });

    render(<OutcomeChart />);

    expect(screen.getByText(/no simulation data available/i)).toBeInTheDocument();
  });
});
