import streamlit as st
from SmartApi import SmartConnect
import pyotp
import requests
import time
import pandas as pd

# --- INITIALIZATION ---
if 'connected' not in st.session_state: st.session_state.connected = False
if 'token_df' not in st.session_state: st.session_state.token_df = None

# --- CONFIG ---
FIXED_CLIENT_ID = "P51646259"
MY_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK SNIPER V14", layout="wide")

# --- TOKEN ENGINE (Background Search) ---
@st.cache_data(ttl=3600)
def load_nfo_tokens():
    try:
        url = "https://margincalculator.angelbroking.com/OpenAPI_Standard/v1/json/OpenAPIScripMaster.json"
        df = pd.DataFrame(requests.get(url).json())
        return df[df['exch_seg'] == 'NFO']
    except: return None

# --- SIDEBAR ---
st.sidebar.title("🎯 GRK SNIPER V14")
idx_choice = st.sidebar.radio("Market", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (DDMMMYY)", value="02APR26").upper()
mpin = st.sidebar.text_input("Enter MPIN", type="password", max_chars=4)

if st.sidebar.button("🚀 Start Sniper"):
    try:
        # Time Sync & OTP
        res_time = requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata").json()
        otp = pyotp.TOTP(MY_SECRET.strip().replace(" ", "")).at(res_time['unixtime'])
        
        obj = SmartConnect(api_key="MT72qa1q")
        data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
        
        if data['status']:
            st.session_state.obj = obj
            st.session_state.token_df = load_nfo_tokens()
            st.session_state.connected = True
            st.sidebar.success("✅ Sniper Online!")
    except Exception as e: st.sidebar.error(f"Error: {e}")

# --- DASHBOARD ---
if st.session_state.connected:
    st.title("🏹 MKPV ULTRA SNIPER | LIVE")
    
    # 1. LIVE DATA
    t_name = "Nifty 50" if idx_choice == "NIFTY" else "Nifty Bank"
    t_tok = "26000" if idx_choice == "NIFTY" else "26009"
    step = 50 if idx_choice == "NIFTY" else 100
    
    res = st.session_state.obj.ltpData("NSE", t_name, t_tok)
    if res['status']:
        ltp = float(res['data']['ltp'])
        atm = int(round(ltp / step) * step)
        
        c1, c2, c3 = st.columns(3)
        c1.metric(f"SPOT {idx_choice}", f"₹{ltp}")
        c2.metric("ATM STRIKE", atm)
        c3.metric("EXPIRY", expiry)

        # 2. TOKEN MAPPING (Asli Trading ke liye)
        st.divider()
        search_sym = f"{idx_choice}{expiry}{atm}"
        df = st.session_state.token_df
        
        ce_data = df[df['symbol'] == f"{search_sym}CE"] if df is not None else pd.DataFrame()
        pe_data = df[df['symbol'] == f"{search_sym}PE"] if df is not None else pd.DataFrame()

        col_ce, col_pe = st.columns(2)
        with col_ce:
            if not ce_data.empty:
                st.success(f"🟢 CALL: {ce_data.iloc[0]['symbol']}")
                st.write(f"Token ID: `{ce_data.iloc[0]['token']}`")
            else: st.warning(f"Searching CE Token for {atm}...")

        with col_pe:
            if not pe_data.empty:
                st.error(f"🔴 PUT: {pe_data.iloc[0]['symbol']}")
                st.write(f"Token ID: `{pe_data.iloc[0]['token']}`")
            else: st.warning(f"Searching PE Token for {atm}...")

    time.sleep(2)
    st.rerun()
else:
    st.info("👈 Sniper is waiting for Login...")
