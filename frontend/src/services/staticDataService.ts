/**
 * Static data service for fetching public JSON artifacts from R2.
 *
 * Configure VITE_DATA_BASE_URL in .env.local to point to your R2 bucket.
 * Falls back to /latest for local development.
 */

import type { WarRoomSummary, LiveWireState, Leaderboard } from '../types/publicData';

const BASE = import.meta.env.VITE_DATA_BASE_URL || '/latest';

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}/${path}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch ${path}: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function fetchWarRoomSummary(): Promise<WarRoomSummary> {
  return fetchJson<WarRoomSummary>('war_room_summary.json');
}

export async function fetchLiveWireState(): Promise<LiveWireState> {
  return fetchJson<LiveWireState>('live_wire_state.json');
}

export async function fetchLeaderboard(): Promise<Leaderboard> {
  return fetchJson<Leaderboard>('leaderboard.json');
}
