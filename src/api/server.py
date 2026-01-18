"""
FastAPI server for Iran Simulation React frontend.

This provides REST API endpoints for:
- Running simulations with custom parameters
- Fetching latest results
- Getting system status

Usage:
    cd /Users/personallaptop/iran_simulator/iran_simulation
    uvicorn src.api.server:app --reload --port 8000
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = BASE_DIR / "outputs"

# Import simulation engine - need to set up path properly
import sys
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "src"))

from simulation import IranCrisisSimulation
from priors.contract import resolve_priors

# Import Causal Engine for Bayesian Network
try:
    sys.path.insert(0, str(BASE_DIR / "scripts"))
    from prototype_causal_graph import CausalEngine, ALL_NODES, EDGES
    HAS_CAUSAL_ENGINE = True
except ImportError:
    HAS_CAUSAL_ENGINE = False
    ALL_NODES = {}
    EDGES = []

# CPT directory for calibrated CPTs
CPT_DIR = BASE_DIR / "prompts" / "cpt_derivation" / "responses"

# Default files
DEFAULT_INTEL = DATA_DIR / "iran_crisis_intel.json"
DEFAULT_PRIORS = DATA_DIR / "analyst_priors.json"
DEFAULT_RESULTS = OUTPUTS_DIR / "simulation_results.json"

# App setup
app = FastAPI(
    title="Iran Simulation API",
    description="REST API for Iran Crisis Monte Carlo Simulation",
    version="1.0.0",
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state for tracking simulation status
simulation_state = {
    "is_running": False,
    "last_run_time": None,
    "last_run_duration_ms": None,
    "run_count": 0,
    "last_error": None,
}


# Pydantic models
class SimulationParams(BaseModel):
    runs: int = Field(default=1000, ge=100, le=50000, description="Number of Monte Carlo runs")
    defectionProbability: float = Field(default=0.05, ge=0.0, le=0.5, description="Security force defection probability")
    protestGrowthFactor: float = Field(default=1.5, ge=1.0, le=3.0, description="Protest growth multiplier")


class OutcomeDistribution(BaseModel):
    probability: float
    ci_low: float
    ci_high: float


class EconomicAnalysis(BaseModel):
    stress_level: str
    rial_rate_used: int
    inflation_used: int
    modifiers_applied: Optional[dict] = None


class KeyEventRates(BaseModel):
    us_intervention: float
    security_force_defection: float
    khamenei_death: float
    ethnic_uprising: float


class SimulationResults(BaseModel):
    n_runs: int
    outcome_distribution: dict
    economic_analysis: EconomicAnalysis
    key_event_rates: KeyEventRates
    run_metadata: Optional[dict] = None


class SystemStatus(BaseModel):
    connected: bool
    lastUpdate: str
    isRunning: bool
    runCount: int
    lastRunDuration: Optional[int] = None
    lastError: Optional[str] = None


def load_json(path: Path) -> dict:
    """Load JSON file with error handling."""
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    with open(path, "r") as f:
        return json.load(f)


def transform_results_for_frontend(results: dict, duration_ms: int = None) -> dict:
    """Transform simulation results to match frontend expected format."""
    # Extract key event rates from the results
    key_event_rates = results.get("key_event_rates", {})

    # Get economic analysis if available
    economic = results.get("economic_analysis", {})

    return {
        "n_runs": results.get("n_runs", 0),
        "outcome_distribution": results.get("outcome_distribution", {}),
        "economic_analysis": {
            "stress_level": economic.get("stress_level", "critical"),
            "rial_rate_used": economic.get("rial_rate_used", 1429000),
            "inflation_used": economic.get("inflation_used", 35),
            "modifiers_applied": economic.get("modifiers_applied"),
        },
        "key_event_rates": {
            "us_intervention": key_event_rates.get("us_kinetic_strike", 0) + key_event_rates.get("us_ground_intervention", 0),
            "security_force_defection": key_event_rates.get("security_force_defection", 0),
            "khamenei_death": key_event_rates.get("khamenei_death", 0),
            "ethnic_uprising": key_event_rates.get("ethnic_uprising", 0),
        },
        "run_metadata": {
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat(),
        }
    }


@app.get("/api/status", response_model=SystemStatus)
async def get_status():
    """Get system status including simulation state."""
    return SystemStatus(
        connected=True,
        lastUpdate=datetime.now().isoformat(),
        isRunning=simulation_state["is_running"],
        runCount=simulation_state["run_count"],
        lastRunDuration=simulation_state["last_run_duration_ms"],
        lastError=simulation_state["last_error"],
    )


@app.get("/api/results")
async def get_results():
    """Get the latest simulation results."""
    # Try to load the most recent results
    results_file = DEFAULT_RESULTS

    # Check for other result files and pick the newest
    if OUTPUTS_DIR.exists():
        result_files = list(OUTPUTS_DIR.glob("simulation_results*.json"))
        if result_files:
            results_file = max(result_files, key=lambda p: p.stat().st_mtime)

    results = load_json(results_file)
    return transform_results_for_frontend(results)


@app.post("/api/simulate")
async def run_simulation(params: SimulationParams):
    """Run a new simulation with the given parameters."""
    global simulation_state

    if simulation_state["is_running"]:
        raise HTTPException(status_code=409, detail="A simulation is already running")

    simulation_state["is_running"] = True
    simulation_state["last_error"] = None
    start_time = time.time()

    try:
        # Load intel and priors
        intel = load_json(DEFAULT_INTEL)
        priors = load_json(DEFAULT_PRIORS)

        # Resolve priors
        priors_resolved, priors_qa = resolve_priors(priors)
        if priors_qa.get("status") == "FAIL":
            raise HTTPException(
                status_code=400,
                detail="Priors validation failed: " + "; ".join(priors_qa.get("errors", []))
            )

        # Apply parameter overrides to priors
        # Modify defection probability
        if "transition_probabilities" in priors_resolved:
            tp = priors_resolved["transition_probabilities"]
            if "security_force_defection_given_protests_30d" in tp:
                defection_base = tp["security_force_defection_given_protests_30d"]["probability"]
                # Scale by the user's parameter
                scale_factor = params.defectionProbability / 0.05
                defection_base["mode"] = min(0.5, defection_base.get("mode", 0.05) * scale_factor)
                defection_base["low"] = min(defection_base["mode"], defection_base.get("low", 0.02) * scale_factor)
                defection_base["high"] = min(0.6, defection_base.get("high", 0.1) * scale_factor)

        # Run simulation
        sim = IranCrisisSimulation(intel, priors_resolved)
        results = sim.run_monte_carlo(params.runs)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Save results
        output_file = OUTPUTS_DIR / f"simulation_results_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        OUTPUTS_DIR.mkdir(exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

        # Also update the default results file
        with open(DEFAULT_RESULTS, "w") as f:
            json.dump(results, f, indent=2)

        # Update state
        simulation_state["is_running"] = False
        simulation_state["last_run_time"] = datetime.now().isoformat()
        simulation_state["last_run_duration_ms"] = duration_ms
        simulation_state["run_count"] += 1

        return transform_results_for_frontend(results, duration_ms)

    except HTTPException:
        simulation_state["is_running"] = False
        raise
    except Exception as e:
        simulation_state["is_running"] = False
        simulation_state["last_error"] = str(e)
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")


@app.get("/api/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# =============================================================================
# CAUSAL / BAYESIAN NETWORK ENDPOINTS
# =============================================================================

# Pydantic models for Causal API
class CausalInferenceRequest(BaseModel):
    evidence: dict = Field(default={}, description="Evidence dict mapping node names to states")
    target: str = Field(default="Regime_Outcome", description="Target node for inference")
    include_surprise: bool = Field(default=True, description="Include surprise analysis")


class CausalInferenceResponse(BaseModel):
    posterior: dict
    evidence: dict
    surprise_score: Optional[float] = None
    surprise_flag: Optional[bool] = None
    surprise_drivers: Optional[list] = None


class CausalGraphResponse(BaseModel):
    nodes: dict
    edges: list
    node_categories: dict


class SensitivityResponse(BaseModel):
    target: str
    sensitivities: dict


# Lazy-loaded causal engine singleton
_causal_engine = None


def get_causal_engine():
    """Get or create the CausalEngine singleton."""
    global _causal_engine
    if _causal_engine is None:
        if not HAS_CAUSAL_ENGINE:
            raise HTTPException(status_code=503, detail="CausalEngine not available")
        _causal_engine = CausalEngine(str(DEFAULT_PRIORS))
        if CPT_DIR.exists():
            _causal_engine.load_cpts_from_dir(CPT_DIR)
    return _causal_engine


@app.get("/api/causal/graph", response_model=CausalGraphResponse)
async def get_causal_graph():
    """Get the Bayesian Network structure (nodes and edges)."""
    if not HAS_CAUSAL_ENGINE:
        raise HTTPException(status_code=503, detail="CausalEngine not available")

    # Categorize nodes
    root_nodes = {"Rial_Rate", "Inflation", "Khamenei_Health", "US_Policy_Disposition"}
    terminal_nodes = {"Regime_Outcome"}

    node_categories = {}
    for node in ALL_NODES:
        if node in root_nodes:
            node_categories[node] = "root"
        elif node in terminal_nodes:
            node_categories[node] = "terminal"
        else:
            node_categories[node] = "intermediate"

    return CausalGraphResponse(
        nodes={name: states for name, states in ALL_NODES.items()},
        edges=[{"source": src, "target": dst} for src, dst in EDGES],
        node_categories=node_categories
    )


@app.post("/api/causal/infer", response_model=CausalInferenceResponse)
async def run_causal_inference(request: CausalInferenceRequest):
    """Run Bayesian Network inference with optional evidence."""
    engine = get_causal_engine()

    try:
        if request.include_surprise:
            result = engine.infer_with_surprise(request.target, request.evidence)
            return CausalInferenceResponse(
                posterior=result.get("posterior", {}),
                evidence=request.evidence,
                surprise_score=result.get("surprise_score"),
                surprise_flag=result.get("surprise_flag"),
                surprise_drivers=result.get("surprise_drivers", [])
            )
        else:
            posterior = engine.infer_single(request.target, request.evidence)
            return CausalInferenceResponse(
                posterior=posterior,
                evidence=request.evidence
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Inference failed: {str(e)}")


@app.get("/api/causal/sensitivity/{target}", response_model=SensitivityResponse)
async def get_sensitivity(target: str = "Regime_Outcome"):
    """Get sensitivity analysis for a target node."""
    engine = get_causal_engine()

    try:
        sensitivities = engine.sensitivity(target)
        return SensitivityResponse(
            target=target,
            sensitivities=sensitivities
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sensitivity analysis failed: {str(e)}")


@app.get("/api/causal/status")
async def causal_status():
    """Check if Causal Engine is available."""
    return {
        "available": HAS_CAUSAL_ENGINE,
        "node_count": len(ALL_NODES) if HAS_CAUSAL_ENGINE else 0,
        "edge_count": len(EDGES) if HAS_CAUSAL_ENGINE else 0,
        "cpts_loaded": CPT_DIR.exists() and len(list(CPT_DIR.glob("*.json"))) > 0
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
