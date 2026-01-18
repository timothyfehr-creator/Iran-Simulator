import type { SimulationApi, SimulationResults, SimulationParams, SystemStatus } from '../types/simulation';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const realApi: SimulationApi = {
  async getResults(): Promise<SimulationResults> {
    const res = await fetch(`${API_BASE}/api/results`);
    if (!res.ok) {
      throw new Error(`Failed to fetch results: ${res.status}`);
    }
    return res.json();
  },

  async runSimulation(params: SimulationParams): Promise<SimulationResults> {
    const res = await fetch(`${API_BASE}/api/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!res.ok) {
      throw new Error(`Failed to run simulation: ${res.status}`);
    }
    return res.json();
  },

  async getStatus(): Promise<SystemStatus> {
    const res = await fetch(`${API_BASE}/api/status`);
    if (!res.ok) {
      throw new Error(`Failed to get status: ${res.status}`);
    }
    return res.json();
  },
};
