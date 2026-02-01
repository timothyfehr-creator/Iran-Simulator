import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  iranProvinces,
  ethnicityColors,
  protestStatusColors,
  neighboringCountries,
  type ProvinceData,
} from '../../data/iranMapData';
import { useSimulationStore } from '../../store/simulationStore';
import { Panel } from '../ui/Panel';
import { Skeleton } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';
import { AlertTriangle, Users, MapPin, Flame, X, Map } from 'lucide-react';

type ViewMode = 'ethnicity' | 'protest' | 'risk';

interface ProvinceTooltipProps {
  province: ProvinceData;
  onClose: () => void;
}

function ProvinceTooltip({ province, onClose }: ProvinceTooltipProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className="absolute z-50 panel-elevated border border-war-room-border p-4 min-w-[280px]"
      style={{ maxWidth: '320px' }}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-bold text-war-room-text-primary text-heading">{province.name}</h3>
          <p className="text-caption text-war-room-text-secondary">{province.ethnicity} majority</p>
        </div>
        <button
          onClick={onClose}
          className="text-war-room-muted hover:text-war-room-text-primary transition-colors p-1 min-w-[28px] min-h-[28px] flex items-center justify-center"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="space-y-2 text-body">
        <div className="flex items-center justify-between">
          <span className="text-war-room-text-secondary flex items-center gap-1">
            <Users className="w-3 h-3" /> Population
          </span>
          <span className="text-war-room-text-primary">{province.population}M</span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-war-room-text-secondary flex items-center gap-1">
            <Flame className="w-3 h-3" /> Protest Level
          </span>
          <span
            className="font-medium"
            style={{ color: protestStatusColors[province.protestStatus] }}
          >
            {province.protestStatus}
          </span>
        </div>

        {province.borders.length > 0 && (
          <div className="flex items-center justify-between">
            <span className="text-war-room-text-secondary flex items-center gap-1">
              <MapPin className="w-3 h-3" /> Borders
            </span>
            <span className="text-war-room-text-primary">{province.borders.join(', ')}</span>
          </div>
        )}

        <div className="pt-2 border-t border-war-room-border">
          <p className="text-caption text-war-room-muted">{province.strategicFeatures}</p>
        </div>

        <div className="pt-2">
          <p className="text-caption text-war-room-text-secondary">Key cities:</p>
          <p className="text-caption text-war-room-text-primary">{province.cities.join(', ')}</p>
        </div>
      </div>
    </motion.div>
  );
}

export function RegionalMap() {
  const [viewMode, setViewMode] = useState<ViewMode>('protest');
  const [selectedProvince, setSelectedProvince] = useState<ProvinceData | null>(null);
  const [hoveredProvince, setHoveredProvince] = useState<string | null>(null);
  const results = useSimulationStore((state) => state.results);
  const isLoading = useSimulationStore((state) => state.isLoading);

  const provinceRiskScores = useMemo(() => {
    if (!results) return {};

    const baseRisk = 1 - (results.outcome_distribution.REGIME_SURVIVES_STATUS_QUO?.probability || 0.8);
    const ethnicRisk = results.key_event_rates.ethnic_uprising || 0.1;

    const scores: Record<string, number> = {};
    iranProvinces.forEach((p) => {
      let risk = baseRisk;
      if (['Kurdish', 'Baloch', 'Arab'].includes(p.ethnicity)) {
        risk += ethnicRisk * 0.5;
      }
      if (p.protestStatus === 'HIGH') {
        risk *= 1.3;
      } else if (p.protestStatus === 'MEDIUM') {
        risk *= 1.1;
      }
      if (p.borders.length > 0) {
        risk *= 1.1;
      }
      scores[p.id] = Math.min(1, risk);
    });

    return scores;
  }, [results]);

  const getProvinceColor = (province: ProvinceData): string => {
    switch (viewMode) {
      case 'ethnicity':
        return ethnicityColors[province.ethnicity] || '#6b7280';
      case 'protest':
        return protestStatusColors[province.protestStatus] || '#6b7280';
      case 'risk':
        const risk = provinceRiskScores[province.id] || 0;
        if (risk > 0.3) return '#ef4444';
        if (risk > 0.2) return '#f97316';
        if (risk > 0.1) return '#f59e0b';
        return '#22c55e';
      default:
        return '#6b7280';
    }
  };

  const highRiskProvinces = iranProvinces.filter(
    (p) => p.protestStatus === 'HIGH' || (provinceRiskScores[p.id] || 0) > 0.25
  );

  if (isLoading && !results) {
    return (
      <Panel title="Regional Map">
        <Skeleton className="h-[500px] w-full" />
      </Panel>
    );
  }

  return (
    <div className="space-y-4">
      {/* View Mode Selector */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          {(['protest', 'ethnicity', 'risk'] as ViewMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`px-3 py-1.5 text-caption font-medium rounded-lg transition-colors min-h-[36px] focus-visible:ring-2 focus-visible:ring-war-room-accent focus-visible:ring-offset-2 focus-visible:ring-offset-war-room-bg ${
                viewMode === mode
                  ? 'bg-war-room-accent text-white'
                  : 'bg-war-room-bg text-war-room-text-secondary hover:text-war-room-text-primary'
              }`}
            >
              {mode === 'protest' && 'Protest Activity'}
              {mode === 'ethnicity' && 'Ethnic Groups'}
              {mode === 'risk' && 'Risk Assessment'}
            </button>
          ))}
        </div>

        {highRiskProvinces.length > 0 && (
          <div className="flex items-center gap-2 text-caption text-war-room-danger">
            <AlertTriangle className="w-4 h-4" />
            <span>{highRiskProvinces.length} high-risk provinces</span>
          </div>
        )}
      </div>

      {/* Map Container */}
      <Panel>
        <div className="relative bg-[#0d1117] rounded-lg overflow-hidden -m-1">
          <svg viewBox="0 0 100 90" className="w-full h-[500px]">
            <rect x="0" y="0" width="100" height="90" fill="#0d1117" />
            <path
              d="M 20 15 L 40 10 L 55 12 L 70 15 L 85 25 L 90 40 L 88 55 L 85 65 L 75 75 L 60 80 L 45 78 L 35 72 L 28 60 L 22 50 L 18 40 L 20 25 Z"
              fill="#1a1f2e"
              stroke="#2d3748"
              strokeWidth="0.5"
            />
            <ellipse cx="48" cy="15" rx="12" ry="6" fill="#1e3a5f" opacity="0.5" />
            <text x="48" y="16" textAnchor="middle" className="text-[3px] fill-blue-400/50">
              Caspian Sea
            </text>
            <path d="M 30 72 Q 40 82 60 82 L 58 78 L 40 76 Z" fill="#1e3a5f" opacity="0.5" />
            <text x="45" y="80" textAnchor="middle" className="text-[2.5px] fill-blue-400/50">
              Persian Gulf
            </text>
            {neighboringCountries.map((country) => (
              <text
                key={country.name}
                x={country.position.x}
                y={country.position.y}
                textAnchor="middle"
                className="text-[2.5px] fill-gray-600 uppercase tracking-wider"
              >
                {country.name}
              </text>
            ))}
            {iranProvinces.map((province) => {
              const isHovered = hoveredProvince === province.id;
              const isSelected = selectedProvince?.id === province.id;
              const color = getProvinceColor(province);
              const size = Math.max(2, Math.sqrt(province.population) * 1.2);

              return (
                <g key={province.id}>
                  {province.protestStatus === 'HIGH' && viewMode === 'protest' && (
                    <circle cx={province.center.x} cy={province.center.y} r={size + 2} fill={color} opacity="0.3">
                      <animate attributeName="r" values={`${size + 1};${size + 4};${size + 1}`} dur="2s" repeatCount="indefinite" />
                      <animate attributeName="opacity" values="0.3;0.1;0.3" dur="2s" repeatCount="indefinite" />
                    </circle>
                  )}
                  <circle
                    cx={province.center.x}
                    cy={province.center.y}
                    r={isHovered || isSelected ? size + 1 : size}
                    fill={color}
                    stroke={isSelected ? '#fff' : isHovered ? '#aaa' : 'none'}
                    strokeWidth={isSelected ? 0.5 : 0.3}
                    opacity={isHovered || isSelected ? 1 : 0.8}
                    className="cursor-pointer transition-all duration-200"
                    onMouseEnter={() => setHoveredProvince(province.id)}
                    onMouseLeave={() => setHoveredProvince(null)}
                    onClick={() => setSelectedProvince(province)}
                  />
                  <text
                    x={province.center.x}
                    y={province.center.y + size + 3}
                    textAnchor="middle"
                    className={`text-[2.5px] ${isHovered || isSelected ? 'fill-white' : 'fill-gray-400'} pointer-events-none`}
                  >
                    {province.name}
                  </text>
                </g>
              );
            })}
          </svg>

          <AnimatePresence>
            {selectedProvince && (
              <div className="absolute top-4 right-4">
                <ProvinceTooltip
                  province={selectedProvince}
                  onClose={() => setSelectedProvince(null)}
                />
              </div>
            )}
          </AnimatePresence>
        </div>
      </Panel>

      {/* Legend */}
      <div className="panel p-4 flex flex-wrap gap-4 text-caption">
        {viewMode === 'ethnicity' &&
          Object.entries(ethnicityColors).map(([ethnicity, color]) => (
            <div key={ethnicity} className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-war-room-text-secondary">{ethnicity}</span>
            </div>
          ))}
        {viewMode === 'protest' &&
          Object.entries(protestStatusColors).map(([status, color]) => (
            <div key={status} className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-war-room-text-secondary">{status}</span>
            </div>
          ))}
        {viewMode === 'risk' && (
          <>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <span className="text-war-room-text-secondary">Critical (&gt;30%)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full bg-orange-500" />
              <span className="text-war-room-text-secondary">High (20-30%)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full bg-amber-500" />
              <span className="text-war-room-text-secondary">Elevated (10-20%)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full bg-green-500" />
              <span className="text-war-room-text-secondary">Low (&lt;10%)</span>
            </div>
          </>
        )}
        <div className="flex items-center gap-1.5 ml-auto text-war-room-muted">
          <span>Circle size = population</span>
        </div>
      </div>

      {/* Key Hotspots Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Panel title="Kurdish Regions">
          <div className="space-y-1">
            {iranProvinces
              .filter((p) => p.ethnicity === 'Kurdish')
              .map((p) => (
                <div key={p.id} className="flex items-center justify-between text-body">
                  <span className="text-war-room-text-secondary">{p.name}</span>
                  <span className="text-caption font-medium" style={{ color: protestStatusColors[p.protestStatus] }}>
                    {p.protestStatus}
                  </span>
                </div>
              ))}
          </div>
        </Panel>

        <Panel title="Border Provinces">
          <div className="space-y-1">
            {iranProvinces
              .filter((p) => p.borders.length > 0)
              .slice(0, 5)
              .map((p) => (
                <div key={p.id} className="flex items-center justify-between text-body">
                  <span className="text-war-room-text-secondary">{p.name}</span>
                  <span className="text-caption text-war-room-muted">{p.borders.join(', ')}</span>
                </div>
              ))}
          </div>
        </Panel>

        <Panel title="Strategic Sites">
          <div className="space-y-1.5 text-body text-war-room-text-secondary">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-yellow-500" />
              <span>Bushehr - Nuclear Plant</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-blue-500" />
              <span>Hormozgan - Strait Control</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-red-500" />
              <span>Khuzestan - Oil Fields</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-purple-500" />
              <span>Tehran - IRGC HQ</span>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
