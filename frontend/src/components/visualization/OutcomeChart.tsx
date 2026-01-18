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

interface ChartData {
  name: string;
  probability: number;
  color: string;
  fullName: string;
}

export function OutcomeChart() {
  const results = useSimulationStore((state) => state.results);

  if (!results) {
    return (
      <div className="flex items-center justify-center min-h-[300px] text-gray-500">
        No simulation data available
      </div>
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
                <div className="bg-war-room-panel border border-war-room-border rounded-lg p-3 shadow-lg">
                  <p className="text-white font-medium text-sm">{item.fullName}</p>
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
