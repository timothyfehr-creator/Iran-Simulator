import { useState } from 'react';
import { RegionalMap } from '../visualization/RegionalMap';
import { OutcomeChart } from '../visualization/OutcomeChart';
import { ExecutiveSummary } from '../visualization/ExecutiveSummary';
import { CausalExplorer } from '../visualization/CausalExplorer';
import { ErrorBoundary } from './ErrorBoundary';
import { Panel } from '../ui/Panel';
import { BarChart3, FileText, Map, Network } from 'lucide-react';
import { useSimulationStore } from '../../store/simulationStore';

type TabId = 'summary' | 'charts' | 'map' | 'causal';

interface Tab {
  id: TabId;
  label: string;
  icon: React.ReactNode;
}

const tabs: Tab[] = [
  { id: 'summary', label: 'Executive Summary', icon: <FileText className="w-4 h-4" /> },
  { id: 'charts', label: 'Analysis', icon: <BarChart3 className="w-4 h-4" /> },
  { id: 'map', label: 'Regional Map', icon: <Map className="w-4 h-4" /> },
  { id: 'causal', label: 'Causal Explorer', icon: <Network className="w-4 h-4" /> },
];

export function MainView() {
  const [activeTab, setActiveTab] = useState<TabId>('summary');

  return (
    <main className="flex-1 flex flex-col overflow-hidden">
      {/* Tab Navigation */}
      <div className="flex border-b border-war-room-border bg-war-room-panel px-5">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`
              flex items-center gap-2 px-4 py-3 text-body font-medium transition-colors
              border-b-2 -mb-px min-h-[44px]
              focus-visible:ring-2 focus-visible:ring-war-room-accent focus-visible:ring-offset-2 focus-visible:ring-offset-war-room-panel focus-visible:outline-none
              ${
                activeTab === tab.id
                  ? 'text-war-room-accent border-war-room-accent'
                  : 'text-war-room-text-secondary border-transparent hover:text-war-room-text-primary hover:border-war-room-border'
              }
            `}
          >
            {tab.icon}
            <span className="hidden sm:inline">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-4">
        <div className="max-w-6xl mx-auto space-y-4">
          <ErrorBoundary>
            {activeTab === 'summary' && <ExecutiveSummary />}

            {activeTab === 'charts' && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Panel title="Outcome Distribution">
                  <OutcomeChart />
                </Panel>

                <Panel title="Key Metrics">
                  <KeyMetricsPanel />
                </Panel>
              </div>
            )}

            {activeTab === 'map' && <RegionalMap />}

            {activeTab === 'causal' && <CausalExplorer />}
          </ErrorBoundary>
        </div>
      </div>
    </main>
  );
}

function KeyMetricsPanel() {
  const results = useSimulationStore((state) => state.results);

  if (!results) {
    return <div className="text-war-room-muted text-body">No data available</div>;
  }

  const metrics = [
    {
      label: 'Economic Stress Level',
      value: results.economic_analysis.stress_level.toUpperCase(),
      color:
        results.economic_analysis.stress_level === 'critical'
          ? 'text-war-room-danger'
          : results.economic_analysis.stress_level === 'pressured'
          ? 'text-war-room-warning'
          : 'text-war-room-success',
    },
    {
      label: 'Rial Exchange Rate',
      value: `${results.economic_analysis.rial_rate_used.toLocaleString()} IRR/USD`,
      color: 'text-war-room-text-primary',
    },
    {
      label: 'Inflation Rate',
      value: `${results.economic_analysis.inflation_used}%`,
      color: 'text-war-room-text-primary',
    },
    {
      label: 'Security Defection Rate',
      value: `${(results.key_event_rates.security_force_defection * 100).toFixed(1)}%`,
      color: 'text-war-room-text-primary',
    },
    {
      label: 'Ethnic Uprising Rate',
      value: `${(results.key_event_rates.ethnic_uprising * 100).toFixed(1)}%`,
      color: 'text-war-room-text-primary',
    },
  ];

  return (
    <div className="space-y-3">
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="flex items-center justify-between p-3 bg-war-room-bg/50 rounded-lg"
        >
          <span className="text-body text-war-room-text-secondary">{metric.label}</span>
          <span className={`font-mono font-medium ${metric.color}`}>{metric.value}</span>
        </div>
      ))}
    </div>
  );
}
