import { create } from 'zustand';
import type { SimulationResults, SimulationControls } from '../types/simulation';
import { api } from '../services';
import { mockResults } from '../data/mockData';

export const initialControls: SimulationControls = {
  timelineDay: 0,
  analystConfidence: 70,
  runs: 10000,
  defectionProbability: 0.05,
  protestGrowthFactor: 1.5,
};

interface SimulationStore {
  controls: SimulationControls;
  results: SimulationResults | null;
  isLoading: boolean;
  error: string | null;
  runCount: number;
  lastRunTime: Date | null;
  lastRunDuration: number | null;

  // Actions
  setTimelineDay: (day: number) => void;
  updateControl: <K extends keyof SimulationControls>(
    key: K,
    value: SimulationControls[K]
  ) => void;
  runSimulation: () => Promise<void>;
  loadResults: () => Promise<void>;
  resetControls: () => void;
}

export const useSimulationStore = create<SimulationStore>((set, get) => ({
  controls: initialControls,
  results: mockResults, // Initialize with mock data
  isLoading: false,
  error: null,
  runCount: 0,
  lastRunTime: null,
  lastRunDuration: null,

  setTimelineDay: (day: number) => {
    set((state) => ({
      controls: { ...state.controls, timelineDay: day },
    }));
  },

  updateControl: (key, value) => {
    set((state) => ({
      controls: { ...state.controls, [key]: value },
    }));
  },

  runSimulation: async () => {
    const { controls } = get();
    set({ isLoading: true, error: null });

    const startTime = Date.now();

    try {
      const results = await api.runSimulation({
        runs: controls.runs,
        defectionProbability: controls.defectionProbability,
        protestGrowthFactor: controls.protestGrowthFactor,
      });

      const duration = Date.now() - startTime;

      set((state) => ({
        results,
        isLoading: false,
        runCount: state.runCount + 1,
        lastRunTime: new Date(),
        lastRunDuration: duration,
      }));
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Simulation failed',
        isLoading: false,
      });
    }
  },

  loadResults: async () => {
    set({ isLoading: true, error: null });

    try {
      const results = await api.getResults();
      set({ results, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load results',
        isLoading: false,
      });
    }
  },

  resetControls: () => {
    set({ controls: initialControls });
  },
}));
