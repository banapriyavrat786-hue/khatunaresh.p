import streamlit as st
from SmartApi import SmartConnect
import pyotp
import requests
import time
import pandas as pd

# --- INITIALIZATION ---
if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None
if 'token_df' not in st.session_state: st.session_state.token_df = None

# --- CONFIG ---
FIXED_CLIENT_ID = "P51646259"
MY_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK SNIPER V14.2", layout="wide")

@st.cache_data(ttl=3600)
def load_nfo_tokens_safe():
    try:
        url = "https://margincalculator.angelbroking.com/OpenAPI_Standard/v1/json/OpenAPIScripMaster.json"
        df = pd.DataFrame(requests.get(url, timeout=15).json())
        return df[df['exch_seg'] == 'NFO']
    except: return None

# --- SIDEBAR ---
st.sidebar.title("🎯 GRK SNIPER V14.2")
idx_choice = st.sidebar.radio("Market", ["NIFTY", "BANKNIFTY"])
expiry_in = st.sidebar.text_input("Expiry (DDMMMYY)", value="02APR26").upper()
mpin = st.sidebar.text_input("Enter MPIN", type="password", max_chars=4)

if st.sidebar.button("🚀 Start Sniper"):
    try:
        res_time = requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata").json()
        otp = pyotp.TOTP(MY_SECRET.strip().replace(" ", "")).at(res_time['unixtime'])
        obj = SmartConnect(api_key="MT72qa1q")
        data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
        if data['status']:
            st.session_state.obj = obj
            st.session_state.token_df = load_nfo_tokens_safe()
            st.session_state.connected = True
            st.sidebar.success("✅ Connected!")
    except Exception as e: st.sidebar.error("Server Busy. Try again.")

# --- DASHBOARD ---
if st.session_state.connected:
    st.title("🏹 MKPV SNIPER | LIVE TERMINAL")
    
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
        c3.metric("EXPIRY", expiry_in)

        st.divider()
        
        if st.session_state.token_df is not None:
            df = st.session_state.token_df
            # 🎯 FLEXIBLE SEARCH: Strike aur Expiry dono check karega
            # Example: NIFTY + 02APR26 + 22450 + CE
            ce_match = df[(df['name'] == idx_choice) & 
                          (df['symbol'].str.contains(expiry_in)) & 
                          (df['symbol'].str.contains(str(atm))) & 
                          (df['symbol'].str.endswith('CE'))]
            
            pe_match = df[(df['name'] == idx_choice) & 
                          (df['symbol'].str.contains(expiry_in)) & 
                          (df['symbol'].str.contains(str(atm))) & 
                          (df['symbol'].str.endswith('PE'))]

            col_ce, col_pe = st.columns(2)
            with col_ce:
                if not ce_match.empty:
                    row = ce_match.iloc[0]
                    st.success(f"🟢 {row['symbol']}")
                    st.write(f"**Token:** `{row['token']}` | **Lot:** `{row['lotsize']}`")
                else: st.warning(f"CE {atm} not found. Check Expiry format.")

            with col_pe:
                if not pe_match.empty:
                    row = pe_match.iloc[0]
                    st.error(f"🔴 {row['symbol']}")
                    st.write(f"**Token:** `{row['token']}` | **Lot:** `{row['lotsize']}`")
                else: st.warning(f"PE {atm} not found.")
        else: st.info("💡 Tokens mapping...")

    time.sleep(2)
    st.rerun()
else:
    st.info("👈 Sniper is waiting for Login...")
