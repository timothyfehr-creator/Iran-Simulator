import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { useSimulationStore } from '../../store/simulationStore';
import { outcomeLabels, outcomeColors } from '../../data/mockData';
import { formatPercent } from '../../utils/formatters';
import { EmptyState } from '../ui/EmptyState';
import { Skeleton } from '../ui/Skeleton';
import { BarChart3 } from 'lucide-react';

interface ChartData {
  name: string;
  probability: number;
  color: string;
  fullName: string;
}

export function OutcomeChart() {
  const results = useSimulationStore((state) => state.results);
  const isLoading = useSimulationStore((state) => state.isLoading);

  if (isLoading && !results) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex items-center gap-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-6 flex-1" />
          </div>
        ))}
      </div>
    );
  }

  if (!results) {
    return (
      <EmptyState
        icon={<BarChart3 className="w-8 h-8" />}
        title="No data available"
        description="Run a simulation to see outcome distribution."
      />
    );
  }

  const data: ChartData[] = Object.entries(results.outcome_distribution)
    .map(([key, value]) => ({
      name: key.replace(/_/g, ' ').slice(0, 15) + (key.length > 15 ? '...' : ''),
      fullName: outcomeLabels[key] || key,
      probability: value.probability * 100,
      color: outcomeColors[key] || '#6b7280',
    }))
    .sort((a, b) => b.probability - a.probability);

  return (
    <div className="h-[300px] lg:h-[400px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
        >
          <XAxis
            type="number"
            domain={[0, 100]}
            tickFormatter={(value) => `${value}%`}
            stroke="#6b7280"
            fontSize={12}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={100}
            stroke="#6b7280"
            fontSize={10}
            tick={{ fill: '#9ca3af' }}
          />
          <Tooltip
            content={({ payload }) => {
              if (!payload || payload.length === 0) return null;
              const item = payload[0].payload as ChartData;
              return (
                <div className="panel-elevated border border-war-room-border p-3">
                  <p className="text-war-room-text-primary font-medium text-body">{item.fullName}</p>
                  <p className="text-war-room-accent font-mono text-lg">
                    {formatPercent(item.probability / 100)}
                  </p>
                </div>
              );
            }}
          />
          <Bar dataKey="probability" radius={[0, 4, 4, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
