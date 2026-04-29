"""
Binance Data Ingestion Script.
"""

import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from core.logger import get_logger
from core.storage import S3Storage

load_dotenv()
logger = get_logger(__name__)
storage = S3Storage()

def fetch_binance_klines(symbol: str, interval: str, start_time: int, end_time: int) -> list:
    """Fetches historical kline (OHLCV) data from Binance Public REST API.

    Args:
        symbol: Trading pair (e.g., 'BTCUSDT').
        interval: Kline interval (e.g., '1m', '1h').
        start_time: Start timestamp in milliseconds.
        end_time: End timestamp in milliseconds.

    Returns:
        list: A list of kline data points.
        
    Raises:
        requests.exceptions.HTTPError: If the API request fails.
    """
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time,
        "endTime": end_time,
        "limit": 1000
    }
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def run_daily_ingestion(symbol: str, date_obj: datetime):
    year = date_obj.strftime('%Y')
    month = date_obj.strftime('%m')
    day = date_obj.strftime('%d')
    start_ts = int(date_obj.timestamp() * 1000)
    end_ts = start_ts + (86400 * 1000) - 1
    
    logger.info(f"Ingesting {symbol} for {date_obj.date()}")
    data = fetch_binance_klines(symbol, "1m", start_ts, end_ts)
    
    s3_key = f"bronze/binance/klines/symbol={symbol}/year={year}/month={month}/day={day}/data.json"
    storage.upload_json(data, s3_key)
    logger.info(f"Upload complete: {s3_key}")

if __name__ == "__main__":
    if not storage.check_config():
        logger.error("S3_BUCKET_NAME missing.")
        exit(1)

    target_date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    try:
        run_daily_ingestion("BTCUSDT", target_date)
    except Exception as e:
        logger.error(f"Ingestion pipeline failed: {str(e)}")
        exit(1)