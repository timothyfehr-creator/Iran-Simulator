import type { ReactNode } from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-6 text-center">
      <div className="text-war-room-muted mb-4">
        {icon || <Inbox className="w-10 h-10" />}
      </div>
      <h3 className="text-heading text-war-room-text-primary mb-1">{title}</h3>
      {description && (
        <p className="text-body text-war-room-text-secondary max-w-sm">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
