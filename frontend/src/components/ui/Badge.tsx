import type { ReactNode } from 'react';

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

interface BadgeProps {
  variant: BadgeVariant;
  children: ReactNode;
}

const variantStyles: Record<BadgeVariant, string> = {
  success: 'bg-war-room-success/20 text-war-room-success',
  warning: 'bg-war-room-warning/20 text-war-room-warning',
  danger: 'bg-war-room-danger/20 text-war-room-danger',
  info: 'bg-war-room-accent/20 text-war-room-accent',
  neutral: 'bg-war-room-border text-war-room-text-secondary',
};

export function Badge({ variant, children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-lg text-caption font-medium uppercase tracking-wider ${variantStyles[variant]}`}
    >
      {children}
    </span>
  );
}
