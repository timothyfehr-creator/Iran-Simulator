import type { StressLevel } from '../types/simulation';

export const WAR_ROOM_COLORS = {
  bg: '#0a0f1c',
  panel: '#111827',
  surface: '#1a2332',
  border: '#1f2937',
  accent: '#3b82f6',
  danger: '#ef4444',
  warning: '#f59e0b',
  success: '#10b981',
  muted: '#6b7280',
  textPrimary: '#f3f4f6',
  textSecondary: '#9ca3af',
} as const;

export const STATUS_COLORS: Record<StressLevel, string> = {
  stable: WAR_ROOM_COLORS.success,
  pressured: WAR_ROOM_COLORS.warning,
  critical: WAR_ROOM_COLORS.danger,
};

export const STATUS_TEXT_COLORS: Record<StressLevel, string> = {
  stable: '#ffffff',
  pressured: '#000000',
  critical: '#ffffff',
};

export function getStatusColor(status: StressLevel): string {
  return STATUS_COLORS[status];
}

export function getStatusTextColor(status: StressLevel): string {
  return STATUS_TEXT_COLORS[status];
}

export function getStatusClass(status: StressLevel): string {
  return `status-${status}`;
}
