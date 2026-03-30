import streamlit as st
from SmartApi import SmartConnect
import pyotp
import time
import requests
import pandas as pd

# --- INITIALIZATION ---
if 'connected' not in st.session_state: st.session_state.connected = False
if 'token_map' not in st.session_state: st.session_state.token_map = None

st.set_page_config(page_title="GRK SNIPER V8.1", layout="wide")

@st.cache_data(show_spinner="Downloading Scrip Master (50MB+)...")
def load_tokens():
    url = "https://margincalculator.angelbroking.com/OpenAPI_Standard/v1/json/OpenAPIScripMaster.json"
    try:
        # Stream download for large files
        r = requests.get(url)
        df = pd.DataFrame(r.json())
        # Filter for NFO (Options) and Nifty/BankNifty
        df = df[df['exch_seg'] == 'NFO']
        df = df[df['name'].isin(['NIFTY', 'BANKNIFTY'])]
        return df
    except:
        return None

# --- SIDEBAR ---
st.sidebar.title("🎯 GRK SNIPER V8.1")
idx = st.sidebar.radio("Market Index", ["NIFTY", "BANKNIFTY"])
expiry_input = st.sidebar.text_input("Expiry (DDMMMYY)", value="02APR26").upper()

if st.sidebar.button("Load Tokens & Connect"):
    st.session_state.token_map = load_tokens()
    if st.session_state.token_map is not None:
        st.sidebar.success(f"Loaded {len(st.session_state.token_map)} Options!")
        st.session_state.connected = True
    else:
        st.sidebar.error("Failed to fetch tokens. Check Internet.")

# --- DASHBOARD ---
if st.session_state.connected:
    # Use fixed price from your screenshot for testing
    ltp = 22492.0 
    step = 50 if idx == "NIFTY" else 100
    atm = int(round(ltp / step) * step)
    
    st.title(f"🏹 {idx} Sniper | ATM @ {atm}")
    
    # Flexible Search: NIFTY + 02APR26 + 22500 + CE
    search_symbol = f"{idx}{expiry_input}{atm}"
    
    df = st.session_state.token_map
    # Filter for CE and PE
    ce_match = df[df['symbol'].str.contains(f"{search_symbol}CE")]
    pe_match = df[df['symbol'].str.contains(f"{search_symbol}PE")]

    col1, col2 = st.columns(2)
    
    with col1:
        if not ce_match.empty:
            row = ce_match.iloc[0]
            st.success(f"🟢 CALL: {row['symbol']}")
            st.metric("Token", row['token'])
        else:
            st.error(f"❌ {search_symbol}CE Not Found")

    with col2:
        if not pe_match.empty:
            row = pe_match.iloc[0]
            st.error(f"🔴 PUT: {row['symbol']}")
            st.metric("Token", row['token'])

    # DEBUG: Show what symbols are available in data
    with st.expander("Check Available Symbols (Debug)"):
        st.write(df['symbol'].head(20).tolist())
