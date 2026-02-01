import { mockApi } from './mockApi';
import { realApi } from './realApi';
import { causalApi } from './causalApi';
import type { SimulationApi } from './api';

// Wraps the real API with automatic fallback to mock if backend is unreachable
function createFallbackApi(): SimulationApi {
  let useMock = import.meta.env.VITE_USE_REAL_API !== 'true';

  async function tryReal<T>(realFn: () => Promise<T>, mockFn: () => Promise<T>): Promise<T> {
    if (useMock) return mockFn();
    try {
      return await realFn();
    } catch {
      useMock = true;
      console.warn('[SimulationApi] Backend not available, falling back to mock data');
      return mockFn();
    }
  }

  return {
    getResults: () => tryReal(() => realApi.getResults(), () => mockApi.getResults()),
    runSimulation: (params) => tryReal(() => realApi.runSimulation(params), () => mockApi.runSimulation(params)),
    getStatus: () => tryReal(() => realApi.getStatus(), () => mockApi.getStatus()),
  };
}

export const api: SimulationApi = createFallbackApi();

export { causalApi };
export type { SimulationApi };
