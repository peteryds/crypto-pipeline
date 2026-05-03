import streamlit as st
import requests
import json
import pandas as pd
import time
from datetime import datetime

# ==========================================
# 1. Page Configuration
# ==========================================
st.set_page_config(page_title="Crypto Execution Optimizer", page_icon="📈", layout="wide")

st.title("🚀 Late Capital Optimizer")
st.markdown("This system utilizes an Extra Trees model hosted via Databricks MLflow to analyze real-time market microstructure and provide optimal pyramidal entry suggestions based on custom probability thresholds.")

# ==========================================
# 2. Data Fetching & Calculation Functions
# ==========================================
@st.cache_data(ttl=3600)
def get_historical_klines():
    """Fetches 31 days of historical Daily Klines from Binance.US to calculate 7D and 30D changes."""
    try:
        url = "https://api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=31"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Klines fetch error: {e}")
        return None

def get_live_ticker():
    """Fetches real-time ticker from Binance.US"""
    try:
        url = "https://api.binance.us/api/v3/ticker/24hr?symbol=BTCUSDT"
        response = requests.get(url, timeout=2)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Ticker fetch error: {e}")
        return None

def get_order_book():
    """Fetches top 10 bids and asks from Binance.US order book."""
    try:
        url = "https://api.binance.us/api/v3/depth?symbol=BTCUSDT&limit=10"
        response = requests.get(url, timeout=2)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Order book fetch error: {e}")
        return None

@st.cache_data(ttl=3600)
def get_realtime_features():
    """Calculates real-time ATR, 4H Volatility, and Bias from Binance.US Klines."""
    try:
        res_4h = requests.get("https://api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=4h&limit=50", timeout=5).json()
        df_4h = pd.DataFrame(res_4h)
        closes_4h = df_4h[4].astype(float)
        
        current_price = closes_4h.iloc[-1]
        ma_50_4h = closes_4h.mean()
        
        bias_4h = (current_price - ma_50_4h) / ma_50_4h
        vol_4h = closes_4h.std()
        
        res_1d = requests.get("https://api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=15", timeout=5).json()
        df_1d = pd.DataFrame(res_1d)
        
        highs = df_1d[2].astype(float)
        lows = df_1d[3].astype(float)
        closes = df_1d[4].astype(float)
        prev_closes = closes.shift(1)
        
        tr1 = highs - lows
        tr2 = (highs - prev_closes).abs()
        tr3 = (lows - prev_closes).abs()
        
        df_tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3})
        tr = df_tr.max(axis=1)
        atr_14 = tr.rolling(window=14).mean().iloc[-1]
        atr_pct = atr_14 / current_price
        
        atr_pct = float(max(0.01, min(0.15, atr_pct)))
        vol_4h = float(max(100.0, min(5000.0, vol_4h)))
        bias_4h = float(max(-0.15, min(0.15, bias_4h)))
        
        return {"atr_pct": atr_pct, "vol_4h": vol_4h, "bias_4h": bias_4h}
        
    except Exception as e:
        print(f"Feature calculation error: {e}")
        return {"atr_pct": 0.045, "vol_4h": 1250.0, "bias_4h": 0.08}

# ==========================================
# 3. Sidebar Configuration
# ==========================================
st.sidebar.header("Execution Parameters")
total_capital = st.sidebar.number_input("Total Allocation (USDT)", min_value=10.0, value=10000.0, step=100.0)

# 👑 新增：自訂機率決策門檻 (Probability Thresholds)
st.sidebar.divider()
st.sidebar.header("🎯 Decision Thresholds")
st.sidebar.caption("Override standard ML output with custom risk appetite.")
threshold_A = st.sidebar.slider("Aggressive Threshold", 0.05, 0.50, 0.15, step=0.01)
threshold_B = st.sidebar.slider("Balanced Threshold", 0.05, 0.50, 0.20, step=0.01)

st.sidebar.divider()
st.sidebar.header("Current Market Features")
st.sidebar.caption("💡 Defaults are auto-calculated from live market data.")

live_features = get_realtime_features()

atr_pct = st.sidebar.slider("ATR Volatility (%)", 0.01, 0.15, value=float(live_features["atr_pct"]), format="%.4f")
volatility_4h = st.sidebar.slider("4H Volatility", 100.0, 5000.0, value=float(live_features["vol_4h"]), format="%.1f")
bias_to_ma_4h = st.sidebar.slider("MA Deviation (Bias)", -0.15, 0.15, value=float(live_features["bias_4h"]), format="%.4f")
days_since_signal = st.sidebar.slider("Days Since Initial Signal", 0, 14, 2)

with st.sidebar.expander("🛠️ Advanced Microstructure Features"):
    st.caption("Adjust these secondary features to fine-tune the model's environment.")
    atr_24h_pct = st.slider("ATR 24H (%)", 0.01, 0.20, 0.05)
    volume_surge_ratio = st.slider("Volume Surge Ratio", 0.5, 5.0, 1.2)
    lower_wick_ratio = st.slider("Lower Wick Ratio", 0.0, 1.0, 0.3)
    roc_4h = st.slider("ROC 4H", -0.10, 0.10, 0.02)
    trend_extension_pct = st.slider("Trend Extension %", 0.0, 0.50, 0.15)

# ==========================================
# 4. Live Market Data Section (Auto-Refresh)
# ==========================================
if 'last_fetch_time' not in st.session_state:
    st.session_state.last_fetch_time = 0
    st.session_state.cached_ticker = None
    st.session_state.cached_depth = None

@st.fragment(run_every="1s")
def display_live_market_data():
    now = time.time()
    elapsed = now - st.session_state.last_fetch_time
    remaining = max(0, 5 - int(elapsed))

    if elapsed >= 5 or st.session_state.cached_ticker is None:
        with st.spinner("Fetching live data..."):
            st.session_state.cached_ticker = get_live_ticker()
            st.session_state.cached_depth = get_order_book()
            st.session_state.last_fetch_time = now
            remaining = 5
    
    ticker = st.session_state.cached_ticker
    depth = st.session_state.cached_depth
    klines = get_historical_klines()

    if ticker:
        price = float(ticker['lastPrice'])
        vol_btc = float(ticker['volume'])
        pct_24h = float(ticker['priceChangePercent'])
        st.session_state['current_btc_price'] = price
        
        pct_7d, pct_30d = 0.0, 0.0
        if klines and len(klines) >= 31:
            close_7d_ago = float(klines[-8][4])
            close_30d_ago = float(klines[0][4])
            pct_7d = ((price - close_7d_ago) / close_7d_ago) * 100
            pct_30d = ((price - close_30d_ago) / close_30d_ago) * 100
        
        c1, c2 = st.columns([1, 4])
        with c1:
            st.metric("Next Update", f"{remaining}s")
        with c2:
            st.write(f"**Status:** {'🟢 Data Live' if remaining > 0 else '🔄 Refreshing...'}")
            st.progress(remaining / 5)

        st.divider()

        st.subheader("📊 Live Market Data (Binance.US)")
        cols = st.columns(4)
        cols[0].metric("BTC/USDT", f"${price:,.2f}", f"{pct_24h:+.2f}% (24H)")
        cols[1].metric("24H Volume", f"{vol_btc:,.0f} BTC")
        cols[2].metric("7D Trend", f"{pct_7d:+.2f}%", f"{pct_7d:+.2f}%" if pct_7d != 0 else None)
        cols[3].metric("30D Trend", f"{pct_30d:+.2f}%", f"{pct_30d:+.2f}%" if pct_30d != 0 else None)

        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("##### 🗂️ Live Order Book (Depth 10)")
        if depth:
            asks = depth['asks'][::-1] 
            bids = depth['bids']
            book_data = []
            
            for ask in asks:
                book_data.append({"Ask Size (BTC)": f"{float(ask[1]):.4f}", "Price (USDT)": f"${float(ask[0]):,.2f}", "Bid Size (BTC)": ""})
            
            book_data.append({"Ask Size (BTC)": "---", "Price (USDT)": f"📍 ${price:,.2f} (Current)", "Bid Size (BTC)": "---"})
            
            for bid in bids:
                book_data.append({"Ask Size (BTC)": "", "Price (USDT)": f"${float(bid[0]):,.2f}", "Bid Size (BTC)": f"{float(bid[1]):.4f}"})
                
            st.dataframe(pd.DataFrame(book_data), hide_index=True, use_container_width=True)
    else:
        st.error("Connection lost or fetching failed. Retrying...")
        st.session_state['current_btc_price'] = 65000.0

display_live_market_data()
st.divider()

# ==========================================
# 5. Model Execution & Order Generation
# ==========================================
DATABRICKS_URL = st.secrets.get("DATABRICKS_URL", "")
DATABRICKS_TOKEN = st.secrets.get("DATABRICKS_TOKEN", "")

if st.button("🧠 Generate AI Execution Strategy", type="primary"):
    current_price = st.session_state.get('current_btc_price', 65000.0)
    atr_usd_value = current_price * atr_pct
    
    if not DATABRICKS_URL or not DATABRICKS_TOKEN:
        st.error("Databricks credentials missing! Please configure your `.streamlit/secrets.toml` file.")
        st.stop()
        
    with st.spinner("Calling Databricks MLOps Endpoint..."):
        headers = {
            "Authorization": f"Bearer {DATABRICKS_TOKEN}", 
            "Content-Type": "application/json"
        }
        
        payload = {
            "dataframe_split": {
                "columns": [
                    "atr_pct", "volatility_4h", "bias_to_ma_4h", "days_since_signal", 
                    "atr_24h_pct", "volume_surge_ratio", "lower_wick_ratio", 
                    "roc_4h", "trend_extension_pct"
                ],
                "data": [[
                    atr_pct, volatility_4h, bias_to_ma_4h, days_since_signal, 
                    atr_24h_pct, volume_surge_ratio, lower_wick_ratio, 
                    roc_4h, trend_extension_pct
                ]]
            }
        }
        
        try:
            response = requests.post(DATABRICKS_URL, headers=headers, data=json.dumps(payload))
            response_status = response.status_code
            
            if response_status == 200:
                response_json = response.json()
                
                # 👑 關鍵修正：針對 PyFunc Wrapper 的字典結構進行解析
                # 結構是: {"predictions": {"probabilities": [[...]], "classes": [...]}}
                predictions_data = response_json.get('predictions', {})
                
                # 1. 取得機率陣列
                probs_list = predictions_data.get('probabilities', None)
                # 2. 取得類別名稱列表
                class_names = predictions_data.get('classes', ['Aggressive', 'Balanced', 'Passive'])
                
                # 預設策略為 Passive
                final_strategy = 'Passive'
                
                if probs_list and isinstance(probs_list, list):
                    prob_array = probs_list[0]  # 取得第一筆資料的機率 [A_prob, B_prob, P_prob]
                    
                    # 找出 A 和 B 在陣列中的索引位置 (防止順序變動)
                    try:
                        idx_A = class_names.index('Aggressive')
                        idx_B = class_names.index('Balanced')
                        
                        # 👑 執行你的自訂閾值決策
                        if prob_array[idx_A] >= threshold_A:
                            final_strategy = 'Aggressive'
                        elif prob_array[idx_B] >= threshold_B:
                            final_strategy = 'Balanced'
                        else:
                            final_strategy = 'Passive'
                    except ValueError:
                        # 如果找不到對應名稱，退回到原本的標籤預測
                        final_strategy = 'Passive'
                
                st.subheader("🎯 Execution Plan & Analysis")
                
                # 1. Debug 面板：顯示機率
                with st.expander("🛠️ API Debug Inspector (Check Probabilities)", expanded=False):
                    if probs_list:
                        st.success(f"✅ Probabilities Found: A={prob_array[idx_A]:.2%}, B={prob_array[idx_B]:.2%}")
                    st.write("**Full Databricks Response:**")
                    st.json(response_json)

                # 2. 顯示模型輸入的背景資訊
                st.markdown("##### 📌 Model Inputs Context")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("ATR Volatility", f"{atr_pct*100:.2f}%", f"${atr_usd_value:,.2f}")
                col2.metric("4H Volatility", f"{volatility_4h:,.2f}")
                col3.metric("MA Bias (4H)", f"{bias_to_ma_4h*100:+.2f}%")
                col4.metric("Days Since Signal", f"{days_since_signal} Days")
                
                st.divider()

                # 3. 核心：根據決策結果生成訂單表格
                orders = []
                
                if final_strategy == 'Aggressive':
                    st.success("**🔥 Strategy A: Aggressive** (Fast deployment for strong momentum)")
                    orders = [
                        {"Order Type": "Market Buy", "Allocation (%)": "50%", "Size (USDT)": total_capital * 0.50, "Target Price (USDT)": "Current Market"},
                        {"Order Type": "Limit Buy", "Allocation (%)": "50%", "Size (USDT)": total_capital * 0.50, "Target Price (USDT)": current_price - (0.5 * atr_usd_value)}
                    ]
                elif final_strategy == 'Balanced':
                    st.info("**⚖️ Strategy B: Balanced** (Standard Pyramiding)")
                    orders = [
                        {"Order Type": "Market Buy", "Allocation (%)": "30%", "Size (USDT)": total_capital * 0.30, "Target Price (USDT)": "Current Market"},
                        {"Order Type": "Limit Buy", "Allocation (%)": "40%", "Size (USDT)": total_capital * 0.40, "Target Price (USDT)": current_price - (1.5 * atr_usd_value)},
                        {"Order Type": "Limit Buy", "Allocation (%)": "30%", "Size (USDT)": total_capital * 0.30, "Target Price (USDT)": current_price - (2.0 * atr_usd_value)}
                    ]
                else:
                    st.warning("**🛡️ Strategy C: Passive** (Waiting for flush/liquidation)")
                    orders = [
                        {"Order Type": "Market Buy", "Allocation (%)": "10%", "Size (USDT)": total_capital * 0.10, "Target Price (USDT)": "Current Market"},
                        {"Order Type": "Limit Buy", "Allocation (%)": "40%", "Size (USDT)": total_capital * 0.40, "Target Price (USDT)": current_price - (2.0 * atr_usd_value)},
                        {"Order Type": "Limit Buy", "Allocation (%)": "50%", "Size (USDT)": total_capital * 0.50, "Target Price (USDT)": current_price - (4.0 * atr_usd_value)}
                    ]
                
                # 4. 格式化並顯示表格
                df_orders = pd.DataFrame(orders)
                df_orders["Size (USDT)"] = df_orders["Size (USDT)"].apply(lambda x: f"${x:,.2f}")
                df_orders["Target Price (USDT)"] = df_orders["Target Price (USDT)"].apply(
                    lambda x: f"${x:,.2f}" if isinstance(x, (int, float)) else x
                )
                
                st.table(df_orders)

            else:
                st.error(f"API Call Failed (Status {response_status}): {response.text}")
                
        except Exception as e:
            st.error(f"Failed to connect to Databricks. Please check your network or API endpoint. Error: {e}")