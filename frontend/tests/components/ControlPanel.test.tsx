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

    // New slider labels (using aria-label)
    expect(screen.getByLabelText(/security force loyalty percentage/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/protest momentum percentage/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/analyst confidence percentage/i)).toBeInTheDocument();
  });

  it('renders run simulation button', () => {
    render(<ControlPanel />);

    expect(screen.getByRole('button', { name: /run simulation/i })).toBeInTheDocument();
  });

  it('updates security force loyalty slider value', () => {
    render(<ControlPanel />);

    const slider = screen.getByLabelText(/security force loyalty percentage/i);
    fireEvent.change(slider, { target: { value: '30' } });

    // Security force loyalty maps to defectionProbability: (100 - value) / 1000
    // At 30% loyalty, defection = (100 - 30) / 1000 = 0.07
    expect(useSimulationStore.getState().controls.defectionProbability).toBeCloseTo(0.07, 2);
  });

  it('updates protest momentum slider value', () => {
    render(<ControlPanel />);

    const slider = screen.getByLabelText(/protest momentum percentage/i);
    fireEvent.change(slider, { target: { value: '80' } });

    // Protest momentum maps to protestGrowthFactor: 1 + (value/100)
    // At 80%, growth factor = 1 + (80/100) = 1.8
    expect(useSimulationStore.getState().controls.protestGrowthFactor).toBeCloseTo(1.8, 1);
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

    // Find the run simulation button specifically (not info buttons)
    const runButton = screen.getByRole('button', { name: /running simulation/i });
    expect(runButton).toBeDisabled();
    expect(screen.getByText(/running/i)).toBeInTheDocument();
  });
});
