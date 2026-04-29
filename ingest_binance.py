import os
"""
Binance Data Ingestion Script.

This module fetches historical kline data from Binance and uploads it to 
an AWS S3 bucket using a standardized partitioning schema.
"""

import os
import requests
import boto3
import json
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# LOGGING CONFIGURATION
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==========================================
# ENVIRONMENT CONFIGURATION
# ==========================================
load_dotenv()

# AWS S3 configuration fetched from environment variables for security
s3_client = boto3.client('s3')
BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

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

def upload_to_s3(data: list, layer: str, source: str, data_type: str, symbol: str, date_obj: datetime) -> None:
    """Uploads JSON data to AWS S3 using a Hive-style partitioning structure.

    Args:
        data: The JSON serializable data to upload.
        layer: Data lake layer (e.g., 'bronze').
        source: Data source name (e.g., 'binance').
        data_type: Type of data (e.g., 'klines').
        symbol: Trading pair symbol.
        date_obj: Datetime object representing the data period.
    """
    year = date_obj.strftime('%Y')
    month = date_obj.strftime('%m')
    day = date_obj.strftime('%d')
    
    # Construct Hive-style partition path for efficient querying in Databricks
    s3_key = f"{layer}/{source}/{data_type}/symbol={symbol}/year={year}/month={month}/day={day}/data.json"
    
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=json.dumps(data),
        ContentType='application/json'
    )
    logger.info(f"Successfully uploaded data to s3://{BUCKET_NAME}/{s3_key}")

if __name__ == "__main__":
    # Fail fast if required configuration is missing
    if not BUCKET_NAME:
        logger.error("Environment variable 'S3_BUCKET_NAME' is missing. Please update your .env file.")
        exit(1)

    # Configuration for the ingestion task
    target_date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    start_ts = int(target_date.timestamp() * 1000)
    end_ts = start_ts + (86400 * 1000) - 1  # 86400 seconds in a day
    SYMBOL = "BTCUSDT"
    
    try:
        logger.info(f"Starting ingestion for {SYMBOL} on {target_date.date()}")
        data = fetch_binance_klines(SYMBOL, "1m", start_ts, end_ts)
        
        logger.info(f"Fetched {len(data)} records. Proceeding with S3 upload...")
        upload_to_s3(data, "bronze", "binance", "klines", SYMBOL, target_date)
        
    except Exception as e:
        logger.error(f"Ingestion pipeline failed: {str(e)}")
        exit(1)