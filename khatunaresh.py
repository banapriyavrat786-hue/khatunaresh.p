import streamlit as st
from SmartApi import SmartConnect
import pyotp
import time
import requests

# 1. INITIALIZATION
if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None

# --- CONFIG ---
FIXED_CLIENT_ID = "P51646259"
st.set_page_config(page_title="GRK SNIPER V7", layout="wide")

# --- SIDEBAR ---
st.sidebar.title("🎯 GRK SNIPER V7")
idx = st.sidebar.radio("Market Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Current Expiry (DDMMMYY)", value="02APR26")

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
            st.sidebar.success("✅ SNIPER ACTIVE")
        else: st.sidebar.error(f"❌ Login Failed: {data['message']}")
    except Exception as e: st.sidebar.error(f"❌ Error: {e}")

# --- DASHBOARD UI ---
if st.session_state.connected:
    # Top Stats Row
    t_sym = "Nifty 50" if idx == "NIFTY" else "Nifty Bank"
    t_tok = "26000" if idx == "NIFTY" else "26009"
    res = st.session_state.obj.ltpData("NSE", t_sym, t_tok)
    
    if res['status']:
        ltp = float(res['data']['ltp'])
        step = 50 if idx == "NIFTY" else 100
        atm = int(round(ltp / step) * step)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("SPOT PRICE", f"₹{ltp}", delta="LIVE")
        c2.metric("ATM STRIKE", f"{atm}")
        c3.metric("SYSTEM STATUS", "STABLE ✅")

        st.divider()
        st.subheader(f"📊 {idx} Option Chain (Targeting ATM @ {atm})")
        
        col_ce, col_pe = st.columns(2)
        
        # 🟢 CALL SIDE
        with col_ce:
            st.success(f"CALL (CE) - Resistance Zone")
            # Note: Token finding logic will go here
            st.metric("LTP", "Fetching...")
            st.metric("Open Interest (OI)", "0", delta="0%")
            st.progress(50, text="Call Writing Status")

        # 🔴 PUT SIDE
        with col_pe:
            st.error(f"PUT (PE) - Support Zone")
            st.metric("LTP", "Fetching...")
            st.metric("Open Interest (OI)", "0", delta="0%")
            st.progress(50, text="Put Writing Status")

        st.divider()
        st.subheader("⚡ Trading Signal")
        st.warning("⚠️ Waiting for NFO Token mapping to find PCR (Put-Call Ratio)...")

    time.sleep(2)
    st.rerun()
else:
    st.info("Bhai, Sidebar se Connect Sniper dabao trading start karne ke liye.")
