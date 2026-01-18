import { mockApi } from './mockApi';
import { realApi } from './realApi';
import { causalApi } from './causalApi';
import type { SimulationApi } from './api';

// Switch between mock and real API based on environment variable
export const api: SimulationApi =
  import.meta.env.VITE_USE_REAL_API === 'true' ? realApi : mockApi;

// Causal API is always real (no mock implementation)
export { causalApi };

export type { SimulationApi };
