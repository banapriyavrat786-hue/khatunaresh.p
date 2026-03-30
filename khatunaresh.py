import streamlit as st
from SmartApi import SmartConnect
import pyotp
import time
import pandas as pd

# --- CONFIG ---
FIXED_CLIENT_ID = "P51646259"

st.set_page_config(page_title="GRK SNIPER V4", layout="wide")

if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None

# --- SIDEBAR ---
st.sidebar.title("🚀 GRK WARRIOR V4")
idx = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])

st.sidebar.markdown("---")
api_key = st.sidebar.text_input("1. SmartAPI Key", value="MT72qa1q")
mpin = st.sidebar.text_input("2. MPIN", type="password", max_chars=4)
totp_key = st.sidebar.text_input("3. TOTP Secret", value="W6SCERQJX4RSU6TXECROABI7TA", type="password")

if st.sidebar.button("Connect Sniper"):
    try:
        otp = pyotp.TOTP(totp_key.strip().replace(" ", "")).now()
        obj = SmartConnect(api_key=api_key.strip())
        data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
        if data['status']:
            st.session_state.obj = obj
            st.session_state.connected = True
            st.sidebar.success("✅ Sniper Ready!")
        else: st.sidebar.error(f"❌ Error: {data['message']}")
    except Exception as e: st.sidebar.error(f"❌ {e}")

# --- MAIN DASHBOARD ---
st.title("🎯 MKPV ULTRA SNIPER V4 | LIVE STRATEGY")
st.divider()

if st.session_state.connected:
    try:
        # 1. Fetch Spot LTP
        t_sym = "Nifty 50" if idx == "NIFTY" else "Nifty Bank"
        t_tok = "26000" if idx == "NIFTY" else "26009"
        
        res = st.session_state.obj.ltpData("NSE", t_sym, t_tok)
        if res['status']:
            ltp = float(res['data']['ltp'])
            
            # 2. UI Top Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric(f"SPOT {idx}", f"₹{ltp}", delta="LIVE")
            c2.metric("Pipeline", "CONNECTED ✅")
            
            # 3. ATM Strike Calculation
            step = 50 if idx == "NIFTY" else 100
            atm_strike = round(ltp / step) * step
            c3.metric("ATM STRIKE", f"{atm_strike}")

            st.markdown("---")
            
            # 4. Strategy Zone (Placeholder for OI and Premium)
            st.subheader(f"⚡ {idx} Option Chain (ATM)")
            st.info(f"Targeting ATM: {atm_strike} CE & {atm_strike} PE")
            
            # Note: For real OI of Options, we need to search 'NFO' tokens.
            # Would you like me to add the NFO Token Search logic here?
            
        else:
            st.session_state.connected = False
            st.rerun()

    except Exception as e: st.error(f"Error: {e}")
    
    time.sleep(1)
    st.rerun()
else:
    st.warning("Please Connect from Sidebar to Start Sniper Mode.")
