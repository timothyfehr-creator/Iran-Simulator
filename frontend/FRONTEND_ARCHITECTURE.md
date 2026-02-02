# Iran Simulator Frontend Architecture

> This document explains the frontend architecture for LLM consumption. It describes how components interact, data flows, and design patterns used.

## Technology Stack

| Technology | Purpose | Version |
|------------|---------|---------|
| React | UI library | 19.x |
| TypeScript | Type safety | 5.x |
| Vite | Build tool & dev server | 7.x |
| Zustand | State management | 5.x |
| Tailwind CSS | Styling (dark theme) | 3.x |
| Recharts | Data visualization charts | 2.x |
| Framer Motion | Animations | 11.x |
| Lucide React | Icon library | 0.x |

## Project Structure

```
frontend/
├── src/
│   ├── main.tsx                 # App entry point
│   ├── App.tsx                  # Root component
│   ├── index.css                # Global styles + Tailwind
│   │
│   ├── types/
│   │   └── simulation.ts        # TypeScript interfaces for all data
│   │
│   ├── data/
│   │   ├── mockData.ts          # Hardcoded simulation results
│   │   └── iranMapData.ts       # Province coordinates & metadata
│   │
│   ├── services/
│   │   ├── api.ts               # API interface definitions
│   │   ├── mockApi.ts           # Mock implementation (default)
│   │   ├── realApi.ts           # Real backend calls
│   │   ├── causalApi.ts         # Causal inference endpoints
│   │   └── index.ts             # API export (switches mock/real)
│   │
│   ├── store/
│   │   └── simulationStore.ts   # Zustand global state
│   │
│   ├── components/
│   │   ├── layout/              # Page structure components
│   │   ├── controls/            # User input components
│   │   ├── status/              # Status indicators
│   │   ├── visualization/       # Charts & maps
│   │   └── timeline/            # Timeline slider
│   │
│   └── utils/
│       ├── colors.ts            # Color constants
│       └── formatters.ts        # Number/percent formatting
│
├── tests/                       # Vitest unit tests
├── e2e/                         # Playwright E2E tests
└── public/                      # Static assets
```

## Component Hierarchy

```
App
└── WarRoomLayout
    ├── Header
    │   └── DefconWidget          # Regime stability indicator
    │
    ├── Sidebar
    │   ├── RunSimulationButton   # Triggers simulation
    │   ├── ControlPanel          # Parameter sliders
    │   │   └── ConfidenceSlider  # Reusable slider component
    │   └── RunStats              # Session run count
    │
    ├── MainView                  # Tabbed content area
    │   ├── ExecutiveSummary      # Tab 1: BLUF overview
    │   ├── OutcomeChart          # Tab 2: Probability charts
    │   ├── RegionalMap           # Tab 3: Interactive Iran map
    │   └── CausalExplorer        # Tab 4: Bayesian network
    │
    └── TimelineSlider            # Bottom: Day 0-90 slider
```

## State Management (Zustand)

### Store Structure (`simulationStore.ts`)

```typescript
interface SimulationStore {
  // State
  controls: SimulationControls;    // User-adjustable parameters
  results: SimulationResults;      // Simulation output data
  isLoading: boolean;              // Loading indicator
  error: string | null;            // Error message
  runCount: number;                // Session run counter
  lastRunTime: Date | null;        # When last simulation ran
  lastRunDuration: number | null;  // How long it took (ms)

  // Actions
  setTimelineDay: (day: number) => void;
  updateControl: (key, value) => void;
  runSimulation: () => Promise<void>;
  loadResults: () => Promise<void>;
  resetControls: () => void;
}
```

### Controls Shape

```typescript
interface SimulationControls {
  timelineDay: number;           // 0-90 day slider
  analystConfidence: number;     // 0-100%
  runs: number;                  // Monte Carlo iterations (10000)
  defectionProbability: number;  // 0.0-1.0 (security force loyalty)
  protestGrowthFactor: number;   // 1.0-2.0 (protest momentum)
}
```

### Results Shape

```typescript
interface SimulationResults {
  n_runs: number;
  outcome_distribution: Record<string, {
    probability: number;
    ci_low: number;
    ci_high: number;
  }>;
  economic_analysis: {
    stress_level: 'stable' | 'pressured' | 'critical';
    rial_rate_used: number;
    inflation_used: number;
  };
  key_event_rates: {
    us_soft_intervention: number;
    us_hard_intervention: number;
    security_force_defection: number;
    khamenei_death: number;
    ethnic_uprising: number;
  };
}
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERACTIONS                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CONTROL COMPONENTS                          │
│  ConfidenceSlider → updateControl() → Zustand Store             │
│  RunSimulationButton → runSimulation() → API call               │
│  TimelineSlider → setTimelineDay() → Zustand Store              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       ZUSTAND STORE                              │
│  - Holds all application state                                   │
│  - Components subscribe via useSimulationStore()                 │
│  - Actions trigger re-renders in subscribed components           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VISUALIZATION COMPONENTS                      │
│  - ExecutiveSummary reads results.outcome_distribution           │
│  - OutcomeChart renders Recharts bar chart                       │
│  - RegionalMap combines results + iranMapData                    │
│  - DefconWidget reads results.economic_analysis.stress_level     │
└─────────────────────────────────────────────────────────────────┘
```

## API Layer

### Switching Between Mock and Real API

```typescript
// services/index.ts
export const api: SimulationApi =
  import.meta.env.VITE_USE_REAL_API === 'true' ? realApi : mockApi;
```

- **Default**: Uses `mockApi` with hardcoded data + 1.5s delay
- **Production**: Set `VITE_USE_REAL_API=true` in `.env` to use FastAPI backend

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/results` | GET | Fetch latest simulation results |
| `/api/simulate` | POST | Run new simulation with params |
| `/api/status` | GET | Check backend connection |
| `/api/causal/graph` | GET | Get Bayesian network structure |
| `/api/causal/infer` | POST | Run causal inference |

## Component Details

### 1. DefconWidget (`status/DefconWidget.tsx`)

**Purpose**: Shows regime stability status with color-coded indicator

**Props**:
```typescript
interface DefconWidgetProps {
  status: 'stable' | 'pressured' | 'critical';
  label: string;
}
```

**Behavior**:
- Green background + "STABLE" when regime stable
- Amber background + "PRESSURED" when under pressure
- Red background + pulsing animation + "CRITICAL" when critical

**Data Source**: `results.economic_analysis.stress_level`

### 2. ControlPanel (`controls/ControlPanel.tsx`)

**Purpose**: Contains all user-adjustable simulation parameters

**Contains**:
- `RunSimulationButton` - Triggers simulation
- 3x `ConfidenceSlider` components:
  - Security Force Loyalty (maps to `defectionProbability`)
  - Protest Momentum (maps to `protestGrowthFactor`)
  - Intel Confidence (maps to `analystConfidence`)

**Slider Value Mappings**:
```typescript
// Security Force Loyalty (inverted - high loyalty = low defection)
value = 100 - controls.defectionProbability * 1000
onChange = (v) => updateControl('defectionProbability', (100 - v) / 1000)

// Protest Momentum (0-100% maps to 1.0-2.0 growth factor)
value = (controls.protestGrowthFactor - 1) * 100
onChange = (v) => updateControl('protestGrowthFactor', 1 + v / 100)

// Intel Confidence (direct mapping)
value = controls.analystConfidence
onChange = (v) => updateControl('analystConfidence', v)
```

### 3. MainView (`layout/MainView.tsx`)

**Purpose**: Tabbed container for main content

**Tabs**:
| Tab ID | Label | Component |
|--------|-------|-----------|
| `summary` | Executive Summary | `<ExecutiveSummary />` |
| `charts` | Analysis | `<OutcomeChart />` + `<KeyMetricsPanel />` |
| `map` | Regional Map | `<RegionalMap />` |
| `causal` | Causal Explorer | `<CausalExplorer />` |

**State**: Local `useState` for `activeTab`

### 4. RegionalMap (`visualization/RegionalMap.tsx`)

**Purpose**: Interactive SVG map of Iran's 31 provinces

**Features**:
- Three view modes: Protest Activity, Ethnic Groups, Risk Assessment
- Clickable province markers with tooltips
- Marker size proportional to population
- Pulse animation on high-protest provinces
- Summary panels for Kurdish regions, border provinces, strategic sites

**Data Sources**:
- `iranMapData.ts`: Province coordinates, ethnicity, cities, borders
- `simulationStore.results`: For risk score calculations

**View Mode Colors**:
```typescript
// Protest Activity
HIGH: '#ef4444'    // Red
MEDIUM: '#f59e0b'  // Amber
LOW: '#22c55e'     // Green
NONE: '#6b7280'    // Gray

// Ethnicity
Persian: '#3b82f6'  // Blue
Kurdish: '#ef4444'  // Red
Azeri: '#22c55e'    // Green
Baloch: '#f97316'   // Orange
Arab: '#eab308'     // Yellow
Lur: '#8b5cf6'      // Purple
Turkmen: '#14b8a6'  // Teal
Mixed: '#6b7280'    // Gray

// Risk Assessment (calculated dynamically)
Critical (>30%): '#ef4444'
High (20-30%): '#f97316'
Elevated (10-20%): '#f59e0b'
Low (<10%): '#22c55e'
```

### 5. ExecutiveSummary (`visualization/ExecutiveSummary.tsx`)

**Purpose**: BLUF (Bottom Line Up Front) overview for decision makers

**Sections**:
1. **BLUF paragraph** - Most likely outcome with probability
2. **Key metrics cards** - Regime stability, collapse risk, economic stress
3. **Event probabilities** - Security defection, ethnic uprising, etc.
4. **Outcome ranking** - All outcomes sorted by probability
5. **Key uncertainties** - Bullet points of main unknowns

### 6. OutcomeChart (`visualization/OutcomeChart.tsx`)

**Purpose**: Bar chart showing outcome probability distribution

**Library**: Recharts `<BarChart>`

**Data transformation**:
```typescript
const chartData = Object.entries(results.outcome_distribution)
  .map(([outcome, data]) => ({
    name: formatOutcomeName(outcome),
    probability: data.probability * 100,
    fill: getOutcomeColor(outcome),
  }))
  .sort((a, b) => b.probability - a.probability);
```

### 7. TimelineSlider (`timeline/TimelineSlider.tsx`)

**Purpose**: Day selector for future timeline visualization

**Range**: 0-90 days
**Tick marks**: Every 10 days
**State**: Controlled by `controls.timelineDay` in store

## Styling System

### Tailwind Dark Theme

Custom colors defined in `tailwind.config.js`:

```javascript
colors: {
  'war-room': {
    bg: '#0a0f1c',      // Deep navy background
    panel: '#111827',    // Panel background
    border: '#1f2937',   // Border color
    accent: '#3b82f6',   // Blue accent
    danger: '#ef4444',   // Red for critical
    warning: '#f59e0b',  // Amber for warnings
    success: '#10b981',  // Green for stable
  },
}
```

### Common CSS Classes

```css
/* Panel styling */
.panel {
  @apply bg-war-room-panel border border-war-room-border rounded-lg;
}

/* Primary button */
.btn-primary {
  @apply bg-war-room-accent hover:bg-blue-600 text-white
         font-medium rounded-lg transition-colors;
}

/* Slider track */
.slider-input {
  @apply w-full h-2 bg-war-room-bg rounded-lg appearance-none
         cursor-pointer accent-war-room-accent;
}
```

## Animation Patterns

### Framer Motion Usage

1. **DefconWidget pulse** (critical status):
```typescript
<motion.div
  animate={{ opacity: [1, 0.7, 1] }}
  transition={{ duration: 1.5, repeat: Infinity }}
/>
```

2. **Province tooltip appear**:
```typescript
<motion.div
  initial={{ opacity: 0, y: 10 }}
  animate={{ opacity: 1, y: 0 }}
  exit={{ opacity: 0, y: 10 }}
/>
```

3. **SVG pulse for high-risk provinces**:
```xml
<circle>
  <animate attributeName="r" values="..." dur="2s" repeatCount="indefinite" />
  <animate attributeName="opacity" values="..." dur="2s" repeatCount="indefinite" />
</circle>
```

## Testing Strategy

### Unit Tests (Vitest + React Testing Library)

Location: `tests/`

```typescript
// Example: ControlPanel.test.tsx
it('updates security force loyalty slider value', () => {
  render(<ControlPanel />);
  const slider = screen.getByLabelText(/security force loyalty/i);
  fireEvent.change(slider, { target: { value: '30' } });
  expect(useSimulationStore.getState().controls.defectionProbability).toBeCloseTo(0.07);
});
```

### E2E Tests (Playwright)

Location: `e2e/`

```typescript
// Example: regional-map.spec.ts
test('can switch between view modes', async ({ page }) => {
  await page.click('button:has-text("Regional Map")');
  await page.click('button:has-text("Ethnic Groups")');
  await expect(page.locator('text=Persian').first()).toBeVisible();
});
```

## Key Patterns

### 1. Store Subscription Pattern

Components subscribe to specific slices of state:

```typescript
// Only re-renders when results change
const results = useSimulationStore((state) => state.results);

// Only re-renders when isLoading changes
const isLoading = useSimulationStore((state) => state.isLoading);
```

### 2. Computed Values with useMemo

Expensive calculations cached until dependencies change:

```typescript
const provinceRiskScores = useMemo(() => {
  // Calculate risk scores from results
  return computeRiskScores(results);
}, [results]);
```

### 3. Service Abstraction

API implementation swappable without changing components:

```typescript
// Components import from services/index.ts
import { api } from '../services';

// Implementation details hidden
await api.runSimulation(params);
```

### 4. Error Boundary

Wraps visualization components to catch render errors:

```typescript
<ErrorBoundary>
  {activeTab === 'map' && <RegionalMap />}
</ErrorBoundary>
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `VITE_USE_REAL_API` | Use real backend instead of mock | `false` |
| `VITE_API_URL` | Backend API base URL | `http://localhost:8000` |

## Running the Application

```bash
# Development (uses mock API)
npm run dev

# Development with real backend
VITE_USE_REAL_API=true npm run dev

# Run unit tests
npm run test

# Run E2E tests
npm run test:e2e

# Build for production
npm run build
```
