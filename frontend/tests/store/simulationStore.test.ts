import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useSimulationStore, initialControls } from '../../src/store/simulationStore';
import { mockResults } from '../../src/data/mockData';

describe('simulationStore', () => {
  beforeEach(() => {
    useSimulationStore.setState({
      controls: { ...initialControls },
      results: mockResults,
      isLoading: false,
      error: null,
      runCount: 0,
    });
  });

  it('has correct initial state', () => {
    const state = useSimulationStore.getState();

    expect(state.controls).toEqual(initialControls);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
    expect(state.runCount).toBe(0);
  });

  it('updates timeline day', () => {
    const { setTimelineDay } = useSimulationStore.getState();
    setTimelineDay(45);

    expect(useSimulationStore.getState().controls.timelineDay).toBe(45);
  });

  it('updates control values', () => {
    const { updateControl } = useSimulationStore.getState();
    updateControl('analystConfidence', 85);

    expect(useSimulationStore.getState().controls.analystConfidence).toBe(85);
  });

  it('updates multiple controls independently', () => {
    const { updateControl } = useSimulationStore.getState();

    updateControl('analystConfidence', 90);
    updateControl('defectionProbability', 0.1);
    updateControl('protestGrowthFactor', 1.8);

    const { controls } = useSimulationStore.getState();
    expect(controls.analystConfidence).toBe(90);
    expect(controls.defectionProbability).toBe(0.1);
    expect(controls.protestGrowthFactor).toBe(1.8);
  });

  it('resets controls to initial values', () => {
    const { updateControl, resetControls } = useSimulationStore.getState();

    updateControl('analystConfidence', 99);
    updateControl('timelineDay', 50);

    resetControls();

    const { controls } = useSimulationStore.getState();
    expect(controls.analystConfidence).toBe(initialControls.analystConfidence);
    expect(controls.timelineDay).toBe(initialControls.timelineDay);
  });

  it('sets loading state during simulation', async () => {
    const { runSimulation } = useSimulationStore.getState();

    // Start the simulation (don't await it yet)
    const simulationPromise = runSimulation();

    // Check that loading is true
    expect(useSimulationStore.getState().isLoading).toBe(true);

    // Wait for simulation to complete
    await simulationPromise;

    // Check that loading is false after completion
    expect(useSimulationStore.getState().isLoading).toBe(false);
  });

  it('increments run count after simulation', async () => {
    const initialRunCount = useSimulationStore.getState().runCount;
    const { runSimulation } = useSimulationStore.getState();

    await runSimulation();

    expect(useSimulationStore.getState().runCount).toBe(initialRunCount + 1);
  });
});
