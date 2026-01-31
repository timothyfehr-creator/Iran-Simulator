"""
Tests for diff report generation with new fields.

Workstream 6: Diff Report Improvements
Verifies contested_claims, coverage_deltas, and health_deltas in diff report.
"""

import pytest

from src.pipeline.run_comparator import (
    compute_coverage_deltas,
    compute_health_deltas,
    extract_contested_claims
)
from src.report.generate_diff_report import (
    format_coverage_deltas,
    format_health_deltas,
    format_contested_claims
)


class TestCoverageDeltas:
    """Tests for coverage delta computation."""

    def test_compute_buckets_missing_now(self):
        """Should identify newly missing buckets."""
        current = {
            'buckets_missing': ['regime_outlets', 'persian_services'],
            'buckets_present': ['osint_thinktank', 'ngo_rights']
        }
        previous = {
            'buckets_missing': ['regime_outlets'],
            'buckets_present': ['osint_thinktank', 'ngo_rights', 'persian_services']
        }

        deltas = compute_coverage_deltas(current, previous)

        assert 'persian_services' in deltas['buckets_missing_now']
        assert 'persian_services' in deltas['buckets_lost']

    def test_compute_buckets_recovered(self):
        """Should identify buckets that are no longer missing."""
        current = {
            'buckets_missing': ['regime_outlets'],
            'buckets_present': ['osint_thinktank', 'ngo_rights', 'persian_services']
        }
        previous = {
            'buckets_missing': ['regime_outlets', 'persian_services'],
            'buckets_present': ['osint_thinktank', 'ngo_rights']
        }

        deltas = compute_coverage_deltas(current, previous)

        assert 'persian_services' in deltas['buckets_recovered']
        assert 'persian_services' in deltas['buckets_missing_prev']

    def test_compute_deltas_with_no_previous(self):
        """Should handle missing previous coverage."""
        current = {
            'buckets_missing': ['regime_outlets'],
            'buckets_present': ['osint_thinktank']
        }

        deltas = compute_coverage_deltas(current, None)

        # All missing are "new" when no previous
        assert 'regime_outlets' in deltas['buckets_missing_now']

    def test_status_change_tracked(self):
        """Should track status changes."""
        current = {'buckets_missing': [], 'buckets_present': ['a'], 'status': 'PASS'}
        previous = {'buckets_missing': ['b'], 'buckets_present': [], 'status': 'WARN'}

        deltas = compute_coverage_deltas(current, previous)

        assert deltas['status_current'] == 'PASS'
        assert deltas['status_previous'] == 'WARN'


class TestHealthDeltas:
    """Tests for health delta computation."""

    def test_ok_to_degraded_transition(self):
        """Should detect OK -> DEGRADED transition."""
        current = {
            'health_summary': {
                'degraded_sources': ['hrana'],
                'down_sources': [],
                'overall_status': 'DEGRADED'
            }
        }
        previous = {
            'health_summary': {
                'degraded_sources': [],
                'down_sources': [],
                'overall_status': 'OK'
            }
        }

        deltas = compute_health_deltas(current, previous)

        transitions = deltas['transitions']
        hrana_transition = next((t for t in transitions if t['source'] == 'hrana'), None)

        assert hrana_transition is not None
        assert hrana_transition['from'] == 'OK'
        assert hrana_transition['to'] == 'DEGRADED'

    def test_degraded_to_down_transition(self):
        """Should detect DEGRADED -> DOWN transition."""
        current = {
            'health_summary': {
                'degraded_sources': [],
                'down_sources': ['isw'],
                'overall_status': 'DOWN'
            }
        }
        previous = {
            'health_summary': {
                'degraded_sources': ['isw'],
                'down_sources': [],
                'overall_status': 'DEGRADED'
            }
        }

        deltas = compute_health_deltas(current, previous)

        transitions = deltas['transitions']
        isw_transition = next((t for t in transitions if t['source'] == 'isw'), None)

        assert isw_transition is not None
        assert isw_transition['from'] == 'DEGRADED'
        assert isw_transition['to'] == 'DOWN'

    def test_down_to_ok_recovery(self):
        """Should detect DOWN -> OK recovery."""
        current = {
            'health_summary': {
                'degraded_sources': [],
                'down_sources': [],
                'overall_status': 'OK'
            }
        }
        previous = {
            'health_summary': {
                'degraded_sources': [],
                'down_sources': ['irna'],
                'overall_status': 'DOWN'
            }
        }

        deltas = compute_health_deltas(current, previous)

        transitions = deltas['transitions']
        irna_transition = next((t for t in transitions if t['source'] == 'irna'), None)

        assert irna_transition is not None
        assert irna_transition['from'] == 'DOWN'
        assert irna_transition['to'] == 'OK'

    def test_overall_status_tracked(self):
        """Should track overall health status."""
        current = {
            'health_summary': {'overall_status': 'DEGRADED', 'degraded_sources': ['a'], 'down_sources': []}
        }

        deltas = compute_health_deltas(current, None)

        assert deltas['overall_status'] == 'DEGRADED'


class TestContestedClaims:
    """Tests for contested claims extraction."""

    def test_extract_conflict_group_claims(self):
        """Should extract claims with actual conflicts."""
        merge_report = {
            'merge_notes': [
                {
                    'path': 'economic.inflation_rate',
                    'conflict': True,
                    'winner_claim_id': 'claim_123',
                    'conflicting_values': [35, 42],
                    'reason': 'source_grade tie with materially different values',
                    'candidates': 2
                }
            ]
        }

        contested = extract_contested_claims(merge_report)

        assert len(contested) == 1
        assert contested[0]['path'] == 'economic.inflation_rate'
        assert 'tie' in contested[0]['reason'].lower()

    def test_extract_high_candidate_claims(self):
        """Should extract claims with high candidate count."""
        merge_report = {
            'merge_notes': [
                {
                    'path': 'security.irgc_loyalty',
                    'conflict': False,
                    'winner_claim_id': 'claim_456',
                    'candidates': 5,
                    'all_candidates': [
                        {'claim_id': 'c1'}, {'claim_id': 'c2'},
                        {'claim_id': 'c3'}, {'claim_id': 'c4'},
                        {'claim_id': 'c5'}
                    ]
                }
            ]
        }

        contested = extract_contested_claims(merge_report)

        assert len(contested) == 1
        assert contested[0]['candidates'] == 5
        assert 'High candidate count' in contested[0]['reason']

    def test_single_candidate_not_contested(self):
        """Should not mark single-candidate paths as contested."""
        merge_report = {
            'merge_notes': [
                {
                    'path': 'simple.path',
                    'conflict': False,
                    'winner_claim_id': 'claim_789',
                    'candidates': 1
                }
            ]
        }

        contested = extract_contested_claims(merge_report)

        assert len(contested) == 0


class TestDiffReportFormatting:
    """Tests for Markdown formatting of new diff fields."""

    def test_format_coverage_deltas_with_lost_buckets(self):
        """Should format lost buckets clearly."""
        deltas = {
            'buckets_lost': ['regime_outlets'],
            'buckets_recovered': []
        }

        formatted = format_coverage_deltas(deltas)

        assert 'Buckets Now Missing' in formatted
        assert 'regime_outlets' in formatted

    def test_format_coverage_deltas_with_recovered_buckets(self):
        """Should format recovered buckets with checkmark."""
        deltas = {
            'buckets_lost': [],
            'buckets_recovered': ['persian_services']
        }

        formatted = format_coverage_deltas(deltas)

        assert 'Buckets Recovered' in formatted
        assert 'persian_services' in formatted

    def test_format_health_deltas_with_down_transition(self):
        """Should highlight DOWN transitions with warning."""
        deltas = {
            'transitions': [
                {'source': 'isw', 'from': 'OK', 'to': 'DOWN'}
            ],
            'overall_status': 'DOWN'
        }

        formatted = format_health_deltas(deltas)

        assert 'DOWN' in formatted
        assert 'isw' in formatted

    def test_format_contested_claims_shows_conflicts(self):
        """Should format conflict claims."""
        contested = [
            {
                'path': 'economic.inflation_rate',
                'reason': 'source_grade tie with different values',
                'candidates': 2
            }
        ]

        formatted = format_contested_claims(contested)

        assert 'Conflicting Claims' in formatted
        assert 'Inflation Rate' in formatted  # Title cased

    def test_format_empty_returns_empty(self):
        """Empty data should return empty string."""
        assert format_coverage_deltas({}) == ""
        assert format_health_deltas({}) == ""
        assert format_contested_claims([]) == ""


class TestDiffReportSchema:
    """Tests for diff report schema compliance with plan."""

    def test_coverage_deltas_has_required_fields(self):
        """Coverage deltas should have buckets_missing_now/prev."""
        current = {'buckets_missing': ['a'], 'buckets_present': ['b']}

        deltas = compute_coverage_deltas(current, None)

        assert 'buckets_missing_now' in deltas
        assert 'buckets_missing_prev' in deltas

    def test_health_deltas_has_required_fields(self):
        """Health deltas should have overall_status and transitions."""
        current = {
            'health_summary': {'overall_status': 'OK', 'degraded_sources': [], 'down_sources': []}
        }

        deltas = compute_health_deltas(current, None)

        assert 'overall_status' in deltas
        assert 'transitions' in deltas

    def test_contested_claim_has_required_fields(self):
        """Contested claims should have path, conflict_group, winner."""
        merge_report = {
            'merge_notes': [
                {
                    'path': 'test.path',
                    'conflict': True,
                    'winner_claim_id': 'winner',
                    'conflicting_values': [1, 2],
                    'reason': 'tie',
                    'candidates': 2
                }
            ]
        }

        contested = extract_contested_claims(merge_report)

        assert len(contested) == 1
        assert 'path' in contested[0]
        assert 'conflict_group' in contested[0]
        assert 'winner' in contested[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
