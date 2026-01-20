"""
Oracle Layer - Forecasting and Scoring System.

Provides observe-only forecasting, resolution, and scoring capabilities
that never modify simulation logic.

Modules:
    catalog - Event catalog loading and validation
    ledger - Append-only JSONL storage for forecasts and resolutions
    forecast - Forecast generation from simulation outputs
    resolver - Resolution logic using future runs
    evidence - Evidence snapshot storage with hashing
    scorer - Brier/log scoring and calibration metrics
    reporter - JSON and markdown report generation
    cli - Command-line interface entrypoints
"""

from . import catalog
from . import ledger
from . import forecast
from . import resolver
from . import evidence
from . import scorer
from . import reporter
from . import cli

__version__ = "2.0.0"
