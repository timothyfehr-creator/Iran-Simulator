import { motion } from 'framer-motion';
import type { StressLevel } from '../../types/simulation';
import { Badge } from '../ui/Badge';

interface DefconWidgetProps {
  status: StressLevel;
  label: string;
}

const statusLabels: Record<StressLevel, string> = {
  stable: 'STABLE',
  pressured: 'PRESSURED',
  critical: 'CRITICAL',
};

const statusVariants: Record<StressLevel, 'success' | 'warning' | 'danger'> = {
  stable: 'success',
  pressured: 'warning',
  critical: 'danger',
};

export function DefconWidget({ status, label }: DefconWidgetProps) {
  const isCritical = status === 'critical';

  return (
    <motion.div
      data-testid="defcon-widget"
      role="status"
      aria-live="polite"
      aria-label={`${label}: ${statusLabels[status]}`}
      className="flex items-center gap-2"
      initial={{ scale: 1 }}
      animate={
        isCritical
          ? { scale: [1, 1.02, 1] }
          : {}
      }
      transition={
        isCritical
          ? { duration: 2, repeat: Infinity, ease: 'easeInOut' }
          : {}
      }
    >
      <span className="text-caption text-war-room-muted uppercase tracking-wider font-medium hidden sm:inline">
        {label}
      </span>
      <Badge variant={statusVariants[status]}>{statusLabels[status]}</Badge>
    </motion.div>
  );
}
