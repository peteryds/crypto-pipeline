import os
import ccxt
from datetime import datetime, timezone
from core.logger import get_logger
from core.storage import S3Storage

logger = get_logger(__name__)
storage = S3Storage()

# Define trading pairs (CCXT uses slashes, but we use no slashes for S3 partition paths)
CCXT_SYMBOL = 'BTC/USDC'
S3_SYMBOL = 'BTCUSDC'

# Initialize Binance API client via CCXT with signature handling
exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_SECRET_KEY'),
    'enableRateLimit': True, # Built-in rate limit protection
})

def upload_to_s3(data: list, folder: str, data_type: str) -> None:
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
    
    s3_key = f"bronze/{folder}/{data_type}/symbol={S3_SYMBOL}/year={year}/month={month}/day={day}/{timestamp}.json"
    storage.upload_json(data, s3_key)
    logger.info(f"Uploaded {data_type} to {s3_key}")

def lambda_handler(event, context):
    """Standard AWS Lambda entry point."""
    logger.info(f"Starting Live Ingestion for {CCXT_SYMBOL}")
    
    if not storage.check_config():
        logger.error("S3_BUCKET_NAME environment variable is missing.")
        return {"statusCode": 500}

    try:
        # --------------------------------------------------
        # 1. Public Data: Latest 1-minute Klines (fetch last 5)
        # --------------------------------------------------
        logger.info("Fetching Public Data (Klines)...")
        klines = exchange.fetch_ohlcv(CCXT_SYMBOL, timeframe='1m', limit=5)
        upload_to_s3(klines, 'binance_public', 'klines')

        # --------------------------------------------------
        # 2. Private Data: Current Open Orders
        # --------------------------------------------------
        logger.info("Fetching Private Data (Open Orders)...")
        open_orders = exchange.fetch_open_orders(CCXT_SYMBOL)
        upload_to_s3(open_orders, 'binance_private', 'open_orders')

        # --------------------------------------------------
        # 3. Private Data: Recent Trade History (My Trades)
        # --------------------------------------------------
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