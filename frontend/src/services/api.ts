import type { SimulationResults, SimulationParams, SystemStatus } from '../types/simulation';

export interface SimulationApi {
  getResults(): Promise<SimulationResults>;
  runSimulation(params: SimulationParams): Promise<SimulationResults>;
  getStatus(): Promise<SystemStatus>;
}
