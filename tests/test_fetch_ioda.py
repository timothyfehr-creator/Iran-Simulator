"""Tests for IODA fetcher."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingest.fetch_ioda import IODAFetcher


class TestIODAFetcher:
    """Test suite for IODA Internet Connectivity fetcher."""

    @pytest.fixture
    def config(self):
        """Basic source configuration for IODA."""
        return {
            "id": "ioda",
            "name": "IODA Internet Observatory",
            "access_grade": "A",
            "bias_grade": 1,
            "bucket": "internet_monitoring",
            "urls": ["https://api.ioda.inetintel.cc.gatech.edu/v2/signals/raw/country/IR"],
        }

    def test_normalize_score_normal(self, config):
        """Test normalization when connectivity is at baseline."""
        fetcher = IODAFetcher(config)
        signal = {"value": 100, "baseline": 100}
        assert fetcher._normalize_score(signal) == 100.0

    def test_normalize_score_outage(self, config):
        """Test normalization during partial outage (50% of baseline)."""
        fetcher = IODAFetcher(config)
        signal = {"value": 50, "baseline": 100}
        assert fetcher._normalize_score(signal) == 50.0

    def test_normalize_score_zero_baseline(self, config):
        """Test normalization with zero baseline (edge case)."""
        fetcher = IODAFetcher(config)
        signal = {"value": 50, "baseline": 0}
        # Should return 100 when baseline is zero to avoid division by zero
        assert fetcher._normalize_score(signal) == 100.0

    def test_normalize_score_above_baseline(self, config):
        """Test normalization when connectivity exceeds baseline."""
        fetcher = IODAFetcher(config)
        signal = {"value": 120, "baseline": 100}
        # Should be capped at 100
        assert fetcher._normalize_score(signal) == 100.0

    def test_normalize_score_severe_outage(self, config):
        """Test normalization during severe outage (10% of baseline)."""
        fetcher = IODAFetcher(config)
        signal = {"value": 10, "baseline": 100}
        assert fetcher._normalize_score(signal) == 10.0

    @patch('src.ingest.fetch_ioda._session.get')
    def test_fetch_success(self, mock_get, config):
        """Test successful fetch from IODA API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                [
                    {
                        "datasource": "gtr-norm",
                        "values": [0.85],
                        "until": 1705500000,
                    }
                ]
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        fetcher = IODAFetcher(config)
        docs, error = fetcher.fetch()

        assert error is None
        assert len(docs) == 1
        assert "connectivity" in docs[0]["raw_text"].lower()
        assert docs[0]["structured_data"]["connectivity_index"] == 85.0

    @patch('src.ingest.fetch_ioda._session.get')
    def test_fetch_empty_data(self, mock_get, config):
        """Test fetch when API returns no data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        fetcher = IODAFetcher(config)
        docs, error = fetcher.fetch()

        assert error is None
        assert len(docs) == 0

    @patch('src.ingest.fetch_ioda._session.get')
    def test_fetch_multiple_signals(self, mock_get, config):
        """Test fetch with multiple datasources - should prefer gtr-norm."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                [
                    {
                        "datasource": "bgp",
                        "values": [90],
                        "until": 1705500000,
                    },
                    {
                        "datasource": "gtr-norm",
                        "values": [0.70],
                        "until": 1705500000,
                    },
                ]
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        fetcher = IODAFetcher(config)
        docs, error = fetcher.fetch()

        assert error is None
        assert len(docs) == 1
        # Should use gtr-norm datasource (0.70 * 100 = 70.0)
        assert docs[0]["structured_data"]["connectivity_index"] == 70.0

    @patch('src.ingest.fetch_ioda._session.get')
    def test_fetch_api_error(self, mock_get, config):
        """Test fetch when API returns an error."""
        mock_get.side_effect = Exception("API connection failed")

        fetcher = IODAFetcher(config)
        docs, error = fetcher.fetch()

        # Should return error after retries
        assert error is not None
        assert len(docs) == 0

    def test_evidence_doc_structure(self, config):
        """Test that evidence doc has required fields."""
        fetcher = IODAFetcher(config)

        with patch('src.ingest.fetch_ioda._session.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [
                    [
                        {
                            "datasource": "gtr-norm",
                            "values": [0.85],
                            "until": 1705500000,
                        }
                    ]
                ]
            }
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            docs, _ = fetcher.fetch()

            assert len(docs) == 1
            doc = docs[0]

            # Check required fields
            assert "doc_id" in doc
            assert "source_id" in doc
            assert "title" in doc
            assert "url" in doc
            assert "published_at_utc" in doc
            assert "retrieved_at_utc" in doc
            assert "raw_text" in doc
            assert "language" in doc
            assert "structured_data" in doc

            # Check source grading
            assert doc["access_grade"] == "A"
            assert doc["bias_grade"] == 1
