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

st.set_page_config(page_title="GRK SNIPER V14.1", layout="wide")

# --- TOKEN ENGINE (Optimized) ---
def load_nfo_tokens_safe():
    try:
        # Token file ko sirf 1 baar download karein
        url = "https://margincalculator.angelbroking.com/OpenAPI_Standard/v1/json/OpenAPIScripMaster.json"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            df = pd.DataFrame(r.json())
            return df[df['exch_seg'] == 'NFO']
        return None
    except: return None

# --- SIDEBAR ---
st.sidebar.title("🎯 GRK SNIPER V14.1")
idx_choice = st.sidebar.radio("Market", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (DDMMMYY)", value="02APR26").upper()
mpin = st.sidebar.text_input("Enter MPIN", type="password", max_chars=4)

if st.sidebar.button("🚀 Start Sniper"):
    try:
        # OTP Generation with Time Sync
        res_time = requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5).json()
        otp = pyotp.TOTP(MY_SECRET.strip().replace(" ", "")).at(res_time['unixtime'])
        
        obj = SmartConnect(api_key="MT72qa1q")
        data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
        
        if data['status']:
            st.session_state.obj = obj
            st.session_state.connected = True
            st.sidebar.success("✅ Connected!")
            # Login ke BAAD tokens load karein taaki connection reset na ho
            if st.session_state.token_df is None:
                with st.spinner("Mapping Tokens..."):
                    st.session_state.token_df = load_nfo_tokens_safe()
        else:
            st.sidebar.error(f"❌ Login Failed: {data['message']}")
    except Exception as e: 
        st.sidebar.error("⚠️ Server Busy. Please try again in 10 seconds.")

# --- DASHBOARD ---
if st.session_state.connected:
    st.title("🏹 MKPV SNIPER | LIVE TERMINAL")
    
    # 1. FETCH SPOT DATA
    t_name = "Nifty 50" if idx_choice == "NIFTY" else "Nifty Bank"
    t_tok = "26000" if idx_choice == "NIFTY" else "26009"
    step = 50 if idx_choice == "NIFTY" else 100
    
    try:
        res = st.session_state.obj.ltpData("NSE", t_name, t_tok)
        if res['status']:
            ltp = float(res['data']['ltp'])
            atm = int(round(ltp / step) * step)
            
            c1, c2, c3 = st.columns(3)
            c1.metric(f"SPOT {idx_choice}", f"₹{ltp}")
            c2.metric("ATM STRIKE", atm)
            c3.metric("EXPIRY", expiry)

            # 2. TOKEN DISPLAY
            st.divider()
            if st.session_state.token_df is not None:
                search_sym = f"{idx_choice}{expiry}{atm}"
                df = st.session_state.token_df
                ce_row = df[df['symbol'] == f"{search_sym}CE"]
                pe_row = df[df['symbol'] == f"{search_sym}PE"]

                col_ce, col_pe = st.columns(2)
                with col_ce:
                    if not ce_row.empty: st.success(f"🟢 CALL: {ce_row.iloc[0]['symbol']} (Token: {ce_row.iloc[0]['token']})")
                    else: st.warning(f"CE {search_sym} not found.")
                with col_pe:
                    if not pe_row.empty: st.error(f"🔴 PUT: {pe_row.iloc[0]['symbol']} (Token: {pe_row.iloc[0]['token']})")
                    else: st.warning(f"PE {search_sym} not found.")
            else:
                st.info("💡 Tokens loading in background...")

    except:
        st.warning("Reconnecting to Data Stream...")

    time.sleep(2)
    st.rerun()
else:
    st.info("👈 Sniper is waiting for Login...")
