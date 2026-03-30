import streamlit as st
from SmartApi import SmartConnect
import pyotp
import time
import requests
import pandas as pd

# --- INITIALIZATION ---
if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None
if 'token_map' not in st.session_state: st.session_state.token_map = None

# --- CONFIG ---
FIXED_CLIENT_ID = "P51646259"
st.set_page_config(page_title="GRK SNIPER V8", layout="wide")

# --- TOKEN MASTER LOADER ---
@st.cache_data
def load_tokens():
    url = "https://margincalculator.angelbroking.com/OpenAPI_Standard/v1/json/OpenAPIScripMaster.json"
    response = requests.get(url).json()
    df = pd.DataFrame(response)
    # Filter only NFO (Options)
    df = df[df['exch_seg'] == 'NFO']
    return df

# --- SIDEBAR ---
st.sidebar.title("🎯 GRK SNIPER V8")
idx = st.sidebar.radio("Market Index", ["NIFTY", "BANKNIFTY"])
expiry_input = st.sidebar.text_input("Current Expiry (e.g., 02APR26)", value="02APR26")

if st.sidebar.button("Load Tokens & Connect"):
    with st.spinner("Downloading Scrip Master..."):
        st.session_state.token_map = load_tokens()
        st.sidebar.success("Tokens Loaded!")
    
    # Login Logic (Assuming details are pre-filled as per your screenshot)
    # otp = pyotp.TOTP(totp_secret).now() ... [Previous login logic here]
    st.session_state.connected = True # Temporary for UI test

# --- DASHBOARD ---
st.title("🏹 MKPV SNIPER | LIVE OPTION CHAIN")
st.divider()

if st.session_state.connected:
    try:
        # 1. Spot LTP (Using fixed 26000 for Nifty)
        # res = st.session_state.obj.ltpData("NSE", "Nifty 50", "26000") ... 
        ltp = 22536.05 # Mocked from your screenshot
        step = 50 if idx == "NIFTY" else 100
        atm = int(round(ltp / step) * step)

        st.subheader(f"📊 {idx} Chain (ATM @ {atm})")
        
        # 2. Find Tokens for CE & PE
        ce_sym = f"{idx.upper()}{expiry_input}{atm}CE"
        pe_sym = f"{idx.upper()}{expiry_input}{atm}PE"

        def get_token(symbol):
            if st.session_state.token_map is not None:
                match = st.session_state.token_map[st.session_state.token_map['symbol'] == symbol]
                if not match.empty: return match.iloc[0]['token']
            return None

        ce_token = get_token(ce_sym)
        pe_token = get_token(pe_sym)

        col_ce, col_pe = st.columns(2)
        with col_ce:
            st.info(f"🟢 {ce_sym}")
            st.metric("CE Token", ce_token if ce_token else "Not Found")
            # Yahan st.session_state.obj.ltpData("NFO", ce_sym, ce_token) aayega
        
        with col_pe:
            st.info(f"🔴 {pe_sym}")
            st.metric("PE Token", pe_token if pe_token else "Not Found")

    except Exception as e: st.error(f"Error: {e}")
