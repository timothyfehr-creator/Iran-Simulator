"""Tests for Nobitex fetcher."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def nobitex_config():
    return {
        "id": "nobitex",
        "name": "Nobitex",
        "bucket": "econ_fx",
        "access_grade": "B",
        "bias_grade": 1,
    }


@pytest.fixture
def mock_nobitex_response():
    return {
        "stats": {
            "usdt-rls": {
                "latest": "620000000",
                "dayOpen": "615000000",
                "dayClose": "618000000",
                "dayHigh": "625000000",
                "dayLow": "610000000",
                "volume": "1500.5",
                "date": "1738000000000",
            }
        }
    }


class TestNobitexFetcher:
    def test_fetch_returns_structured_data_in_irr(self, nobitex_config, mock_nobitex_response):
        from src.ingest.fetch_nobitex import NobitexFetcher

        with patch("src.ingest.fetch_nobitex.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_nobitex_response
            mock_resp.raise_for_status.return_value = None
            mock_post.return_value = mock_resp

            fetcher = NobitexFetcher(nobitex_config)
            docs, error = fetcher.fetch()

        assert error is None
        assert len(docs) == 1
        sd = docs[0]["structured_data"]
        assert sd["units"] == "IRR"
        assert sd["usdt_irt_rate"]["latest"] == 620000000.0
        assert sd["source"] == "nobitex"

    def test_empty_stats_returns_empty(self, nobitex_config):
        from src.ingest.fetch_nobitex import NobitexFetcher

        with patch("src.ingest.fetch_nobitex.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"stats": {}}
            mock_resp.raise_for_status.return_value = None
            mock_post.return_value = mock_resp

            fetcher = NobitexFetcher(nobitex_config)
            docs, error = fetcher.fetch()

        assert docs == []

    def test_post_payload(self, nobitex_config, mock_nobitex_response):
        from src.ingest.fetch_nobitex import NobitexFetcher

        with patch("src.ingest.fetch_nobitex.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_nobitex_response
            mock_resp.raise_for_status.return_value = None
            mock_post.return_value = mock_resp

            fetcher = NobitexFetcher(nobitex_config)
            fetcher.fetch()

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["json"] == {"srcCurrency": "usdt", "dstCurrency": "rls"}

    def test_source_timestamp_present(self, nobitex_config, mock_nobitex_response):
        from src.ingest.fetch_nobitex import NobitexFetcher

        with patch("src.ingest.fetch_nobitex.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_nobitex_response
            mock_resp.raise_for_status.return_value = None
            mock_post.return_value = mock_resp

            fetcher = NobitexFetcher(nobitex_config)
            docs, _ = fetcher.fetch()

        sd = docs[0]["structured_data"]
        assert sd["source_timestamp_utc"] is not None
