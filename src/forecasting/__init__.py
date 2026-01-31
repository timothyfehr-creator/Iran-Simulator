"""
Oracle Layer - Forecasting and Scoring System.

Provides observe-only forecasting, resolution, and scoring capabilities
that never modify simulation logic.

Modules:
    catalog - Event catalog loading and validation
    bins - Bin validation and value-to-bin mapping for binned events
    ledger - Append-only JSONL storage for forecasts and resolutions
    forecast - Forecast generation from simulation outputs
    resolver - Resolution logic using future runs
    evidence - Evidence snapshot storage with hashing
    scorer - Brier/log scoring and calibration metrics
    reporter - JSON and markdown report generation
    ensembles - Static ensemble forecaster generation
    baseline_history - History-based baseline forecasters (Phase 3D-2)
    cli - Command-line interface entrypoints
"""

from . import catalog
from . import bins
from . import ledger
from . import forecast
from . import resolver
from . import evidence
from . import scorer
from . import reporter
from . import ensembles
from . import baseline_history
from . import cli

__version__ = "3.1.0"
