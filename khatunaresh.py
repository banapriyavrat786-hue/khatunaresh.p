import streamlit as st
from SmartApi import SmartConnect
import pyotp
import time
import requests

# 1. INITIALIZATION (Isse Attribute Error khatam ho jayega)
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'obj' not in st.session_state:
    st.session_state.obj = None

# --- CONFIG ---
FIXED_CLIENT_ID = "P51646259"
st.set_page_config(page_title="GRK SNIPER V6", layout="wide")

# --- SIDEBAR ---
st.sidebar.title("🎯 GRK SNIPER V6")
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
            st.sidebar.success("✅ Connected!")
        else:
            st.sidebar.error(f"❌ Login Failed: {data['message']}")
    except Exception as e:
        st.sidebar.error(f"❌ Error: {e}")

# --- MAIN DASHBOARD ---
st.title("🏹 MKPV SNIPER | LIVE DATA")
st.divider()

col1, col2, col3 = st.columns(3)

if st.session_state.connected:
    try:
        # Index Mapping
        t_sym = "Nifty 50" if idx == "NIFTY" else "Nifty Bank"
        t_tok = "26000" if idx == "NIFTY" else "26009"
        
        # LTP Fetch
        res = st.session_state.obj.ltpData("NSE", t_sym, t_tok)
        if res['status']:
            ltp = res['data']['ltp']
            col1.metric(f"SPOT {idx}", f"₹{ltp}", delta="LIVE")
            col2.metric("Pipeline", "CONNECTED ✅")
            col3.metric("Status", "Fetching OI...")
        else:
            st.session_state.connected = False
            st.rerun()
            
    except Exception as e:
        st.error(f"Data Fetch Error: {e}")
    
    time.sleep(1)
    st.rerun()
else:
    col1.metric(f"SPOT {idx}", "₹0")
    col2.metric("Pipeline", "OFFLINE ❌")
    col3.metric("Status", "Waiting...")
