/** TypeScript interfaces for public JSON artifacts served from R2. */

export type DefconLevel = 'GREEN' | 'YELLOW' | 'ORANGE' | 'RED' | 'UNKNOWN';

export interface HeadlineKpi {
  label: string;
  value: number | string | null;
  format?: string;
  units?: string;
}

export interface ChartPoint {
  date: string;
  rial_usd_rate: number | null;
  connectivity_index: number | null;
}

export interface Alert {
  type: string;
  signal?: string;
  consecutive_failures?: number;
  message: string;
}

export interface ForecastSummary {
  brier_score: number | null;
  calibration_error: number | null;
  total_forecasts: number;
}

export interface DerivedStates {
  economic_stress: string | null;
  internet_status: string | null;
  news_activity: string | null;
}

export interface WarRoomSummary {
  _schema_version: string;
  generated_at_utc: string;
  defcon_status: DefconLevel;
  headline_kpis: HeadlineKpi[];
  headline_chart: ChartPoint[];
  live_wire_summary: DerivedStates | null;
  forecast_summary: ForecastSummary | null;
  alerts: Alert[];
  map_data: { regions: unknown[] };
}

// Signal quality
export interface SignalQuality {
  status: 'OK' | 'STALE' | 'FAILED';
  value: number | null;
  fetched_at_utc: string;
  source_timestamp_utc: string | null;
  freshness: 'source_verified' | 'fetch_time_only';
  confidence: 'high' | 'medium' | 'low';
  last_good_value: number | null;
  last_good_at: string | null;
  consecutive_failures: number;
}

export interface SignalData {
  value: number | null;
  units: string;
  source: string;
  avg_tone?: null;
}

export interface HysteresisState {
  confirmed_state: string | null;
  pending_state: string | null;
  pending_count: number;
}

export interface LiveWireState {
  _schema_version: string;
  rule_version: string;
  snapshot_id: string;
  generated_at_utc: string;
  signals: Record<string, SignalData>;
  signal_quality: Record<string, SignalQuality>;
  smoothed: Record<string, number | null>;
  derived_states: DerivedStates;
  hysteresis: Record<string, HysteresisState>;
}

// Leaderboard
export interface TopForecaster {
  forecaster_id: string;
  primary_brier: number | null;
  skill_score: number | null;
  resolved_n: number;
}

export interface QuestionGroup {
  event_type: string;
  horizon_days: number;
  avg_brier: number | null;
  forecaster_count: number;
}

export interface Leaderboard {
  _schema_version: string;
  generated_at_utc: string;
  metrics: { primary: string };
  top_forecasters: TopForecaster[];
  question_groups: QuestionGroup[];
}
