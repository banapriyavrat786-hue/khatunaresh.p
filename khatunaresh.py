import streamlit as st
from SmartApi import SmartConnect
import pyotp
import time
import requests
import pandas as pd

# --- INITIALIZATION ---
if 'connected' not in st.session_state: st.session_state.connected = False
if 'token_map' not in st.session_state: st.session_state.token_map = None

st.set_page_config(page_title="GRK SNIPER V8.2", layout="wide")

@st.cache_data(ttl=3600, show_spinner="Downloading Scrip Master...")
def load_tokens():
    url = "https://margincalculator.angelbroking.com/OpenAPI_Standard/v1/json/OpenAPIScripMaster.json"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            df = pd.DataFrame(r.json())
            # Basic Filtering
            df = df[df['exch_seg'] == 'NFO']
            return df
        return None
    except:
        return None

# --- SIDEBAR ---
st.sidebar.title("🎯 GRK SNIPER V8.2")
idx = st.sidebar.radio("Market Index", ["NIFTY", "BANKNIFTY"])
expiry_input = st.sidebar.text_input("Expiry (DDMMMYY)", value="02APR26").upper()

if st.sidebar.button("Load Tokens & Connect"):
    token_df = load_tokens()
    if token_df is not None:
        st.session_state.token_map = token_df
        st.sidebar.success(f"✅ Loaded {len(token_df)} Symbols")
        st.session_state.connected = True
    else:
        st.sidebar.error("❌ Angel Server down. Token map is Empty.")
        # Optional: Yahan manual token bhi daal sakte ho testing ke liye

# --- DASHBOARD ---
if st.session_state.connected:
    # Safely check if token_map exists before searching
    if st.session_state.token_map is not None:
        ltp = 22500.0 # Mock price for UI
        step = 50 if idx == "NIFTY" else 100
        atm = int(round(ltp / step) * step)
        
        st.title(f"🏹 {idx} Sniper | ATM @ {atm}")
        
        search_symbol = f"{idx}{expiry_input}{atm}"
        df = st.session_state.token_map
        
        # 🎯 CRITICAL FIX: Line 55 crash protection
        try:
            ce_match = df[df['symbol'].str.contains(f"{search_symbol}CE", na=False)]
            pe_match = df[df['symbol'].str.contains(f"{search_symbol}PE", na=False)]

            col1, col2 = st.columns(2)
            with col1:
                if not ce_match.empty:
                    st.success(f"🟢 CALL: {ce_match.iloc[0]['symbol']}")
                    st.metric("Token", ce_match.iloc[0]['token'])
                else:
                    st.warning(f"CE Token not found for {search_symbol}")

            with col2:
                if not pe_match.empty:
                    st.error(f"🔴 PUT: {pe_match.iloc[0]['symbol']}")
                    st.metric("Token", pe_match.iloc[0]['token'])
                else:
                    st.warning(f"PE Token not found for {search_symbol}")
        except Exception as e:
            st.error(f"Search Error: {e}")
    else:
        st.error("Token database is missing. Please click 'Load Tokens' again.")

else:
    st.info("👈 Please Load Tokens from sidebar to start.")
