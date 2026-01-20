# Event Catalog Changelog

## v3.0.0 (2026-01-20)

### Added
- `event_type: binned_continuous` for binned numeric events (keeps `continuous` for backward compat)
- `bin_spec` field with bin definitions (bin_id, min, max, include_min, include_max)
- `enabled` flag to control which events are processed (default: true)
- `requires_manual_resolution` workflow flag for manual queue events
- `horizons_days` array per event for event-specific horizon configuration
- `forecast_source.type` now supports: `baseline_persistence`, `baseline_climatology`
- `resolution_source.rule` now supports: `bin_map`, `enum_match`
- New `src/forecasting/bins.py` module for bin validation and value-to-bin mapping
- Extended catalog validation for v3.0.0 features
- `validate_distribution()` function for probability validation in forecast.py
- `generate_baseline_distribution()` for MVP baseline events (uniform fallback)
- 13 new events total:
  - **MVP Events (enabled: true):**
    - `econ.fx_band` - FX black-market band (binned_continuous, auto-resolve)
    - `info.internet_level` - National internet status (categorical, auto-resolve)
    - `protest.multi_city` - Multi-city protests (binary, manual queue)
  - **Non-MVP Events (enabled: false):**
    - `econ.inflation_band` - Inflation severity band
    - `econ.bank_stress` - Banking system stress level
    - `protest.freq_band` - Protest frequency band
    - `protest.trend_level` - Protest intensity trend
    - `security.arrest_wave` - Mass arrest wave
    - `security.lethal_band` - Lethal force severity band
    - `info.platform_blocks` - Platform blocking status
    - `external.strike_level` - External military strike threat level
    - `external.maritime_band` - Maritime tension band
    - `energy.export_band` - Oil export volume band

### Changed
- Event definitions now require `effective_from_utc` for new binned_continuous events
- `get_forecastable_events()` now filters by `enabled: true` in addition to non-diagnostic
- `resolve_pending()` now skips `requires_manual_resolution: true` events
- `apply_resolution_rule()` now requires full event object for bin_map/enum_match rules
- Binary events now allow `UNKNOWN` in allowed_outcomes (for v3+ events)

### Schema Updates
- `event_catalog.schema.json`: Added bin_spec, horizons_days, enabled, requires_manual_resolution
- `forecast_record.schema.json`: Added `binned_continuous` to distribution_type enum
- Category enum expanded to include `energy`

### Migration Notes
- Existing Phase 2 events are unchanged (backward compatible)
- Non-MVP events have `enabled: false` and will not be processed until Phase 3B scoring
- Events with `requires_manual_resolution: true` stay in pending queue until manual resolution

---

## v2.0.0 (2026-01-20)

### Added
- `auto_resolve` field for external auto-resolution
- `effective_from_utc` optional field (for new events only)
- Resolution records now require `resolution_mode`, `reason_code`, `evidence_refs`, `evidence_hashes`
- Conditional requirement: `adjudicator_id` required when `resolution_mode == "external_manual"`

### Changed
- `catalog_version` now uses SemVer (X.Y.Z) format
- Added `auto_resolve: true` to events:
  - `econ.rial_ge_1_2m` - Rial black-market threshold
  - `econ.inflation_ge_50` - Official inflation threshold
  - `state.internet_degraded` - Internet status check

### Resolution Modes
- `external_auto`: Automated resolution using compiled intel data paths
- `external_manual`: Human adjudicator resolved with required `adjudicator_id`
- `claims_inferred`: Resolution inferred from claims (fallback mode)

## v1.0 (2026-01-15)

### Initial Release
- Initial catalog with 5 events:
  - `econ.rial_ge_1_2m` - Rial exchange rate threshold
  - `econ.inflation_ge_50` - Official inflation threshold
  - `event.security_defection` - Security force defection
  - `state.internet_degraded` - Internet blackout/degradation
  - `state.protests_escalating` - Protest intensity trend
- Basic resolution source definitions
- Forecast source mappings to simulation outputs
