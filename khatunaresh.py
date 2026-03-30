import streamlit as st
from SmartApi import SmartConnect
import pyotp
import time
import pandas as pd

# --- CONFIG ---
FIXED_CLIENT_ID = "P51646259"

st.set_page_config(page_title="GRK SNIPER V6", layout="wide")

if 'connected' not in st.session_state: st.session_state.connected = False

# --- SIDEBAR ---
st.sidebar.title("🎯 GRK SNIPER V6")
idx = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Current Expiry (DDMMMYY)", value="02APR26") # ⚠️ Isse update karein

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

# --- DASHBOARD ---
st.title("🏹 MKPV SNIPER | OI & VOLUME ANALYSIS")
st.divider()

if st.session_state.connected:
    try:
        # 1. Fetch Spot Price
        t_sym = "Nifty 50" if idx == "NIFTY" else "Nifty Bank"
        t_tok = "26000" if idx == "NIFTY" else "26009"
        
        spot_res = st.session_state.obj.ltpData("NSE", t_sym, t_tok)
        if spot_res['status']:
            ltp = float(spot_res['data']['ltp'])
            step = 50 if idx == "NIFTY" else 100
            atm = int(round(ltp / step) * step)

            # 2. Build Option Symbols (Format: NIFTY02APR2622600CE)
            ce_symbol = f"{idx.upper()}{expiry}{atm}CE"
            pe_symbol = f"{idx.upper()}{expiry}{atm}PE"

            # 3. Fetch Full Quote (OI + Volume + LTP)
            # Note: For OI/Vol, we use 'getQuote' API
            # Note: Option Tokens are unique, for now using dummy placeholder logic
            # To get real tokens, you need to download Angel's Scrip Master JSON.
            
            st.subheader(f"📊 Market Structure: {idx} (ATM @ {atm})")
            c1, c2, c3 = st.columns(3)
            c1.metric("SPOT PRICE", f"₹{ltp}")
            c2.metric("RESISTANCE (Approx)", f"₹{atm + step}")
            c3.metric("SUPPORT (Approx)", f"₹{atm - step}")

            st.divider()

            # 4. Call vs Put Analysis
            col_ce, col_pe = st.columns(2)
            
            with col_ce:
                st.markdown("### 🟢 CALL (CE) Data")
                st.info(f"Symbol: {ce_symbol}")
                st.metric("CE LTP", "₹--", help="Needs Option Token")
                st.metric("CE OI", "0", delta="-2% (Short Covering)", delta_color="normal")
                st.progress(40, text="Call Writing Pressure")

            with col_pe:
                st.markdown("### 🔴 PUT (PE) Data")
                st.info(f"Symbol: {pe_symbol}")
                st.metric("PE LTP", "₹--", help="Needs Option Token")
                st.metric("PE OI", "0", delta="+15% (Long Buildup)", delta_color="inverse")
                st.progress(75, text="Put Writing Strength (Support)")

            st.success("Bhai, Support/Resistance find karne ke liye humein PCR (Put Call Ratio) calculate karna hoga.")

        else:
            st.session_state.connected = False
            st.rerun()

    except Exception as e: st.error(f"Error: {e}")
    
    time.sleep(2)
    st.rerun()
else:
    st.warning("Sniper Offline. Please Connect Sidebar.")
