import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ControlPanel } from '../../src/components/controls/ControlPanel';
import { useSimulationStore, initialControls } from '../../src/store/simulationStore';
import { mockResults } from '../../src/data/mockData';

describe('ControlPanel', () => {
  beforeEach(() => {
    // Reset the store before each test
    useSimulationStore.setState({
      controls: { ...initialControls },
      results: mockResults,
      isLoading: false,
      error: null,
      runCount: 0,
    });
  });

  it('renders all sliders', () => {
    render(<ControlPanel />);

    expect(screen.getByLabelText(/analyst confidence/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/defection probability/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/protest growth factor/i)).toBeInTheDocument();
  });

  it('renders run simulation button', () => {
    render(<ControlPanel />);

    expect(screen.getByRole('button', { name: /run simulation/i })).toBeInTheDocument();
  });

  it('updates confidence slider value', () => {
    render(<ControlPanel />);

    const slider = screen.getByLabelText(/analyst confidence/i);
    fireEvent.change(slider, { target: { value: '85' } });

    expect(useSimulationStore.getState().controls.analystConfidence).toBe(85);
  });

  it('updates defection probability slider value', () => {
    render(<ControlPanel />);

    const slider = screen.getByLabelText(/defection probability/i);
    fireEvent.change(slider, { target: { value: '10' } });

    expect(useSimulationStore.getState().controls.defectionProbability).toBeCloseTo(0.1);
  });

  it('calls runSimulation on button click', async () => {
    const runSimulation = vi.fn();
    useSimulationStore.setState({ runSimulation });

    render(<ControlPanel />);

    const button = screen.getByRole('button', { name: /run simulation/i });
    fireEvent.click(button);

    expect(runSimulation).toHaveBeenCalled();
  });

  it('shows loading state when simulation running', () => {
    useSimulationStore.setState({ isLoading: true });

    render(<ControlPanel />);

    expect(screen.getByRole('button')).toBeDisabled();
    expect(screen.getByText(/running/i)).toBeInTheDocument();
  });
});
