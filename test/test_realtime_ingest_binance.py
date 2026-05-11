import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from aws import realtime_ingest_binance


class TestRealtimeIngestBinance(unittest.TestCase):
    def test_get_previous_minute_window_ms(self):
        now = datetime(2026, 5, 11, 20, 14, 41, tzinfo=timezone.utc)
        start_ms, end_ms = realtime_ingest_binance.get_previous_minute_window_ms(now)
        expected_start = int(datetime(2026, 5, 11, 20, 13, 0, tzinfo=timezone.utc).timestamp() * 1000)
        expected_end = int(datetime(2026, 5, 11, 20, 13, 59, 999000, tzinfo=timezone.utc).timestamp() * 1000)

        self.assertEqual(start_ms, expected_start)
        self.assertEqual(end_ms, expected_end)

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

    @patch("aws.realtime_ingest_binance.upload_to_s3")
    @patch("aws.realtime_ingest_binance.fetch_binance_json")
    @patch("aws.realtime_ingest_binance.get_previous_minute_window_ms")
    def test_lambda_handler_uses_windowed_klines_and_lands_agg_trades(
        self,
        mock_window,
        mock_fetch,
        mock_upload,
    ):
        mock_window.return_value = (1000, 1999)
        mock_fetch.side_effect = [[[1, 2, 3, 4, 5]], [{"a": 1}]]

        class StorageStub:
            def check_config(self):
                return True

        class ExchangeStub:
            def fetch_open_orders(self, symbol):
                return []

            def fetch_my_trades(self, symbol, limit=50):
                return []

        with patch.object(realtime_ingest_binance, "storage", StorageStub()), patch.object(
            realtime_ingest_binance, "exchange", ExchangeStub()
        ):
            response = realtime_ingest_binance.lambda_handler({}, {})

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            mock_fetch.call_args_list[0].args,
            (
                "/api/v3/klines",
                {
                    "symbol": "BTCUSDC",
                    "interval": "1m",
                    "startTime": 1000,
                    "endTime": 1999,
                    "limit": 1,
                },
            ),
        )
        self.assertEqual(
            mock_fetch.call_args_list[1].args,
            (
                "/api/v3/aggTrades",
                {"symbol": "BTCUSDC", "startTime": 1000, "endTime": 1999, "limit": 1000},
            ),
        )
        self.assertEqual(mock_upload.call_args_list[1].kwargs["base_prefix"], "landing")
        self.assertEqual(mock_upload.call_args_list[1].args[1], "binance_public")
        self.assertEqual(mock_upload.call_args_list[1].args[2], "agg_trades")


if __name__ == "__main__":
    unittest.main()
