import { motion } from 'framer-motion';
import type { StressLevel } from '../../types/simulation';
import { getStatusClass } from '../../utils/colors';

interface DefconWidgetProps {
  status: StressLevel;
  label: string;
}

const statusLabels: Record<StressLevel, string> = {
  stable: 'STABLE',
  pressured: 'PRESSURED',
  critical: 'CRITICAL',
};

export function DefconWidget({ status, label }: DefconWidgetProps) {
  const isCritical = status === 'critical';

  return (
    <motion.div
      data-testid="defcon-widget"
      role="status"
      aria-live="polite"
      aria-label={`${label}: ${statusLabels[status]}`}
      className={`
        px-4 py-2 rounded-lg font-mono text-sm uppercase tracking-wider
        ${getStatusClass(status)}
        ${isCritical ? 'text-war-room-danger' : ''}
      `}
      initial={{ scale: 1 }}
      animate={
        isCritical
          ? {
              scale: [1, 1.02, 1],
            }
          : {}
      }
      transition={
        isCritical
          ? {
              duration: 2,
              repeat: Infinity,
              ease: 'easeInOut',
            }
          : {}
      }
    >
      <span className="font-bold">{label}:</span>{' '}
      <span className="font-extrabold">{statusLabels[status]}</span>
    </motion.div>
  );
}
