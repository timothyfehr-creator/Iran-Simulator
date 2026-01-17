"""
Iran Crisis Simulator - Mission Control Dashboard
==================================================

A Streamlit dashboard for observing past simulation runs and running
ad-hoc simulations with parameter overrides.

Usage:
    streamlit run dashboard.py
    # or
    make dashboard
"""

import sys
import re
from pathlib import Path

# Add repo root and src to path for imports
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

import json
import copy
import subprocess
import time
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# Import simulation engine
from src.simulation import IranCrisisSimulation
from priors.contract import resolve_priors

# Import CausalEngine for BN visualization (optional)
try:
    from scripts.prototype_causal_graph import CausalEngine, ALL_NODES, EDGES
    HAS_CAUSAL_ENGINE = True
except ImportError:
    HAS_CAUSAL_ENGINE = False

# Load .env file (this module loads dotenv on import)
try:
    import src.config.secrets  # Loads .env automatically
except ImportError:
    pass  # Secrets module not available, env vars must be set externally

RUNS_DIR = REPO_ROOT / "runs"
DATA_DIR = REPO_ROOT / "data"


# =============================================================================
# EXPLAINER CONTENT
# =============================================================================

EXPLAINER_TEXT = """
### Monte Carlo Simulation
This dashboard runs **10,000+ simulated scenarios** for Iran's political
trajectory over a 90-day horizon. Each simulation samples from
probability distributions for key events (protests, crackdowns,
defections) and traces the outcome.

### Outcome Categories
- **Regime Survives (Status Quo)**: Protests suppressed, no concessions
- **Regime Survives (Concessions)**: Meaningful reforms offered
- **Managed Transition**: Orderly leadership succession
- **Chaotic Collapse**: Regime falls without clear successor
- **Ethnic Fragmentation**: Regional breakaway (Kurdistan, etc.)

### Key Parameters
- **Security Force Defection**: Probability that military units
  refuse orders (historically rare but high impact)
- **Protest Growth Factor**: Multiplier on protest sustainability
  and escalation probabilities

### Limitations
- Probabilities are analyst estimates, not ground truth
- Model uses historical base rates from similar regimes
- Results should inform planning, not predict outcomes
"""


# =============================================================================
# DESIGN SYSTEM - Colors, Styles, and Components
# =============================================================================

# Chart color palette
CHART_COLORS = ['#3B82F6', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981']

# Outcome-specific colors for simulation results
OUTCOME_COLORS = {
    'Regime Survives Status Quo': '#10B981',
    'Regime Survives With Concessions': '#22C55E',
    'Managed Transition': '#3B82F6',
    'Regime Collapse Chaotic': '#EF4444',
    'Ethnic Fragmentation': '#8B5CF6',
}

# Status badge colors: (background, text)
STATUS_BADGE_COLORS = {
    "success": ("#D1FAE5", "#065F46"),
    "warning": ("#FEF3C7", "#92400E"),
    "error": ("#FEE2E2", "#991B1B"),
    "info": ("#DBEAFE", "#1E40AF"),
    "neutral": ("#F1F5F9", "#475569"),
}

# Plotly chart theme
PLOTLY_THEME = {
    'font': {'family': 'Inter, -apple-system, BlinkMacSystemFont, sans-serif', 'color': '#0F172A'},
    'paper_bgcolor': '#FFFFFF',
    'plot_bgcolor': '#FFFFFF',
    'title': {'font': {'size': 16, 'color': '#0F172A'}},
    'xaxis': {
        'gridcolor': '#E2E8F0',
        'linecolor': '#CBD5E1',
        'tickfont': {'size': 12, 'color': '#475569'},
    },
    'yaxis': {
        'gridcolor': '#E2E8F0',
        'linecolor': '#CBD5E1',
        'tickfont': {'size': 12, 'color': '#475569'},
    },
    'legend': {
        'bgcolor': 'rgba(255,255,255,0)',
        'bordercolor': 'rgba(0,0,0,0)',
    },
    'margin': {'l': 60, 'r': 20, 't': 50, 'b': 50},
}


def inject_custom_css():
    """Inject custom CSS for professional SaaS-style dashboard."""
    st.markdown("""
        <style>
        /* Import Inter font */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        /* Global font */
        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }

        /* Main content area */
        .main .block-container {
            padding: 2rem 3rem;
            max-width: 1200px;
        }

        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF;
            border-right: 1px solid #E2E8F0;
        }

        [data-testid="stSidebar"] .block-container {
            padding: 1.5rem 1rem;
        }

        /* Headers */
        h1 {
            font-size: 28px !important;
            font-weight: 600 !important;
            color: #0F172A !important;
            margin-bottom: 0.5rem !important;
        }

        h2 {
            font-size: 20px !important;
            font-weight: 600 !important;
            color: #0F172A !important;
            margin-top: 1.5rem !important;
        }

        h3 {
            font-size: 16px !important;
            font-weight: 500 !important;
            color: #0F172A !important;
        }

        /* Subheader styling */
        .stSubheader {
            font-size: 18px !important;
            font-weight: 600 !important;
            color: #0F172A !important;
            border-bottom: 1px solid #E2E8F0;
            padding-bottom: 0.5rem;
            margin-bottom: 1rem !important;
        }

        /* Metric styling */
        [data-testid="stMetricValue"] {
            font-size: 28px !important;
            font-weight: 600 !important;
            color: #0F172A !important;
        }

        [data-testid="stMetricLabel"] {
            font-size: 12px !important;
            color: #64748B !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
            font-weight: 500 !important;
        }

        /* Button styling */
        .stButton > button {
            background-color: #3B82F6 !important;
            color: white !important;
            border: none !important;
            border-radius: 6px !important;
            font-weight: 500 !important;
            padding: 0.5rem 1rem !important;
            transition: background-color 0.2s ease !important;
        }

        .stButton > button:hover {
            background-color: #2563EB !important;
        }

        .stButton > button[kind="secondary"] {
            background-color: #FFFFFF !important;
            color: #0F172A !important;
            border: 1px solid #E2E8F0 !important;
        }

        /* Slider styling */
        .stSlider > div > div > div {
            background-color: #3B82F6 !important;
        }

        /* Selectbox styling */
        .stSelectbox > div > div {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 6px;
        }

        /* Expander styling */
        .streamlit-expanderHeader {
            background-color: #F8FAFC !important;
            border-radius: 6px !important;
            font-weight: 500 !important;
        }

        /* Info/warning/error boxes */
        .stAlert {
            border-radius: 8px !important;
            border: none !important;
        }

        /* Divider */
        hr {
            border: none !important;
            height: 1px !important;
            background-color: #E2E8F0 !important;
            margin: 1.5rem 0 !important;
        }

        /* Radio buttons - horizontal mode toggle */
        .stRadio > div {
            gap: 0 !important;
        }

        .stRadio > div > label {
            background-color: #F1F5F9 !important;
            padding: 0.5rem 1rem !important;
            border-radius: 0 !important;
            border: 1px solid #E2E8F0 !important;
            margin: 0 !important;
        }

        .stRadio > div > label:first-child {
            border-radius: 6px 0 0 6px !important;
        }

        .stRadio > div > label:last-child {
            border-radius: 0 6px 6px 0 !important;
            border-left: none !important;
        }

        .stRadio > div > label[data-checked="true"] {
            background-color: #3B82F6 !important;
            color: white !important;
            border-color: #3B82F6 !important;
        }

        /* DataFrames */
        .stDataFrame {
            border: 1px solid #E2E8F0 !important;
            border-radius: 8px !important;
        }

        /* Caption text */
        .stCaption {
            color: #64748B !important;
            font-size: 13px !important;
        }

        /* Card styling utility class */
        .dashboard-card {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }

        .dashboard-card-header {
            font-size: 14px;
            font-weight: 600;
            color: #0F172A;
            margin-bottom: 1rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid #E2E8F0;
        }

        /* Status badges */
        .status-badge {
            display: inline-flex;
            align-items: center;
            padding: 3px 10px;
            font-size: 12px;
            font-weight: 500;
            border-radius: 9999px;
            line-height: 1.4;
        }

        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)


def render_badge(text: str, variant: str = "neutral") -> str:
    """Render a professional status badge as HTML."""
    bg, fg = STATUS_BADGE_COLORS.get(variant, STATUS_BADGE_COLORS["neutral"])
    return f'<span style="background:{bg};color:{fg};padding:3px 10px;border-radius:9999px;font-size:12px;font-weight:500;display:inline-block;">{text}</span>'


def render_metric_card(label: str, value: str, subtitle: str = None) -> str:
    """Render a styled metric card as HTML."""
    subtitle_html = f'<div style="font-size:13px;color:#64748B;margin-top:4px;">{subtitle}</div>' if subtitle else ''
    return f'''
    <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:1.25rem;text-align:center;">
        <div style="font-size:12px;color:#64748B;text-transform:uppercase;letter-spacing:0.5px;font-weight:500;margin-bottom:6px;">
            {label}
        </div>
        <div style="font-size:28px;font-weight:600;color:#0F172A;">
            {value}
        </div>
        {subtitle_html}
    </div>
    '''


def card_start(title: str = None) -> None:
    """Start a card container with optional title."""
    if title:
        st.markdown(f'''
            <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:1.5rem;margin-bottom:1rem;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <div style="font-size:14px;font-weight:600;color:#0F172A;margin-bottom:1rem;padding-bottom:0.75rem;border-bottom:1px solid #E2E8F0;">
                    {title}
                </div>
        ''', unsafe_allow_html=True)
    else:
        st.markdown('''
            <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:1.5rem;margin-bottom:1rem;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        ''', unsafe_allow_html=True)


def card_end() -> None:
    """Close a card container."""
    st.markdown('</div>', unsafe_allow_html=True)


# =============================================================================
# RUN STATUS HELPERS
# =============================================================================

@dataclass
class RunStatus:
    """Status of a run folder's artifacts."""
    name: str
    has_claims: bool = False
    has_compiled_intel: bool = False
    has_priors: bool = False
    has_simulation: bool = False
    is_test: bool = False
    is_adhoc: bool = False

    @property
    def can_simulate(self) -> bool:
        """Can run simulation (has both intel and priors)."""
        return self.has_compiled_intel and self.has_priors

    @property
    def can_compile(self) -> bool:
        """Can compile intel (has claims but no compiled intel)."""
        return self.has_claims and not self.has_compiled_intel

    @property
    def status_variant(self) -> str:
        """Return status variant for badge styling."""
        if self.can_simulate:
            return "success"
        elif self.has_compiled_intel:
            return "warning"
        elif self.can_compile:
            return "info"
        else:
            return "neutral"

    @property
    def status_label(self) -> str:
        """Return human-readable status."""
        if self.can_simulate:
            return "Ready"
        elif self.has_compiled_intel:
            return "Missing Priors"
        elif self.can_compile:
            return "Pending Compile"
        else:
            return "Import Only"

    @property
    def status_badge_html(self) -> str:
        """Return styled HTML badge for this status."""
        return render_badge(self.status_label, self.status_variant)


def get_run_status(run_path: Path) -> RunStatus:
    """Check which artifacts exist in a run folder."""
    name = run_path.name
    return RunStatus(
        name=name,
        has_claims=(run_path / "claims_deep_research.jsonl").exists(),
        has_compiled_intel=(run_path / "compiled_intel.json").exists(),
        has_priors=(run_path / "priors_resolved.json").exists(),
        has_simulation=(run_path / "simulation_results.json").exists(),
        is_test=name.startswith("TEST_"),
        is_adhoc=name.startswith("ADHOC_"),
    )


def list_run_folders_with_status(include_test: bool = False, include_adhoc: bool = True) -> List[RunStatus]:
    """Return sorted list of run folders with status (latest first by name)."""
    if not RUNS_DIR.exists():
        return []
    statuses = []
    for f in RUNS_DIR.iterdir():
        if f.is_dir() and not f.name.startswith("_"):
            status = get_run_status(f)
            if status.is_test and not include_test:
                continue
            if status.is_adhoc and not include_adhoc:
                continue
            statuses.append(status)
    return sorted(statuses, key=lambda s: s.name, reverse=True)


def get_latest_simulatable_run() -> Optional[str]:
    """Return the latest run that can simulate (has intel + priors)."""
    statuses = list_run_folders_with_status(include_test=False, include_adhoc=False)
    for s in statuses:
        if s.can_simulate:
            return s.name
    # Fallback: include adhoc runs
    statuses = list_run_folders_with_status(include_test=False, include_adhoc=True)
    for s in statuses:
        if s.can_simulate:
            return s.name
    return None


def get_default_run_index(statuses: List[RunStatus], require_simulatable: bool = False) -> int:
    """Get index of best default run (latest simulatable, or latest overall)."""
    if not statuses:
        return 0
    if require_simulatable:
        for i, s in enumerate(statuses):
            if s.can_simulate:
                return i
    return 0


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def load_json_safe(path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON with graceful error handling."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def load_text_safe(path: Path) -> Optional[str]:
    """Load text file with graceful error handling."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except IOError:
        return None


def get_latest_executive_summary() -> Tuple[Optional[Path], Optional[str]]:
    """
    Find the most recent executive summary from RUN_ folders.
    Returns (path_to_summary, run_name) or (None, None) if not found.
    """
    if not RUNS_DIR.exists():
        return None, None

    candidates = []
    for f in RUNS_DIR.iterdir():
        if f.is_dir() and f.name.startswith("RUN_"):
            summary_path = f / "visualizations" / "EXECUTIVE_SUMMARY_ONE_PAGE.md"
            if summary_path.exists():
                candidates.append((summary_path, f.name))

    if not candidates:
        return None, None

    # Sort by run name descending (newest first)
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0]


def get_status_badge_html(status: Optional[str]) -> str:
    """Return styled HTML badge for pipeline status."""
    if status is None:
        return render_badge("N/A", "neutral")
    status_upper = status.upper()
    if status_upper in ("OK", "PASS"):
        return render_badge("Pass", "success")
    elif status_upper == "WARN":
        return render_badge("Warning", "warning")
    elif status_upper == "FAIL":
        return render_badge("Fail", "error")
    return render_badge(status, "neutral")


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp value to [low, high]."""
    return max(low, min(high, value))


def apply_defection_override(priors: Dict[str, Any], value: float) -> Dict[str, Any]:
    """Override security force defection probability, scaling low/high proportionally."""
    priors = copy.deepcopy(priors)
    key = "security_force_defection_given_protests_30d"
    if key in priors.get("transition_probabilities", {}):
        prob = priors["transition_probabilities"][key]["probability"]
        original_mode = prob.get("mode", prob.get("point", 0.08))
        if original_mode > 0:
            scale = value / original_mode
        else:
            scale = 1.0
        prob["mode"] = clamp(value)
        prob["low"] = clamp(prob.get("low", 0.03) * scale)
        prob["high"] = clamp(prob.get("high", 0.15) * scale)
        if "point" in prob:
            prob["point"] = prob["mode"]
    return priors


def apply_growth_factor(priors: Dict[str, Any], factor: float) -> Dict[str, Any]:
    """Multiply growth-related priors by factor, clamped to [0, 1]."""
    priors = copy.deepcopy(priors)
    growth_keys = [
        "protests_sustain_30d",
        "protests_escalate_14d",
    ]
    tp = priors.get("transition_probabilities", {})
    for key in growth_keys:
        if key in tp:
            prob = tp[key]["probability"]
            prob["mode"] = clamp(prob.get("mode", prob.get("point", 0.5)) * factor)
            prob["low"] = clamp(prob.get("low", 0.3) * factor)
            prob["high"] = clamp(prob.get("high", 0.7) * factor)
            if "point" in prob:
                prob["point"] = prob["mode"]
    return priors


def run_adhoc_simulation(
    intel: Dict[str, Any],
    priors: Dict[str, Any],
    n_runs: int
) -> Tuple[Dict[str, Any], Path]:
    """Run simulation and save to ADHOC folder. Returns (results, run_dir)."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    run_dir = RUNS_DIR / f"ADHOC_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Resolve priors
    priors_resolved, priors_qa = resolve_priors(priors)

    # Save resolved priors
    with open(run_dir / "priors_resolved.json", "w", encoding="utf-8") as f:
        json.dump(priors_resolved, f, indent=2)
    with open(run_dir / "priors_qa.json", "w", encoding="utf-8") as f:
        json.dump(priors_qa, f, indent=2)

    # Run simulation
    sim = IranCrisisSimulation(intel, priors_resolved)
    results = sim.run_monte_carlo(n_runs)

    # Save results
    with open(run_dir / "simulation_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results, run_dir


def compile_intel_for_run(run_path: Path) -> Tuple[bool, str]:
    """
    Compile intel for a run that has claims but no compiled_intel.
    Returns (success, message).
    """
    claims_path = run_path / "claims_deep_research.jsonl"
    template_path = DATA_DIR / "iran_crisis_intel.json"

    if not claims_path.exists():
        return False, "No claims file found"

    if not template_path.exists():
        return False, f"Template not found: {template_path}"

    # Run the compiler
    cmd = [
        sys.executable, "-m", "src.pipeline.compile_intel_v2",
        "--claims", str(claims_path),
        "--template", str(template_path),
        "--out_dir", str(run_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, "Intel compiled successfully!"
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            return False, f"Compilation failed: {error_msg[:500]}"
    except subprocess.TimeoutExpired:
        return False, "Compilation timed out (>120s)"
    except Exception as e:
        return False, f"Error running compiler: {e}"


def trigger_deep_research_pipeline() -> Tuple[bool, str]:
    """
    Trigger full deep research pipeline as background subprocess.
    Uses status file for communication.
    """
    import os
    import time

    # Check for OPENAI_API_KEY
    if not os.getenv('OPENAI_API_KEY'):
        return False, "⚠️ OPENAI_API_KEY not configured. Required for claim extraction."

    status_file = REPO_ROOT / ".pipeline_status.json"

    # Prevent duplicate runs
    if status_file.exists():
        try:
            with open(status_file, 'r') as f:
                status = json.load(f)
            if status.get("status") == "running":
                pid = status.get("pid")
                if pid and is_process_running(pid):
                    return False, f"Pipeline already running (PID: {pid})"
                else:
                    status_file.unlink()
        except Exception:
            status_file.unlink()

    # Build command
    from datetime import datetime, timezone
    cutoff = datetime.now(timezone.utc).isoformat()
    cmd = [
        sys.executable,
        "scripts/daily_update.py",
        "--auto-ingest",
        "--cutoff", cutoff,
    ]

    # Create status file
    status_data = {
        "status": "running",
        "start_time": time.time(),
        "cutoff": cutoff,
        "current_stage": "Initializing"
    }

    # Start background process
    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        status_data["pid"] = process.pid
        with open(status_file, 'w') as f:
            json.dump(status_data, f, indent=2)

        return True, f"✅ Pipeline started (PID: {process.pid})"
    except Exception as e:
        if status_file.exists():
            status_file.unlink()
        return False, f"❌ Failed to start: {str(e)}"


def is_process_running(pid: int) -> bool:
    """Check if process is running."""
    import os
    import signal
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def get_pipeline_status() -> Optional[Dict[str, Any]]:
    """Read pipeline status from file."""
    status_file = REPO_ROOT / ".pipeline_status.json"
    if not status_file.exists():
        return None
    try:
        with open(status_file, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def update_pipeline_status(status: str, error: Optional[str] = None):
    """Update pipeline status file."""
    import time
    status_file = REPO_ROOT / ".pipeline_status.json"
    data = get_pipeline_status() or {}
    data["status"] = status
    data["end_time"] = time.time()
    if error:
        data["error"] = error
    with open(status_file, 'w') as f:
        json.dump(data, f, indent=2)


def display_pipeline_progress_detailed():
    """Display detailed progress with stage tracking."""
    import time

    status = get_pipeline_status()

    if not status:
        st.warning("⚠️ Pipeline status unknown")
        return

    start_time = status.get("start_time", time.time())
    elapsed = int(time.time() - start_time)
    elapsed_min = elapsed // 60
    elapsed_sec = elapsed % 60
    pipeline_status = status.get("status", "unknown")
    pid = status.get("pid")

    # Check if process died
    if pipeline_status == "running" and pid and not is_process_running(pid):
        update_pipeline_status("failed", "Process terminated unexpectedly")
        st.error("❌ Pipeline process terminated. Check logs.")
        if st.button("Clear Status"):
            (REPO_ROOT / ".pipeline_status.json").unlink()
            st.rerun()
        return

    if pipeline_status == "running":
        # Pipeline stages with durations
        stages = [
            ("Fetching Evidence", 180, "ISW, HRANA, Amnesty, BBC Persian, etc."),
            ("Extracting Claims", 300, "GPT-4 API extracts discrete claims"),
            ("Compiling Intel", 120, "Schema-compliant intelligence"),
            ("Running Simulation", 240, "10,000 Monte Carlo simulations"),
            ("Generating Reports", 60, "Visualizations and summaries"),
        ]

        total_duration = sum(s[1] for s in stages)

        # Determine current stage
        cumulative = 0
        current_idx = 0
        for i, (name, duration, desc) in enumerate(stages):
            if elapsed < cumulative + duration:
                current_idx = i
                break
            cumulative += duration
        else:
            current_idx = len(stages) - 1

        # Header
        st.markdown("""
        <div style="background: linear-gradient(135deg, #3B82F6 0%, #1E40AF 100%);
                    border-radius: 10px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; color: white;">
            <h3 style="margin: 0; color: white;">🔄 Deep Research Pipeline Running</h3>
            <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">Takes ~15 minutes. Keep this tab open.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### Pipeline Stages")

        # Display stages
        for i, (name, duration, desc) in enumerate(stages):
            if i < current_idx:
                icon, status_text, color = "✅", "Complete", "#10B981"
            elif i == current_idx:
                icon, status_text, color = "🔄", "In Progress", "#3B82F6"
            else:
                icon, status_text, color = "⏳", "Pending", "#94A3B8"

            st.markdown(f"""
            <div style="padding: 12px; margin: 8px 0; border-left: 3px solid {color};
                        background: #F8FAFC; border-radius: 4px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-weight: 600; color: #0F172A;">{icon} {name}</div>
                        <div style="font-size: 13px; color: #64748B; margin-top: 4px;">{desc}</div>
                    </div>
                    <div style="color: {color}; font-weight: 500; font-size: 14px;">{status_text}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Progress bar
        st.markdown("### Overall Progress")
        progress = min(elapsed / total_duration, 0.99)
        st.progress(progress)

        col1, col2, col3 = st.columns(3)
        col1.metric("Elapsed", f"{elapsed_min}m {elapsed_sec}s")
        col2.metric("Est. Remaining", f"{max(0, (total_duration - elapsed) // 60)}m")
        col3.metric("Process ID", str(pid))

        st.info("💡 Auto-refreshes every 10 seconds. Safe to minimize, but don't close.")

        # Auto-refresh
        if elapsed < 1500:
            time.sleep(10)
            st.rerun()
        else:
            st.warning("⚠️ Pipeline taking >25 min. Check logs.")

    elif pipeline_status == "completed":
        st.success("✅ **Pipeline completed!** Click below to reload dashboard.")
        end_time = status.get("end_time", time.time())
        duration = int(end_time - start_time)
        st.metric("Total Duration", f"{duration // 60}m {duration % 60}s")

        if st.button("🔄 Reload Dashboard", type="primary", use_container_width=True):
            (REPO_ROOT / ".pipeline_status.json").unlink()
            st.cache_data.clear()
            st.rerun()

    elif pipeline_status == "failed":
        error = status.get("error", "Unknown error")
        st.error(f"❌ **Pipeline failed**: {error[:500]}\n\nCheck logs/ for details.")
        if st.button("Clear Error and Retry", type="primary"):
            (REPO_ROOT / ".pipeline_status.json").unlink()
            st.rerun()

    elif pipeline_status == "timeout":
        st.error("⏱️ **Timeout** - Check logs/ for details.")
        if st.button("Clear Status", type="primary"):
            (REPO_ROOT / ".pipeline_status.json").unlink()
            st.rerun()


# =============================================================================
# HISTORICAL PROBABILITY TRACKING
# =============================================================================

def extract_date_from_run_name(name: str) -> Optional[str]:
    """Extract YYYYMMDD date from run folder name like RUN_20260111_v3."""
    match = re.search(r"(\d{8})", name)
    if match:
        return match.group(1)
    return None


def get_historical_probabilities() -> pd.DataFrame:
    """
    Collect outcome probabilities from all dated RUN_* folders.
    Returns DataFrame with columns: date, outcome, probability
    Groups by date and keeps only latest run per day.
    """
    rows = []
    runs_by_date: Dict[str, Tuple[str, Path]] = {}  # date -> (name, path)

    if not RUNS_DIR.exists():
        return pd.DataFrame(columns=["date", "outcome", "probability"])

    # Collect all RUN_* folders (not ADHOC_, not TEST_)
    for f in RUNS_DIR.iterdir():
        if f.is_dir() and f.name.startswith("RUN_"):
            date_str = extract_date_from_run_name(f.name)
            if date_str:
                # Keep latest run per day (by name, which includes version)
                if date_str not in runs_by_date or f.name > runs_by_date[date_str][0]:
                    runs_by_date[date_str] = (f.name, f)

    # Extract probabilities from each run
    for date_str, (name, run_path) in sorted(runs_by_date.items()):
        sim_results = load_json_safe(run_path / "simulation_results.json")
        if sim_results and "outcome_distribution" in sim_results:
            # Parse date
            try:
                date_obj = datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                continue

            for outcome, data in sim_results["outcome_distribution"].items():
                rows.append({
                    "date": date_obj,
                    "outcome": outcome.replace("_", " ").title(),
                    "probability": data["probability"],
                })

    return pd.DataFrame(rows)


def plot_probability_trends(df: pd.DataFrame) -> Optional[go.Figure]:
    """Create line chart of outcome probabilities over time."""
    if df.empty:
        return None

    fig = px.line(
        df,
        x="date",
        y="probability",
        color="outcome",
        markers=True,
        color_discrete_sequence=CHART_COLORS,
        line_shape="spline",
    )
    fig.update_traces(
        line=dict(width=2),
        marker=dict(size=8),
    )
    fig.update_layout(
        font=PLOTLY_THEME['font'],
        paper_bgcolor=PLOTLY_THEME['paper_bgcolor'],
        plot_bgcolor=PLOTLY_THEME['plot_bgcolor'],
        xaxis=PLOTLY_THEME['xaxis'],
        yaxis=PLOTLY_THEME['yaxis'],
        xaxis_title="Date",
        yaxis_title="Probability",
        yaxis_tickformat=".0%",
        height=400,
        legend=dict(
            title=None,
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
        ),
    )
    return fig


# =============================================================================
# VISUALIZATION FUNCTIONS
# =============================================================================

def plot_outcome_distribution(results: Dict[str, Any]) -> go.Figure:
    """Create bar chart of outcome distribution."""
    outcome_dist = results.get("outcome_distribution", {})
    if not outcome_dist:
        return None

    df = pd.DataFrame([
        {
            "Outcome": k.replace("_", " ").title(),
            "Probability": v["probability"],
            "CI Low": v.get("ci_low", 0),
            "CI High": v.get("ci_high", 0),
        }
        for k, v in outcome_dist.items()
    ])
    df = df.sort_values("Probability", ascending=True)

    # Map outcomes to colors
    colors = [OUTCOME_COLORS.get(outcome, '#3B82F6') for outcome in df["Outcome"]]

    fig = go.Figure(go.Bar(
        x=df["Probability"],
        y=df["Outcome"],
        orientation="h",
        text=df["Probability"].apply(lambda x: f"{x:.1%}"),
        textposition="outside",
        marker=dict(
            color=colors,
            line=dict(width=0),
        ),
    ))
    fig.update_layout(
        font=PLOTLY_THEME['font'],
        paper_bgcolor=PLOTLY_THEME['paper_bgcolor'],
        plot_bgcolor=PLOTLY_THEME['plot_bgcolor'],
        xaxis=PLOTLY_THEME['xaxis'],
        yaxis=PLOTLY_THEME['yaxis'],
        xaxis_tickformat=".0%",
        xaxis_title="Probability",
        yaxis_title="",
        height=350,
        showlegend=False,
        bargap=0.3,
    )
    return fig


def display_event_rates(results: Dict[str, Any]):
    """Display key event rates as metrics."""
    rates = results.get("key_event_rates", {})
    if not rates:
        st.info("No event rates available")
        return

    cols = st.columns(len(rates))
    for i, (key, value) in enumerate(rates.items()):
        label = key.replace("_", " ").title()
        cols[i].metric(label, f"{value:.1%}")


def display_regional_rates(results: Dict[str, Any]):
    """Display regional cascade rates if present."""
    rates = results.get("regional_cascade_rates", {})
    if not rates:
        return

    st.subheader("Regional Cascade Rates")
    df = pd.DataFrame([
        {"Event": k.replace("_", " ").title(), "Rate": f"{v:.1%}"}
        for k, v in rates.items()
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)


# =============================================================================
# OBSERVE MODE
# =============================================================================

def render_observe_mode():
    """Render the Observe mode UI."""
    # Page header
    st.markdown("""
        <div style="margin-bottom: 1.5rem;">
            <h2 style="margin: 0; font-size: 24px; font-weight: 600; color: #0F172A;">Observe Mode</h2>
            <p style="margin: 0.25rem 0 0 0; color: #64748B; font-size: 14px;">View results from past simulation runs</p>
        </div>
    """, unsafe_allow_html=True)

    # Sidebar: run selector with test folder toggle
    with st.sidebar:
        st.markdown("""
            <div style="font-size: 11px; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.5rem;">
                Select Run
            </div>
        """, unsafe_allow_html=True)
        include_test = st.checkbox("Include TEST_* folders", value=False)

    run_statuses = list_run_folders_with_status(include_test=include_test)
    if not run_statuses:
        st.warning("No run folders found in `runs/`")
        return

    # Build display names with status indicator
    def format_run_option(status: RunStatus) -> str:
        indicators = {"success": "[OK]", "warning": "[!]", "info": "[~]", "neutral": "[-]"}
        indicator = indicators.get(status.status_variant, "[-]")
        return f"{indicator} {status.name}"

    run_options = [format_run_option(s) for s in run_statuses]
    run_names = [s.name for s in run_statuses]

    with st.sidebar:
        selected_idx = st.selectbox(
            "Run Folder",
            range(len(run_options)),
            index=0,
            format_func=lambda i: run_options[i],
            help="Select a run folder to view results"
        )
        # Status legend
        st.markdown("""
            <div style="font-size: 11px; color: #64748B; margin-top: 0.5rem; line-height: 1.6;">
                <span style="color: #065F46;">[OK]</span> Ready &nbsp;
                <span style="color: #92400E;">[!]</span> Missing Priors<br>
                <span style="color: #1E40AF;">[~]</span> Pending Compile &nbsp;
                <span style="color: #475569;">[-]</span> Import Only
            </div>
        """, unsafe_allow_html=True)

    selected_run = run_names[selected_idx]
    selected_status = run_statuses[selected_idx]
    run_path = RUNS_DIR / selected_run

    # Load artifacts
    qa_report = load_json_safe(run_path / "qa_report.json")
    coverage_report = load_json_safe(run_path / "coverage_report.json")
    sim_results = load_json_safe(run_path / "simulation_results.json")
    source_index = load_json_safe(run_path / "source_index.json")
    diff_report = load_json_safe(run_path / "diff_report.json")

    # Run header card
    status_badge = selected_status.status_badge_html
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #1E3A5F 0%, #0F172A 100%); border-radius: 10px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; color: white;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-size: 12px; opacity: 0.7; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Selected Run</div>
                    <div style="font-size: 20px; font-weight: 600;">{selected_run}</div>
                </div>
                <div>{status_badge}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Executive Summary (if available)
    exec_summary_path = run_path / "visualizations" / "EXECUTIVE_SUMMARY_ONE_PAGE.md"
    exec_summary = load_text_safe(exec_summary_path)
    if exec_summary:
        with st.expander("Executive Summary", expanded=True):
            st.markdown(exec_summary)

    # Status badges row
    st.subheader("Pipeline Status")
    col1, col2, col3 = st.columns(3)

    qa_status = qa_report.get("status") if qa_report else None
    cov_status = coverage_report.get("status") if coverage_report else None

    with col1:
        badge_html = get_status_badge_html(qa_status)
        st.markdown(f'<div><span style="font-weight:500;color:#0F172A;">QA Report</span> {badge_html}</div>', unsafe_allow_html=True)

    with col2:
        badge_html = get_status_badge_html(cov_status)
        st.markdown(f'<div><span style="font-weight:500;color:#0F172A;">Coverage</span> {badge_html}</div>', unsafe_allow_html=True)

    with col3:
        if sim_results:
            n_runs = sim_results.get("n_runs", 0)
            st.markdown(f'<div><span style="font-weight:500;color:#0F172A;">Simulation Runs</span> <span style="color:#3B82F6;font-weight:600;">{n_runs:,}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div><span style="font-weight:500;color:#0F172A;">Simulation</span> {render_badge("Not Run", "neutral")}</div>', unsafe_allow_html=True)

    # Bucket counts
    if coverage_report:
        st.subheader("Source Coverage")
        buckets = coverage_report.get("buckets_found", [])
        total_docs = coverage_report.get("total_docs", 0)
        farsi_docs = coverage_report.get("farsi_docs", 0)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Docs", total_docs)
        col2.metric("Farsi Docs", farsi_docs)
        col3.metric("Source Buckets", len(buckets))

        if buckets:
            st.caption(f"Buckets: {', '.join(buckets)}")
    elif source_index and isinstance(source_index, list):
        st.subheader("Sources")
        st.metric("Source Count", len(source_index))

    # Outcome distribution
    if sim_results:
        st.subheader("Outcome Distribution")
        fig = plot_outcome_distribution(sim_results)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Key Event Rates")
        display_event_rates(sim_results)

        display_regional_rates(sim_results)

    else:
        st.info("No simulation results available for this run")

    # Probability trend chart (across runs)
    st.subheader("Probability Trends Across Runs")
    hist_df = get_historical_probabilities()
    if not hist_df.empty:
        trend_fig = plot_probability_trends(hist_df)
        if trend_fig:
            st.plotly_chart(trend_fig, use_container_width=True)
    else:
        st.caption("Not enough historical data for trend chart (need multiple dated runs)")

    # Diff report
    if diff_report:
        st.subheader("Changes from Previous Run")
        deltas = diff_report.get("outcome_deltas", diff_report.get("deltas", []))
        if isinstance(deltas, list) and deltas:
            df = pd.DataFrame(deltas[:10])
            st.dataframe(df, use_container_width=True, hide_index=True)
        elif isinstance(deltas, dict):
            df = pd.DataFrame([
                {"Outcome": k, "Delta": f"{v:+.1%}" if isinstance(v, (int, float)) else str(v)}
                for k, v in list(deltas.items())[:10]
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("No significant deltas")

    # Report links
    st.subheader("Reports")
    report_html = run_path / "report.html"
    report_md = run_path / "report.md"

    col1, col2 = st.columns(2)
    if report_html.exists():
        col1.markdown(f"`{report_html.relative_to(REPO_ROOT)}`")
    else:
        col1.caption("report.html: not available")

    if report_md.exists():
        col2.markdown(f"`{report_md.relative_to(REPO_ROOT)}`")
    else:
        col2.caption("report.md: not available")


# =============================================================================
# SIMULATE MODE
# =============================================================================

def render_simulate_mode():
    """Render the Simulate mode UI."""
    # Page header
    st.markdown("""
        <div style="margin-bottom: 1.5rem;">
            <h2 style="margin: 0; font-size: 24px; font-weight: 600; color: #0F172A;">Simulate Mode</h2>
            <p style="margin: 0.25rem 0 0 0; color: #64748B; font-size: 14px;">Run ad-hoc simulations with parameter overrides</p>
        </div>
    """, unsafe_allow_html=True)

    # Display most recent executive summary
    exec_summary_path, exec_summary_run = get_latest_executive_summary()
    if exec_summary_path and exec_summary_run:
        exec_summary = load_text_safe(exec_summary_path)
        if exec_summary:
            with st.expander(f"📊 Executive Summary (from {exec_summary_run})", expanded=True):
                st.markdown(exec_summary)
                st.caption(f"Source: `{exec_summary_run}/visualizations/EXECUTIVE_SUMMARY_ONE_PAGE.md`")

    # Auto-select latest simulatable run
    latest_run = get_latest_simulatable_run()

    if not latest_run:
        st.error("No simulatable runs found. Need a run with both intel and priors.")
        return

    source_path = RUNS_DIR / latest_run

    # Sidebar: show current source and refresh button
    with st.sidebar:
        st.markdown("""
            <div style="font-size: 11px; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.5rem;">
                Data Source
            </div>
        """, unsafe_allow_html=True)
        st.markdown(f"""
            <div style="background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 6px; padding: 12px; margin-bottom: 12px;">
                <div style="display: flex; align-items: center;">
                    <div style="width: 8px; height: 8px; background: #22C55E; border-radius: 50%; margin-right: 10px;"></div>
                    <div style="font-size: 14px; color: #166534; font-weight: 500;">{latest_run}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Check pipeline status
        pipeline_status_data = get_pipeline_status()
        is_running = pipeline_status_data and pipeline_status_data.get("status") == "running"

        # Refresh button
        button_label = "🔄 Deep Research Running..." if is_running else "🔄 Refresh Data (~15 min)"
        button_help = "Trigger full deep research pipeline: fetch evidence, extract claims, compile intel, run simulation"

        if st.button(button_label, use_container_width=True, disabled=is_running, type="primary", help=button_help):
            import time
            success, message = trigger_deep_research_pipeline()
            if success:
                st.success(message)
                time.sleep(1)
                st.rerun()
            else:
                st.error(message)

        # Display progress if running
        if is_running:
            display_pipeline_progress_detailed()

    # Load intel and priors
    intel = load_json_safe(source_path / "compiled_intel.json")
    priors = load_json_safe(source_path / "priors_resolved.json")

    if not intel:
        st.error(f"Could not load compiled_intel.json from {latest_run}")
        return
    if not priors:
        st.error(f"Could not load priors_resolved.json from {latest_run}")
        return

    # Sidebar controls for simulation parameters
    with st.sidebar:
        st.divider()
        st.markdown("""
            <div style="font-size: 11px; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.75rem;">
                Simulation Parameters
            </div>
        """, unsafe_allow_html=True)

        max_runs = st.slider(
            "Max Runs",
            min_value=100,
            max_value=2000,
            value=500,
            step=100,
            help="Number of Monte Carlo simulations"
        )

        defection_prob = st.slider(
            "Security Force Defection",
            min_value=0.0,
            max_value=0.30,
            value=0.08,
            step=0.01,
            format="%.2f",
            help="Override defection probability (mode)"
        )

        growth_factor = st.slider(
            "Protest Growth Factor",
            min_value=1.0,
            max_value=2.0,
            value=1.0,
            step=0.1,
            format="%.1f",
            help="Multiply protest sustain/escalate probabilities"
        )

        run_button = st.button("Run Simulation", type="primary", use_container_width=True)

    # Show current source info
    st.success(f"**Source:** {latest_run} — Ready for simulation")

    # Run simulation on button click
    if run_button:
        # Apply overrides
        modified_priors = apply_defection_override(priors, defection_prob)
        modified_priors = apply_growth_factor(modified_priors, growth_factor)

        with st.spinner(f"Running {max_runs} simulations..."):
            results, run_dir = run_adhoc_simulation(intel, modified_priors, max_runs)

        st.success(f"Simulation complete! Results saved to `{run_dir.relative_to(REPO_ROOT)}`")

        # Store results in session state
        st.session_state["sim_results"] = results
        st.session_state["sim_run_dir"] = run_dir

    # Display results if available
    if "sim_results" in st.session_state:
        results = st.session_state["sim_results"]

        # Top 3 outcomes as metric cards
        st.subheader("Top Outcomes")
        outcome_dist = results.get("outcome_distribution", {})
        sorted_outcomes = sorted(
            outcome_dist.items(),
            key=lambda x: x[1]["probability"],
            reverse=True
        )[:3]

        cols = st.columns(3)
        for i, (outcome, data) in enumerate(sorted_outcomes):
            label = outcome.replace("_", " ").title()
            prob = data["probability"]
            ci_low = data.get("ci_low", 0)
            ci_high = data.get("ci_high", 0)
            cols[i].metric(
                label,
                f"{prob:.1%}",
                help=f"95% CI: {ci_low:.1%} - {ci_high:.1%}"
            )

        # Full distribution chart
        st.subheader("Outcome Distribution")
        fig = plot_outcome_distribution(results)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

        # Key event rates
        st.subheader("Key Event Rates")
        display_event_rates(results)

        # Regional rates
        display_regional_rates(results)

    else:
        st.info("Adjust parameters in the sidebar and click 'Run Simulation' to start.")


# =============================================================================
# CAUSAL EXPLORER MODE
# =============================================================================

def render_causal_explorer():
    """Render the interactive Causal DAG explorer using pyvis."""
    st.header("Causal Network Explorer")
    st.caption("Interactive visualization of the Bayesian Network structure")

    if not HAS_CAUSAL_ENGINE:
        st.error("CausalEngine not available. Please ensure pgmpy is installed.")
        return

    try:
        from pyvis.network import Network
        import streamlit.components.v1 as components
    except ImportError:
        st.error("pyvis not available. Install with: pip install pyvis")
        return

    # Load engine
    priors_path = DATA_DIR / "analyst_priors.json"
    cpt_dir = REPO_ROOT / "prompts" / "cpt_derivation" / "responses"

    if not priors_path.exists():
        st.error(f"analyst_priors.json not found at {priors_path}")
        return

    @st.cache_resource
    def load_engine():
        engine = CausalEngine(str(priors_path))
        if cpt_dir.exists():
            engine.load_cpts_from_dir(cpt_dir)
        return engine

    engine = load_engine()

    # Sidebar controls
    with st.sidebar:
        st.subheader("Intervention Settings")
        st.caption("Set evidence to see effects on the network")

        # Evidence selection
        evidence = {}

        # Economic Stress intervention
        econ_stress = st.selectbox(
            "Economic Stress",
            ["(No intervention)", "STABLE", "PRESSURED", "CRITICAL"],
            index=0,
        )
        if econ_stress != "(No intervention)":
            evidence["Economic_Stress"] = econ_stress

        # Security Loyalty intervention
        security = st.selectbox(
            "Security Loyalty",
            ["(No intervention)", "LOYAL", "WAVERING", "DEFECTED"],
            index=0,
        )
        if security != "(No intervention)":
            evidence["Security_Loyalty"] = security

        # Khamenei Health intervention
        khamenei = st.selectbox(
            "Khamenei Health",
            ["(No intervention)", "ALIVE", "DEAD"],
            index=0,
        )
        if khamenei != "(No intervention)":
            evidence["Khamenei_Health"] = khamenei

        # Protest State intervention
        protest = st.selectbox(
            "Protest State",
            ["(No intervention)", "DECLINING", "STABLE", "ESCALATING", "ORGANIZED", "COLLAPSED"],
            index=0,
        )
        if protest != "(No intervention)":
            evidence["Protest_State"] = protest

    # Create network visualization
    net = Network(height="600px", width="100%", directed=True, bgcolor="#0E1117", font_color="white")
    net.toggle_physics(True)
    net.set_options("""
    {
        "nodes": {
            "font": {"size": 12, "face": "Arial"},
            "scaling": {"min": 20, "max": 40}
        },
        "edges": {
            "color": {"color": "#4a5568", "highlight": "#63b3ed"},
            "arrows": {"to": {"enabled": true, "scaleFactor": 0.5}},
            "smooth": {"type": "curvedCW", "roundness": 0.2}
        },
        "physics": {
            "forceAtlas2Based": {
                "gravitationalConstant": -50,
                "centralGravity": 0.01,
                "springLength": 200,
                "springConstant": 0.02
            },
            "solver": "forceAtlas2Based"
        }
    }
    """)

    # Node categories for coloring
    root_nodes = {"Rial_Rate", "Inflation", "Khamenei_Health", "US_Policy_Disposition"}
    terminal_nodes = {"Regime_Outcome"}
    evidence_nodes = set(evidence.keys())

    # Get posteriors if we have evidence
    posteriors = {}
    surprise_data = {}
    if evidence:
        try:
            result = engine.infer_single("Regime_Outcome", evidence)
            posteriors["Regime_Outcome"] = result

            # Get surprise analysis (returns flat dict with surprise_score, surprise_flag, etc.)
            surprise_result = engine.infer_with_surprise("Regime_Outcome", evidence)
            surprise_data = {
                "surprise_score": surprise_result.get("surprise_score", 0),
                "surprise_flag": surprise_result.get("surprise_flag", False),
                "surprise_drivers": surprise_result.get("surprise_drivers", []),
            }
        except Exception as e:
            st.warning(f"Inference error: {e}")

    # Add nodes with colors based on type
    for node, states in ALL_NODES.items():
        # Determine node color
        if node in evidence_nodes:
            color = "#f59e0b"  # Orange for evidence nodes
            title = f"EVIDENCE: {evidence[node]}"
        elif node in root_nodes:
            color = "#10b981"  # Green for root nodes
            title = f"Root node\nStates: {states}"
        elif node in terminal_nodes:
            color = "#ef4444"  # Red for terminal
            title = f"Terminal node\nStates: {states}"
        else:
            color = "#3b82f6"  # Blue for intermediate
            title = f"States: {states}"

        # Add posterior info if available
        if node == "Regime_Outcome" and "Regime_Outcome" in posteriors:
            probs_dict = posteriors["Regime_Outcome"]
            prob_strs = [f"{s}: {probs_dict.get(s, 0)*100:.1f}%" for s in states]
            title += "\n\nPosterior:\n" + "\n".join(prob_strs)

            if surprise_data.get("surprise_flag"):
                title += f"\n\n⚠️ SURPRISE: {surprise_data.get('surprise_score', 0):.2f}"

        net.add_node(node, label=node.replace("_", "\n"), color=color, title=title, size=25)

    # Add edges
    for src, dst in EDGES:
        net.add_edge(src, dst)

    # Generate HTML
    html_content = net.generate_html()

    # Fix the HTML to work in Streamlit iframe
    html_content = html_content.replace(
        '<div id="mynetwork"',
        '<div id="mynetwork" style="background-color: #0E1117;"'
    )

    # Display network
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Causal DAG")
        components.html(html_content, height=650, scrolling=True)

        # Legend
        st.markdown("""
        **Legend:**
        - 🟢 **Green**: Root nodes (observable inputs)
        - 🔵 **Blue**: Intermediate nodes
        - 🔴 **Red**: Terminal outcome
        - 🟠 **Orange**: Evidence (intervention) nodes
        """)

    with col2:
        st.subheader("Inference Results")

        if evidence:
            st.markdown("**Evidence Set:**")
            for node, state in evidence.items():
                st.markdown(f"- {node}: **{state}**")
            st.divider()

            # Show posterior distribution
            if "Regime_Outcome" in posteriors:
                st.markdown("**P(Regime_Outcome | Evidence):**")
                states = ALL_NODES["Regime_Outcome"]
                probs_dict = posteriors["Regime_Outcome"]
                # Convert dict to list in state order
                probs = [probs_dict.get(s, 0) for s in states]

                # Create dataframe for bar chart
                df = pd.DataFrame({
                    "Outcome": [s.replace("_", " ").title() for s in states],
                    "Probability": probs
                })

                fig = px.bar(
                    df, x="Outcome", y="Probability",
                    color="Probability",
                    color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
                    range_color=[0, 1]
                )
                fig.update_layout(
                    showlegend=False,
                    height=300,
                    margin=dict(l=0, r=0, t=10, b=0),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    yaxis_range=[0, 1],
                )
                st.plotly_chart(fig, use_container_width=True)

                # Show surprise analysis
                if surprise_data:
                    st.divider()
                    score = surprise_data.get("surprise_score", 0)
                    flag = surprise_data.get("surprise_flag", False)
                    drivers = surprise_data.get("surprise_drivers", [])

                    if flag:
                        st.warning(f"⚠️ Model Disagreement Detected")
                        st.metric("Surprise Score", f"{score:.2f}", delta=None)
                        if drivers:
                            st.markdown(f"**Drivers:** {', '.join(drivers)}")
                    else:
                        st.success("Model agrees with analyst priors")
                        st.metric("Surprise Score", f"{score:.2f}")

        else:
            st.info("Set evidence in the sidebar to run inference")

            # Show marginal distribution
            st.markdown("**Marginal P(Regime_Outcome):**")
            try:
                marginal_dict = engine.infer_single("Regime_Outcome", {})
                states = ALL_NODES["Regime_Outcome"]
                # Convert dict to list in state order
                marginal = [marginal_dict.get(s, 0) for s in states]

                df = pd.DataFrame({
                    "Outcome": [s.replace("_", " ").title() for s in states],
                    "Probability": marginal
                })

                fig = px.bar(
                    df, x="Outcome", y="Probability",
                    color="Probability",
                    color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
                    range_color=[0, 1]
                )
                fig.update_layout(
                    showlegend=False,
                    height=300,
                    margin=dict(l=0, r=0, t=10, b=0),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    yaxis_range=[0, 1],
                )
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Could not compute marginal: {e}")

        # Sensitivity analysis
        st.divider()
        st.subheader("Sensitivity Analysis")
        try:
            sensitivity = engine.sensitivity("Regime_Outcome")
            if sensitivity:
                df = pd.DataFrame([
                    {"Factor": k, "Influence": v}
                    for k, v in sorted(sensitivity.items(), key=lambda x: -x[1])
                ])
                st.dataframe(df, hide_index=True, use_container_width=True)
        except Exception as e:
            st.warning(f"Sensitivity analysis unavailable: {e}")


# =============================================================================
# MAIN APP
# =============================================================================

def main():
    st.set_page_config(
        page_title="Iran Crisis Simulator - Mission Control",
        page_icon=":chart_with_upwards_trend:",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Inject custom CSS for professional styling
    inject_custom_css()

    st.title("Iran Crisis Simulator")
    st.caption("Mission Control Dashboard")

    # Mode selector in sidebar
    with st.sidebar:
        # Styled sidebar header
        st.markdown("""
            <div style="margin-bottom: 1.5rem;">
                <div style="font-size: 11px; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.5rem;">
                    Dashboard Mode
                </div>
            </div>
        """, unsafe_allow_html=True)
        modes = ["Observe", "Simulate"]
        if HAS_CAUSAL_ENGINE:
            modes.append("Causal")
        mode = st.radio(
            "Select Mode",
            modes,
            index=0,
            label_visibility="collapsed",
            horizontal=True,
        )
        st.divider()

    if mode == "Observe":
        render_observe_mode()
    elif mode == "Simulate":
        render_simulate_mode()
    elif mode == "Causal":
        render_causal_explorer()

    # Explainer section at bottom of sidebar
    with st.sidebar:
        st.divider()
        with st.expander("How This Works"):
            st.markdown(EXPLAINER_TEXT)


if __name__ == "__main__":
    main()
