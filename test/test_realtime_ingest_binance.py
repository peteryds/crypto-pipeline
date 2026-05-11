import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from aws import realtime_ingest_binance


class TestRealtimeIngestBinance(unittest.TestCase):
    def test_get_previous_minute_window_ms(self):
        now = datetime(2026, 5, 11, 20, 14, 41, tzinfo=timezone.utc)
        start_ms, end_ms = realtime_ingest_binance.get_previous_minute_window_ms(now)

        self.assertEqual(start_ms, 1778530380000)
        self.assertEqual(end_ms, 1778530439999)

    @patch("aws.realtime_ingest_binance.time.sleep")
    @patch("aws.realtime_ingest_binance.requests.get")
    def test_fetch_binance_json_retries_rate_limit(self, mock_get, mock_sleep):
        rate_limited_response = Mock()
        rate_limited_response.status_code = 429
        rate_limited_response.headers = {"Retry-After": "1"}

        success_response = Mock()
        success_response.status_code = 200
        success_response.headers = {}
        success_response.raise_for_status.return_value = None
        success_response.json.return_value = [{"id": 1}]

        mock_get.side_effect = [rate_limited_response, success_response]

        payload = realtime_ingest_binance.fetch_binance_json(
            "/api/v3/aggTrades",
            {"symbol": "BTCUSDC"},
            max_retries=3,
        )

        self.assertEqual(payload, [{"id": 1}])
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
