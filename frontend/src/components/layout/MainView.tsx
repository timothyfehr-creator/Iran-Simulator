import { useState } from 'react';
import { RegionalMap } from '../visualization/RegionalMap';
import { OutcomeChart } from '../visualization/OutcomeChart';
import { ExecutiveSummary } from '../visualization/ExecutiveSummary';
import { CausalExplorer } from '../visualization/CausalExplorer';
import { ErrorBoundary } from './ErrorBoundary';
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
      <div className="flex border-b border-war-room-border bg-war-room-panel px-4">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`
              flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors
              border-b-2 -mb-px
              ${
                activeTab === tab.id
                  ? 'text-war-room-accent border-war-room-accent'
                  : 'text-gray-400 border-transparent hover:text-gray-200 hover:border-gray-600'
              }
            `}
          >
            {tab.icon}
            <span className="hidden sm:inline">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-6">
        <ErrorBoundary>
          {activeTab === 'summary' && <ExecutiveSummary />}

          {activeTab === 'charts' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="panel p-4">
                <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-4">
                  Outcome Distribution
                </h2>
                <OutcomeChart />
              </div>

              <div className="panel p-4">
                <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-4">
                  Key Metrics
                </h2>
                <KeyMetricsPanel />
              </div>
            </div>
          )}

          {activeTab === 'map' && <RegionalMap />}

          {activeTab === 'causal' && (
            <CausalExplorer />
          )}
        </ErrorBoundary>
      </div>
    </main>
  );
}

function KeyMetricsPanel() {
  const results = useSimulationStore((state) => state.results);

  if (!results) {
    return <div className="text-gray-500">No data available</div>;
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
      color: 'text-gray-300',
    },
    {
      label: 'Inflation Rate',
      value: `${results.economic_analysis.inflation_used}%`,
      color: 'text-gray-300',
    },
    {
      label: 'Security Defection Rate',
      value: `${(results.key_event_rates.security_force_defection * 100).toFixed(1)}%`,
      color: 'text-gray-300',
    },
    {
      label: 'Ethnic Uprising Rate',
      value: `${(results.key_event_rates.ethnic_uprising * 100).toFixed(1)}%`,
      color: 'text-gray-300',
    },
  ];

  return (
    <div className="space-y-4">
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="flex items-center justify-between p-3 bg-war-room-bg/50 rounded-lg"
        >
          <span className="text-sm text-gray-400">{metric.label}</span>
          <span className={`font-mono font-medium ${metric.color}`}>{metric.value}</span>
        </div>
      ))}
    </div>
  );
}
