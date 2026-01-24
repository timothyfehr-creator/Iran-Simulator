"""
Command-line interface for Oracle forecasting system.

Provides subcommands for logging forecasts, resolving outcomes,
computing scores, and generating reports.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from . import catalog
from . import forecast
from . import resolver
from . import scorer
from . import reporter
from . import ledger


def cmd_log(args: argparse.Namespace) -> int:
    """Log forecasts from a simulation run."""
    try:
        run_dir = Path(args.run_dir) if args.run_dir else None
        horizons = [args.horizon] if args.horizon else None

        records = forecast.generate_forecasts(
            catalog_path=Path(args.catalog),
            runs_dir=Path(args.runs_dir),
            run_dir=run_dir,
            horizons=horizons,
            ledger_dir=Path(args.ledger_dir),
            dry_run=args.dry_run,
            with_ensembles=args.with_ensembles,
        )

        # Count base vs ensemble forecasts
        base_count = sum(1 for r in records if "ensemble" not in r.get("forecaster_id", ""))
        ensemble_count = len(records) - base_count

        if ensemble_count > 0:
            print(f"Generated {base_count} base forecast(s) + {ensemble_count} ensemble forecast(s)")
        else:
            print(f"Generated {len(records)} forecast(s)")

        if args.verbose:
            for r in records:
                p_yes = r.get("probabilities", {}).get("YES", 0)
                status = "ABSTAIN" if r.get("abstain") else f"P(YES)={p_yes:.3f}"
                print(f"  {r['event_id']} [{r['horizon_days']}d]: {status}")

        if args.dry_run:
            print("(dry run - no records written)")

        return 0

    except forecast.ForecastError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_resolve(args: argparse.Namespace) -> int:
    """Resolve pending forecasts."""
    try:
        records = resolver.resolve_pending(
            catalog_path=Path(args.catalog),
            runs_dir=Path(args.runs_dir),
            ledger_dir=Path(args.ledger_dir),
            max_lag_days=args.max_lag,
            dry_run=args.dry_run,
        )

        print(f"Resolved {len(records)} forecast(s)")

        if args.verbose:
            for r in records:
                outcome = r.get("resolved_outcome", "UNKNOWN")
                unknown = r.get("unknown_reason", "")
                status = f"{outcome}" + (f" ({unknown})" if unknown else "")
                print(f"  {r['event_id']}: {status}")

        if args.dry_run:
            print("(dry run - no records written)")

        return 0

    except resolver.ResolutionError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_score(args: argparse.Namespace) -> int:
    """Compute scoring metrics."""
    try:
        scores = scorer.compute_scores(
            ledger_dir=Path(args.ledger_dir),
            event_id=args.event_id,
            horizon_days=args.horizon,
        )

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(scores, f, indent=2)
            print(f"Scores written to {args.output}")
        else:
            print(json.dumps(scores, indent=2))

        return 0

    except scorer.ScoringError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_report(args: argparse.Namespace) -> int:
    """Generate score reports."""
    try:
        outputs = reporter.generate_report(
            ledger_dir=Path(args.ledger_dir),
            reports_dir=Path(args.reports_dir),
            output_format=args.format,
            event_id=args.event_id,
            horizon_days=args.horizon,
        )

        for fmt, path in outputs.items():
            print(f"Generated {fmt} report: {path}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show forecast status summary."""
    try:
        status = reporter.generate_status_report(
            ledger_dir=Path(args.ledger_dir)
        )

        print("Oracle Forecast Status")
        print("=" * 40)
        print(f"Total forecasts:  {status['total_forecasts']}")
        print(f"Total resolved:   {status['total_resolutions']}")
        print(f"Pending:          {status['pending_count']}")
        print(f"Coverage rate:    {status['coverage_rate']:.1%}")
        print()

        if status['by_event']:
            print("By Event:")
            for event_id, counts in sorted(status['by_event'].items()):
                print(f"  {event_id}: {counts['resolved']}/{counts['total']} resolved")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_validate_catalog(args: argparse.Namespace) -> int:
    """Validate event catalog."""
    try:
        cat = catalog.load_catalog(Path(args.catalog))
        catalog.validate_catalog(cat)

        events = cat.get("events", [])
        forecastable = catalog.get_forecastable_events(cat)
        diagnostic = catalog.get_diagnostic_events(cat)

        print(f"Catalog valid: {args.catalog}")
        print(f"  Version: {cat.get('catalog_version')}")
        print(f"  Total events: {len(events)}")
        print(f"  Forecastable: {len(forecastable)}")
        print(f"  Diagnostic: {len(diagnostic)}")

        if args.verbose:
            print("\nEvents:")
            for e in events:
                src_type = e.get("forecast_source", {}).get("type", "unknown")
                print(f"  {e['event_id']}: {e['name']} [{src_type}]")

        return 0

    except catalog.CatalogValidationError as e:
        print(f"Validation failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_queue(args: argparse.Namespace) -> int:
    """Show forecasts awaiting resolution."""
    from datetime import datetime, timezone

    try:
        pending = ledger.get_pending_forecasts(Path(args.ledger_dir))
        now = datetime.now(timezone.utc)

        # Filter to due forecasts (target_date <= now)
        due_forecasts = []
        for f in pending:
            target_str = f.get("target_date_utc")
            if not target_str:
                continue

            # Parse target date
            target_str = target_str.replace('Z', '+00:00')
            try:
                target_date = datetime.fromisoformat(target_str)
                if target_date.tzinfo is None:
                    target_date = target_date.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            # Check if due
            if target_date <= now:
                days_overdue = (now - target_date).days
                due_forecasts.append({
                    "forecast": f,
                    "target_date": target_date,
                    "days_overdue": days_overdue,
                })

        # Sort by most overdue first
        due_forecasts.sort(key=lambda x: x["days_overdue"], reverse=True)

        if not due_forecasts:
            print("No forecasts due for resolution.")
            return 0

        print(f"Forecasts awaiting resolution: {len(due_forecasts)}")
        print()
        print(f"{'Event ID':<30} {'Horizon':<10} {'Target Date':<12} {'Overdue':<10}")
        print("-" * 62)

        for item in due_forecasts:
            f = item["forecast"]
            event_id = f.get("event_id", "unknown")
            horizon = f.get("horizon_days", 0)
            target_date = item["target_date"].strftime("%Y-%m-%d")
            days_overdue = item["days_overdue"]

            overdue_str = f"{days_overdue}d" if days_overdue > 0 else "today"
            print(f"{event_id:<30} {horizon:<10} {target_date:<12} {overdue_str:<10}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main(argv: Optional[list] = None) -> int:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="forecast",
        description="Oracle Layer - Forecasting and Scoring System"
    )

    # Global options
    parser.add_argument(
        "--catalog",
        default="config/event_catalog.json",
        help="Path to event catalog"
    )
    parser.add_argument(
        "--runs-dir",
        default="runs",
        help="Path to runs directory"
    )
    parser.add_argument(
        "--ledger-dir",
        default="forecasting/ledger",
        help="Path to ledger directory"
    )
    parser.add_argument(
        "--reports-dir",
        default="forecasting/reports",
        help="Path to reports directory"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # log command
    log_parser = subparsers.add_parser("log", help="Log forecasts from simulation run")
    log_parser.add_argument("--run-dir", help="Specific run directory (auto-selects if omitted)")
    log_parser.add_argument("--horizon", type=int, choices=[1, 7, 15, 30], help="Specific horizon")
    log_parser.add_argument("--dry-run", action="store_true", help="Don't write to ledger")
    log_parser.add_argument("--with-ensembles", action="store_true",
                           help="Generate ensemble forecasts after base forecasts")
    log_parser.set_defaults(func=cmd_log)

    # resolve command
    resolve_parser = subparsers.add_parser("resolve", help="Resolve pending forecasts")
    resolve_parser.add_argument("--max-lag", type=int, default=14, help="Max resolution lag days")
    resolve_parser.add_argument("--dry-run", action="store_true", help="Don't write to ledger")
    resolve_parser.set_defaults(func=cmd_resolve)

    # score command
    score_parser = subparsers.add_parser("score", help="Compute scoring metrics")
    score_parser.add_argument("--event-id", help="Filter by event ID")
    score_parser.add_argument("--horizon", type=int, help="Filter by horizon")
    score_parser.add_argument("--output", "-o", help="Output file (JSON)")
    score_parser.set_defaults(func=cmd_score)

    # report command
    report_parser = subparsers.add_parser("report", help="Generate score reports")
    report_parser.add_argument("--format", choices=["json", "md", "both"], default="both")
    report_parser.add_argument("--event-id", help="Filter by event ID")
    report_parser.add_argument("--horizon", type=int, help="Filter by horizon")
    report_parser.set_defaults(func=cmd_report)

    # status command
    status_parser = subparsers.add_parser("status", help="Show forecast status")
    status_parser.set_defaults(func=cmd_status)

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate event catalog")
    validate_parser.set_defaults(func=cmd_validate_catalog)

    # queue command
    queue_parser = subparsers.add_parser("queue", help="Show forecasts awaiting resolution")
    queue_parser.add_argument("--due-only", action="store_true", default=True,
                              help="Only show overdue forecasts (default)")
    queue_parser.set_defaults(func=cmd_queue)

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
