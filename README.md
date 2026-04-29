# Crypto Pipeline

This repository contains a data ingestion pipeline to fetch cryptocurrency market data from Binance and store it in an AWS S3 Data Lake.

## Architecture
- **Source**: Binance Public API (Klines/OHLCV)
- **Destination**: AWS S3 (Bronze Layer)
- **Partitioning**: Hive-style (`year=YYYY/month=MM/day=DD`) for optimized querying via Athena/Databricks.

## Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/peteryds/crypto-pipeline.git
   cd crypto-pipeline
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Variables**:
   Create a `.env` file in the root directory and add your AWS credentials:
   ```env
   S3_BUCKET_NAME=your-bucket-name
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   ```