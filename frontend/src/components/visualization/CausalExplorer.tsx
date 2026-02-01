import { useState, useEffect, useCallback } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { causalApi } from '../../services';
import type {
  CausalGraph,
  CausalInferenceResult,
  SensitivityResult,
  CausalStatus,
} from '../../types/simulation';
import { Panel } from '../ui/Panel';
import { EmptyState } from '../ui/EmptyState';
import { Skeleton } from '../ui/Skeleton';
import { Badge } from '../ui/Badge';
import { AlertTriangle, Network, Activity, BarChart3, RefreshCw } from 'lucide-react';

const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
  Rial_Rate: { x: 50, y: 50 },
  Inflation: { x: 50, y: 120 },
  Khamenei_Health: { x: 50, y: 190 },
  US_Policy_Disposition: { x: 50, y: 260 },
  Economic_Stress: { x: 200, y: 85 },
  Protest_Escalation: { x: 350, y: 50 },
  Regime_Response: { x: 350, y: 200 },
  Internet_Status: { x: 350, y: 280 },
  Protest_Sustained: { x: 500, y: 50 },
  Protest_State: { x: 500, y: 130 },
  Security_Loyalty: { x: 500, y: 210 },
  Elite_Cohesion: { x: 500, y: 290 },
  Ethnic_Uprising: { x: 650, y: 50 },
  Fragmentation_Outcome: { x: 650, y: 120 },
  Succession_Type: { x: 650, y: 210 },
  Israel_Posture: { x: 650, y: 290 },
  Regional_Instability: { x: 800, y: 180 },
  Iraq_Stability: { x: 800, y: 260 },
  Syria_Stability: { x: 800, y: 320 },
  Russia_Posture: { x: 800, y: 100 },
  Gulf_Realignment: { x: 800, y: 50 },
  Regime_Outcome: { x: 950, y: 180 },
};

const CATEGORY_COLORS: Record<string, string> = {
  root: '#3b82f6',
  intermediate: '#8b5cf6',
  terminal: '#ef4444',
};

interface EvidenceState {
  [node: string]: string;
}

export function CausalExplorer() {
  const [status, setStatus] = useState<CausalStatus | null>(null);
  const [graph, setGraph] = useState<CausalGraph | null>(null);
  const [evidence, setEvidence] = useState<EvidenceState>({});
  const [inferenceResult, setInferenceResult] = useState<CausalInferenceResult | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityResult | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setIsLoading(true);
        const [statusRes, graphRes] = await Promise.all([
          causalApi.getStatus(),
          causalApi.getGraph(),
        ]);
        setStatus(statusRes);
        setGraph(graphRes);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load causal engine');
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, []);

  const runInference = useCallback(async () => {
    if (!graph) return;
    try {
      setIsLoading(true);
      const result = await causalApi.infer({
        evidence,
        target: 'Regime_Outcome',
        include_surprise: true,
      });
      setInferenceResult(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Inference failed');
    } finally {
      setIsLoading(false);
    }
  }, [evidence, graph]);

  const loadSensitivity = useCallback(async () => {
    try {
      setIsLoading(true);
      const result = await causalApi.getSensitivity('Regime_Outcome');
      setSensitivity(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sensitivity analysis failed');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (graph) {
      runInference();
      loadSensitivity();
    }
  }, [graph, runInference, loadSensitivity]);

  const handleEvidenceChange = (node: string, state: string | null) => {
    setEvidence((prev) => {
      const next = { ...prev };
      if (state === null) {
        delete next[node];
      } else {
        next[node] = state;
      }
      return next;
    });
  };

  const clearEvidence = () => {
    setEvidence({});
    setSelectedNode(null);
  };

  if (isLoading && !graph) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[380px] w-full" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (error && !graph) {
    return (
      <EmptyState
        icon={<AlertTriangle className="w-10 h-10 text-war-room-danger" />}
        title="Causal Engine Error"
        description={error}
      />
    );
  }

  if (!status?.available || !graph) {
    return (
      <EmptyState
        icon={<Network className="w-10 h-10" />}
        title="Causal Engine Not Available"
        description="The Bayesian network engine is not currently running."
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* Status Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-body text-war-room-text-secondary">
            <Network className="w-4 h-4" />
            <span>{status.node_count} nodes</span>
            <span className="text-war-room-border">|</span>
            <span>{status.edge_count} edges</span>
            {status.cpts_loaded && (
              <>
                <span className="text-war-room-border">|</span>
                <Badge variant="success">CPTs loaded</Badge>
              </>
            )}
          </div>
          {Object.keys(evidence).length > 0 && (
            <button
              onClick={clearEvidence}
              className="text-body text-war-room-accent hover:underline focus-visible:ring-2 focus-visible:ring-war-room-accent focus-visible:ring-offset-2 focus-visible:ring-offset-war-room-bg rounded"
            >
              Clear evidence ({Object.keys(evidence).length})
            </button>
          )}
        </div>
        <button
          onClick={runInference}
          disabled={isLoading}
          className="flex items-center gap-2 px-3 py-1.5 bg-war-room-accent/20 text-war-room-accent rounded-lg hover:bg-war-room-accent/30 transition-colors disabled:opacity-50 min-h-[36px] focus-visible:ring-2 focus-visible:ring-war-room-accent focus-visible:ring-offset-2 focus-visible:ring-offset-war-room-bg"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          Update
        </button>
      </div>

      {/* DAG Visualization */}
      <Panel title="Bayesian Network Structure">
        <div className="overflow-auto">
          <svg width="1050" height="380" className="bg-war-room-bg/50 rounded-lg">
            {graph.edges.map((edge, idx) => {
              const from = NODE_POSITIONS[edge.source];
              const to = NODE_POSITIONS[edge.target];
              if (!from || !to) return null;
              return (
                <line
                  key={idx}
                  x1={from.x + 60}
                  y1={from.y + 15}
                  x2={to.x}
                  y2={to.y + 15}
                  stroke="#4b5563"
                  strokeWidth="1"
                  markerEnd="url(#arrowhead)"
                />
              );
            })}
            <defs>
              <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#4b5563" />
              </marker>
            </defs>
            {Object.entries(graph.nodes).map(([name, states]) => {
              const pos = NODE_POSITIONS[name];
              if (!pos) return null;
              const category = graph.node_categories[name] || 'intermediate';
              const isSelected = selectedNode === name;
              const hasEvidence = name in evidence;

              return (
                <g
                  key={name}
                  transform={`translate(${pos.x}, ${pos.y})`}
                  onClick={() => setSelectedNode(isSelected ? null : name)}
                  style={{ cursor: 'pointer' }}
                >
                  <rect
                    width="120"
                    height="30"
                    rx="6"
                    fill={hasEvidence ? '#059669' : isSelected ? '#1e40af' : '#1f2937'}
                    stroke={isSelected ? CATEGORY_COLORS[category] : '#374151'}
                    strokeWidth={isSelected ? 2 : 1}
                  />
                  <text
                    x="60"
                    y="20"
                    textAnchor="middle"
                    fill={hasEvidence || isSelected ? 'white' : '#9ca3af'}
                    fontSize="10"
                    fontFamily="monospace"
                  >
                    {name.replace(/_/g, ' ').slice(0, 14)}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {selectedNode && graph.nodes[selectedNode] && (
          <div className="mt-3 p-4 bg-war-room-bg/50 rounded-lg border border-war-room-border">
            <h4 className="font-medium text-war-room-text-primary text-body mb-2">
              {selectedNode.replace(/_/g, ' ')}
            </h4>
            <p className="text-caption text-war-room-muted mb-3">
              Category: {graph.node_categories[selectedNode]}
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => handleEvidenceChange(selectedNode, null)}
                className={`px-2.5 py-1 text-caption rounded-lg min-h-[32px] focus-visible:ring-2 focus-visible:ring-war-room-accent ${
                  !(selectedNode in evidence)
                    ? 'bg-war-room-accent text-white'
                    : 'bg-war-room-border text-war-room-text-secondary hover:bg-war-room-border/80'
                }`}
              >
                No evidence
              </button>
              {graph.nodes[selectedNode].map((state) => (
                <button
                  key={state}
                  onClick={() => handleEvidenceChange(selectedNode, state)}
                  className={`px-2.5 py-1 text-caption rounded-lg min-h-[32px] focus-visible:ring-2 focus-visible:ring-war-room-accent ${
                    evidence[selectedNode] === state
                      ? 'bg-green-600 text-white'
                      : 'bg-war-room-border text-war-room-text-secondary hover:bg-war-room-border/80'
                  }`}
                >
                  {state}
                </button>
              ))}
            </div>
          </div>
        )}
      </Panel>

      {/* Results Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel
          title="Posterior P(Regime_Outcome)"
          action={<Activity className="w-4 h-4 text-war-room-accent" />}
        >
          {inferenceResult ? (
            <>
              <PosteriorChart posterior={inferenceResult.posterior} />
              {inferenceResult.surprise_flag && (
                <div className="mt-3 p-3 bg-war-room-warning/10 border border-war-room-warning/30 rounded-lg">
                  <div className="flex items-center gap-2 text-war-room-warning text-body font-medium mb-1">
                    <AlertTriangle className="w-4 h-4" />
                    Surprise detected (score: {inferenceResult.surprise_score?.toFixed(2)})
                  </div>
                  {inferenceResult.surprise_drivers && (
                    <p className="text-caption text-war-room-warning/70">
                      Key drivers: {inferenceResult.surprise_drivers.join(', ')}
                    </p>
                  )}
                </div>
              )}
            </>
          ) : (
            <EmptyState
              title="No inference results"
              description="Set evidence and click Update to run inference."
            />
          )}
        </Panel>

        <Panel
          title="Sensitivity Analysis"
          action={<BarChart3 className="w-4 h-4 text-war-room-accent" />}
        >
          {sensitivity ? (
            <SensitivityChart sensitivities={sensitivity.sensitivities} />
          ) : (
            <div className="space-y-3 py-4">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-5 w-full" />
              ))}
            </div>
          )}
        </Panel>
      </div>

      {/* Current Evidence Summary */}
      {Object.keys(evidence).length > 0 && (
        <Panel title="Current Evidence">
          <div className="flex flex-wrap gap-2">
            {Object.entries(evidence).map(([node, state]) => (
              <Badge key={node} variant="success">
                {node.replace(/_/g, ' ')} = {state}
              </Badge>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

function PosteriorChart({ posterior }: { posterior: Record<string, number> }) {
  const data = Object.entries(posterior)
    .map(([name, prob]) => ({
      name: name.replace(/_/g, ' '),
      probability: prob * 100,
      fullName: name,
    }))
    .sort((a, b) => b.probability - a.probability);

  const OUTCOME_COLORS: Record<string, string> = {
    STATUS_QUO: '#3b82f6',
    CONCESSIONS: '#22c55e',
    TRANSITION: '#eab308',
    COLLAPSE: '#ef4444',
    FRAGMENTATION: '#8b5cf6',
  };

  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 20, right: 20 }}>
          <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} stroke="#6b7280" fontSize={10} />
          <YAxis type="category" dataKey="name" width={80} stroke="#6b7280" fontSize={10} />
          <Tooltip
            content={({ payload }) => {
              if (!payload?.[0]) return null;
              const item = payload[0].payload;
              return (
                <div className="panel-elevated border border-war-room-border p-2">
                  <p className="text-war-room-text-primary text-body">{item.fullName}</p>
                  <p className="text-war-room-accent font-mono">{item.probability.toFixed(1)}%</p>
                </div>
              );
            }}
          />
          <Bar dataKey="probability" radius={[0, 4, 4, 0]}>
            {data.map((entry) => (
              <Cell key={entry.fullName} fill={OUTCOME_COLORS[entry.fullName] || '#6b7280'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function SensitivityChart({ sensitivities }: { sensitivities: Record<string, number> }) {
  const data = Object.entries(sensitivities)
    .map(([name, mi]) => ({
      name: name.replace(/_/g, ' ').slice(0, 12),
      fullName: name,
      mi: mi,
    }))
    .sort((a, b) => b.mi - a.mi)
    .slice(0, 8);

  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 20, right: 20 }}>
          <XAxis type="number" stroke="#6b7280" fontSize={10} />
          <YAxis type="category" dataKey="name" width={80} stroke="#6b7280" fontSize={10} />
          <Tooltip
            content={({ payload }) => {
              if (!payload?.[0]) return null;
              const item = payload[0].payload;
              return (
                <div className="panel-elevated border border-war-room-border p-2">
                  <p className="text-war-room-text-primary text-body">{item.fullName}</p>
                  <p className="text-war-room-accent font-mono">MI: {item.mi.toFixed(4)}</p>
                </div>
              );
            }}
          />
          <Bar dataKey="mi" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
