# Event Catalog Changelog

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
