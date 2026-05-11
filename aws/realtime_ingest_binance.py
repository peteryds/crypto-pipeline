import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests

try:
    import ccxt
except Exception:  # pragma: no cover - fallback for environments without ccxt
    ccxt = None

from logger import get_logger
from aws.storage import S3Storage

logger = get_logger(__name__)
storage = S3Storage()

# Define trading pairs (CCXT uses slashes, Binance REST does not)
CCXT_SYMBOL = 'BTC/USDC'
S3_SYMBOL = 'BTCUSDC'
BINANCE_BASE_URL = "https://api.binance.com"

def init_exchange():
    if ccxt is None:
        logger.warning("ccxt is unavailable; private Binance endpoints will be skipped.")
        return None
    return ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_SECRET_KEY'),
        'enableRateLimit': True,
    })


exchange = init_exchange()

def upload_to_s3(data: list, folder: str, data_type: str, base_prefix: str = "bronze") -> None:
    """Uploads real-time data to S3.

    Unlike historical backfills, real-time filenames include a timestamp 
    to prevent overwriting data within the same day partition.
    """
    if not data:
        logger.info(f"No data found for {data_type}, skipping upload.")
        return

    now = datetime.now(timezone.utc)
    year = now.strftime('%Y')
    month = now.strftime('%m')
    day = now.strftime('%d')
    timestamp = now.strftime('%H%M%S') # e.g., 143005
    
    s3_key = f"{base_prefix}/{folder}/{data_type}/symbol={S3_SYMBOL}/year={year}/month={month}/day={day}/{timestamp}.json"
    storage.upload_json(data, s3_key)
    logger.info(f"Uploaded {data_type} to {s3_key}")


def get_previous_minute_window_ms(now: datetime = None):
    current_utc = now or datetime.now(timezone.utc)
    previous_minute = current_utc.replace(second=0, microsecond=0) - timedelta(minutes=1)
    start_ms = int(previous_minute.timestamp() * 1000)
    end_ms = start_ms + 60_000 - 1
    return start_ms, end_ms


def fetch_binance_json(endpoint: str, params: dict, max_retries: int = 3, timeout: int = 10):
    url = f"{BINANCE_BASE_URL}{endpoint}"

    for attempt in range(max_retries):
        response = requests.get(url, params=params, timeout=timeout)

        if response.status_code in (429, 418):
            wait_seconds = int(response.headers.get("Retry-After", 0)) or (2 ** attempt)
            logger.warning(
                "Binance rate limit encountered (status=%s). Retrying in %ss (attempt %s/%s).",
                response.status_code,
                wait_seconds,
                attempt + 1,
                max_retries,
            )
            if attempt == max_retries - 1:
                raise Exception(f"Binance rate limit persisted after {max_retries} attempts.")
            time.sleep(wait_seconds)
            continue

        response.raise_for_status()
        return response.json()

    raise Exception(f"Failed to fetch Binance endpoint: {endpoint}")

def lambda_handler(event, context):
    """Standard AWS Lambda entry point."""
    logger.info(f"Starting Live Ingestion for {CCXT_SYMBOL}")
    
    if not storage.check_config():
        logger.error("S3_BUCKET_NAME environment variable is missing.")
        return {"statusCode": 500}

    try:
        # --------------------------------------------------
        # 1. Public Data: Strict previous 1-minute window
        # --------------------------------------------------
        start_ms, end_ms = get_previous_minute_window_ms()
        logger.info("Fetching Public Data for window %s - %s", start_ms, end_ms)

        logger.info("Fetching Public Data (Klines)...")
        klines = fetch_binance_json(
            "/api/v3/klines",
            {
                "symbol": S3_SYMBOL,
                "interval": "1m",
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": 1,
            },
        )
        upload_to_s3(klines, 'binance_public', 'klines')

        logger.info("Fetching Public Data (aggTrades)...")
        agg_trades = fetch_binance_json(
            "/api/v3/aggTrades",
            {
                "symbol": S3_SYMBOL,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": 1000,
            },
        )
        upload_to_s3(agg_trades, 'binance_public', 'agg_trades', base_prefix='landing')

        # --------------------------------------------------
        # 2. Private Data: Current Open Orders
        # --------------------------------------------------
        if exchange:
            logger.info("Fetching Private Data (Open Orders)...")
            open_orders = exchange.fetch_open_orders(CCXT_SYMBOL)
            upload_to_s3(open_orders, 'binance_private', 'open_orders')

        # --------------------------------------------------
        # 3. Private Data: Recent Trade History (My Trades)
        # --------------------------------------------------
        if exchange:
            logger.info("Fetching Private Data (My Trades)...")
            my_trades = exchange.fetch_my_trades(CCXT_SYMBOL, limit=50)
            upload_to_s3(my_trades, 'binance_private', 'my_trades')

        logger.info("Live Ingestion Completed Successfully!")
        return {
            "statusCode": 200,
            "body": json.dumps("Ingestion successful")
        }

    except Exception as e:
        logger.error(f"Live Ingestion Failed: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps(str(e))
        }

if __name__ == "__main__":
    # Simulate AWS Lambda trigger for local testing
    lambda_handler(None, None)
