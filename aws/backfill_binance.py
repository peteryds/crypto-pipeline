"""
Binance Historical Data Backfill Script.

This module automates the retrieval of daily klines (OHLCV) and aggTrades from 
Binance Vision and uploads them to an AWS S3 data lake using Hive-style partitioning.
The implementation uses streaming to minimize local disk I/O and memory usage.
"""

import os
import requests
import boto3
import logging
from datetime import datetime, timedelta
from io import BytesIO
from dotenv import load_dotenv
import storage  # Custom module for S3 interactions

# ==========================================
# LOGGING CONFIGURATION
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==========================================
# ENVIRONMENT CONFIGURATION
# ==========================================

load_dotenv()

# Fetch configuration from environment variables for security and flexibility
BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

# Initialize AWS S3 client
s3_client = boto3.client('s3')

# ==========================================
# CORE FUNCTIONS
# ==========================================

def stream_zip_to_s3(url: str, s3_key: str) -> bool:
    """Downloads a ZIP file from a URL and streams it directly to S3.

    Utilizes streaming to minimize memory footprint. Note: Using response.raw 
    allows boto3 to handle the upload in chunks.
    
    Args:
        url: The public URL of the Binance data file.
        s3_key: The destination path in the S3 bucket.

    Returns:
        bool: True if the upload was successful, False otherwise.
    """
    try:
        # Use stream=True to avoid loading the entire file into memory at once
        with requests.get(url, stream=True) as response:
            if response.status_code == 404:
                logger.warning(f"File not found on Binance Server: {url}")
                return False
                
            response.raise_for_status()
        
            # Pass the raw socket stream to storage handler
            storage.upload_stream(response.raw, s3_key)
            logger.info(f"Successfully uploaded to s3://{BUCKET_NAME}/{s3_key}")
            return True
        
    except Exception as e:
        logger.error(f"Failed to process {url}: {e}")
        return False

def backfill_historical_data(symbol: str, start_date_str: str, end_date_str: str) -> None:
    """Iterates through a date range to backfill klines and aggTrades.

    Data is organized using a Hive-style partition: symbol/year/month/day.

    Args:
        symbol: The trading pair (e.g., 'BTCUSDC').
        start_date_str: Start date in ISO format (YYYY-MM-DD).
        end_date_str: End date in ISO format (YYYY-MM-DD).
    """
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    current_date = start_date
    
    logger.info(f"Starting Data Ingestion Pipeline | Target: {symbol} | Range: {start_date_str} to {end_date_str}")
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        year = current_date.strftime("%Y")
        month = current_date.strftime("%m")
        day = current_date.strftime("%d")
        
        logger.info(f"Processing date: {date_str}")
        
        # --------------------------------------------------
        # 1. Process 1-minute Klines (OHLCV)
        # --------------------------------------------------
        kline_url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/1m/{symbol}-1m-{date_str}.zip"
        kline_s3_key = f"landing/binance/klines/symbol={symbol}/year={year}/month={month}/day={day}/data.zip"
        
        stream_zip_to_s3(kline_url, kline_s3_key)
        
        # --------------------------------------------------
        # 2. Process aggTrades (Tick-level aggregated trades)
        # --------------------------------------------------
        agg_url = f"https://data.binance.vision/data/spot/daily/aggTrades/{symbol}/{symbol}-aggTrades-{date_str}.zip"
        agg_s3_key = f"landing/binance/aggTrades/symbol={symbol}/year={year}/month={month}/day={day}/data.zip"
        
        stream_zip_to_s3(agg_url, agg_s3_key)
        
        # Increment to the next day
        current_date += timedelta(days=1)
        
    logger.info("Data Ingestion Pipeline Completed Successfully!")

if __name__ == "__main__":
    if not storage.check_config():
        logger.error("S3_BUCKET_NAME not configured.")
        exit(1)

    TARGET_SYMBOL = "BTCUSDC"
    START_DATE = "2026-02-01"
    END_DATE = "2026-04-29"
    
    backfill_historical_data(TARGET_SYMBOL, START_DATE, END_DATE)