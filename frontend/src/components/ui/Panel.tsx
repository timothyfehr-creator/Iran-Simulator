import type { ReactNode } from 'react';

interface PanelProps {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  accent?: 'blue' | 'yellow' | 'red';
}

export function Panel({ title, action, children, className = '', accent }: PanelProps) {
  const accentBorder = accent === 'blue'
    ? 'border-l-4 border-l-war-room-accent'
    : accent === 'yellow'
    ? 'border-l-4 border-l-war-room-warning'
    : accent === 'red'
    ? 'border-l-4 border-l-war-room-danger'
    : '';

  return (
    <div className={`panel p-5 space-y-3 ${accentBorder} ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between">
          {title && (
            <h3 className="text-heading uppercase tracking-wider text-war-room-text-secondary">
              {title}
            </h3>
          )}
          {action && <div className="flex-shrink-0">{action}</div>}
        </div>
      )}
      <div>{children}</div>
    </div>
  );
}
