"""
Test Script for Crypto Execution Optimizer (Late Capital Deployment)
====================================================================
Sends a sample market data payload to the Databricks Model Serving endpoint
and retrieves the optimal execution strategy recommendation.

Quick Start for GitHub Users:
1. Setup Virtual Environment (Recommended):
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate

2. Install Required Packages:
   pip install -r requirements.txt

3. Environment Setup:
   - Create a '.env' file in the root directory of this project.
   - Add your endpoint and token to the file: 
     DATABRICKS_TOKEN=your_actual_token_here
     DATABRICKS_URL=your_serving_endpoint_url_here

- CRITICAL: Ensure '.env' is added to your '.gitignore' file.

Usage: 
- python test/test_project.py
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# ==========================================
# 1. Endpoint Configuration
# ==========================================
# TODO: Replace the URL with your actual Databricks Serving Endpoint URL
URL = os.environ.get("DATABRICKS_URL")

# Securely fetch the token from the loaded environment variables
TOKEN = os.environ.get("DATABRICKS_TOKEN")

if not TOKEN or not URL:
    print("FAIL: DATABRICKS_TOKEN or DATABRICKS_URL is not set.")
    print("Please ensure you have a '.env' file with both variables defined.")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# ==========================================
# 2. Sample Payload (Schema Enforcement)
# ==========================================
# Features must strictly match the schema expected by the MLflow model signature
payload = {
    "dataframe_split": {
        "columns": [
            "close", "atr_pct", "volatility_4h", "bias_to_ma_4h", 
            "days_since_signal", "atr_24h_pct", "volume_surge_ratio", 
            "lower_wick_ratio", "roc_4h", "trend_extension_pct"
        ],
        "data": [
            # Simulating high volatility (4.5% ATR) and over-extended bias (8%)
            [65000.0, 0.045, 1250.5, 0.08, 2, 0.05, 1.2, 0.3, 0.02, 0.15]
        ]
    }
}

# Decoding dictionary mapping label integers to human-readable strategies
strategy_map = {
    "Aggressive": "Aggressive (50% Market / 50% Limit at 0.5x ATR)",
    "Balanced": "Balanced (30% Market / 40% Limit at 1.5x ATR / 30% Limit at 2.0x ATR)",
    "Passive": "Passive (10% Market / 90% Deep Limit between 2.0x and 4.0x ATR)"
}

# ==========================================
# 3. Execute Verification
# ==========================================
def main():
    print("[INFO] Initiating end-to-end test sequence...")
    print(f"[INFO] Target Endpoint: {URL}")
    print("[INFO] Sending mock market data payload to the execution optimizer...")
    
    try:
        # Send POST request to the serving endpoint
        resp = requests.post(URL, headers=headers, json=payload, timeout=30)
        
        if resp.status_code != 200:
            print(f"\nFAIL: Received HTTP status {resp.status_code}")
            print(f"Error Details: {resp.text}")
            sys.exit(1)
            
        result = resp.json()
        print(f"[DEBUG] Raw API Response: {result}")
        
        # 👑 Upgraded Smart Parsing Logic
        prediction_value = None
        
        if 'predictions' in result:
            preds = result['predictions']
            
            # Handle dictionary formats containing probability matrices (e.g., FLAML return format)
            if isinstance(preds, dict) and 'probabilities' in preds and 'classes' in preds:
                probs = preds['probabilities'][0]
                classes = preds['classes']
                # Find the index with the highest probability
                max_index = probs.index(max(probs))
                prediction_value = classes[max_index]  # Example: 'Passive'
                
            # Fallback: If it returns a list/array directly
            elif isinstance(preds, list):
                prediction_value = preds[0]
            # Fallback: If it returns a dictionary with index keys
            elif isinstance(preds, dict):
                prediction_value = preds.get('0', preds.get(0))
        else:
            prediction_value = result

        # Ensure a value was successfully captured
        if prediction_value is None:
            raise KeyError("Could not extract prediction from response format.")

        # Retrieve the full strategy name from the strategy map dictionary
        strategy_name = strategy_map.get(str(prediction_value), f"Unknown Strategy ({prediction_value})")
        
        print("\n" + "="*45)
        print("          PREDICTION RESULTS          ")
        print("="*45)
        print(f"Model Inference : {prediction_value}")
        print(f"Algorithm Rec.  : {strategy_name}")
        print("="*45 + "\n")
        
        print("PASS")
        sys.exit(0)

    except requests.exceptions.RequestException as e:
        print(f"\nFAIL: Network error or timeout occurred - {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"\nFAIL: An unexpected system error occurred - {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()