import streamlit as st
import pandas as pd
import time
from api_helper import ShoonyaApiPy

# --- STREAMLIT UI SETUP ---
st.set_page_config(page_title="Ultra Sniper Bot", layout="wide")
st.title("🎯 Ultra Sniper Trading Bot")

# --- SESSION STATE (Variables ko save rakhne ke liye) ---
if 'api' not in st.session_state:
    st.session_state.api = ShoonyaApiPy()
if 'running' not in st.session_state:
    st.session_state.running = False
if 'trade_count' not in st.session_state:
    st.session_state.trade_count = 0
if 'daily_pnl' not in st.session_state:
    st.session_state.daily_pnl = 0

# --- SIDEBAR CONFIG ---
st.sidebar.header("Settings")
USER = st.sidebar.text_input("User ID")
PWD = st.sidebar.text_input("Password", type="password")
VC = st.sidebar.text_input("Vendor Code")
KEY = st.sidebar.text_input("API Key", type="password")
TOTP = st.sidebar.text_input("Enter TOTP")

idx_choice = st.sidebar.selectbox("Select Index", ["NIFTY", "BANKNIFTY"])
token = "26000" if idx_choice == "NIFTY" else "26009"

# --- FUNCTIONS (Pehle wale logic se same) ---
def rsi_calc(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def fetch_data(api, token):
    try:
        q = api.get_quotes(exchange="NSE", token=token)
        hist = api.get_time_price_series(exchange="NSE", token=token, interval=5)
        if not q or not hist: return None
        
        df = pd.DataFrame(hist)
        df['intc'] = df['intc'].astype(float)
        df['v'] = df['v'].astype(float)
        
        lp = float(q['lp'])
        sma = df['intc'].rolling(20).mean().iloc[-1]
        rsi = rsi_calc(df['intc']).iloc[-1]
        df['vwap'] = (df['intc'] * df['v']).cumsum() / df['v'].cumsum()
        vwap = df['vwap'].iloc[-1]
        
        return lp, sma, rsi, vwap, int(q.get('toi', 0))
    except: return None

# --- AUTHENTICATION ---
if st.sidebar.button("Login"):
    login = st.session_state.api.login(userid=USER, password=PWD, twoFA=TOTP, 
                                      vendor_code=VC, api_secret=KEY, imei="abc123")
    if login and login.get('stat') == 'Ok':
        st.sidebar.success("✅ Logged In")
    else:
        st.sidebar.error("❌ Login Failed")

# --- MAIN DASHBOARD ---
col1, col2, col3 = st.columns(3)
pnl_metric = col1.metric("Daily PnL", f"₹{st.session_state.daily_pnl}")
trade_metric = col2.metric("Total Trades", st.session_state.trade_count)
status_metric = col3.metric("Status", "Running" if st.session_state.running else "Stopped")

start_btn = st.button("▶️ Start Bot")
stop_btn = st.button("🛑 Stop Bot")

if start_btn: st.session_state.running = True
if stop_btn: st.session_state.running = False

# --- TRADING LOOP ---
log_placeholder = st.empty()
if st.session_state.running:
    while st.session_state.running:
        data = fetch_data(st.session_state.api, token)
        if data:
            lp, sma, rsi, vwap, toi = data
            
            # Simple Display
            with log_placeholder.container():
                st.write(f"### Current Price: {lp}")
                st.write(f"**RSI:** {round(rsi,2)} | **VWAP:** {round(vwap,2)}")
                
                # Signal Logic (Example)
                if lp > vwap and rsi > 55:
                    st.success("🎯 SIGNAL: STRONG CALL 🟢")
                elif lp < vwap and rsi < 45:
                    st.error("🎯 SIGNAL: STRONG PUT 🔴")
                else:
                    st.info("⌛ Waiting for Setup...")

        time.sleep(2)
        if not st.session_state.running:
            break
