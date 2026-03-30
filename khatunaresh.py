import streamlit as st
from SmartApi import SmartConnect
import pyotp
import requests
import time

# --- CONFIG ---
FIXED_CLIENT_ID = "P51646259"
MY_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

def get_internet_time():
    try:
        response = requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5)
        return response.json()['unixtime']
    except: return time.time()

if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None

st.set_page_config(page_title="GRK WARRIOR V13", layout="wide")

# --- SIDEBAR LOGIN ---
st.sidebar.title("🚀 GRK WARRIOR V13")
user_mpin = st.sidebar.text_input("Enter 4-Digit MPIN", type="password", max_chars=4)

if st.sidebar.button("🚀 Sync & Connect"):
    try:
        accurate_time = get_internet_time()
        otp = pyotp.TOTP(MY_SECRET.strip().replace(" ", "")).at(accurate_time)
        obj = SmartConnect(api_key="MT72qa1q")
        data = obj.generateSession(FIXED_CLIENT_ID, user_mpin, otp)
        if data['status']:
            st.session_state.obj = obj
            st.session_state.connected = True
            st.sidebar.success("✅ Login Success!")
    except Exception as e: st.sidebar.error(f"❌ Error: {e}")

# --- DASHBOARD ---
if st.session_state.connected:
    st.title("🎯 MKPV LIVE TERMINAL | OI ANALYSIS")
    
    # 1. LIVE PRICE & ATM CALCULATION
    c1, c2 = st.columns(2)
    indices = [
        {"name": "Nifty 50", "token": "26000", "step": 50},
        {"name": "Nifty Bank", "token": "26009", "step": 100}
    ]

    for i, idx in enumerate(indices):
        res = st.session_state.obj.ltpData("NSE", idx['name'], idx['token'])
        if res['status']:
            price = float(res['data']['ltp'])
            atm = int(round(price / idx['step']) * idx['step'])
            c1 if i==0 else c2
            st.metric(idx['name'], f"₹{price}", help=f"ATM Strike: {atm}")

    st.divider()

    # 2. OPTION CHAIN ANALYZER (Placeholder for now)
    st.subheader("📊 Market Sentiment (PCR & OI)")
    
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("PCR (Put-Call Ratio)", "1.05", delta="Bullish Bias")
    col_b.metric("Support Strike", "22450", delta="Strong")
    col_c.metric("Resistance Strike", "22600", delta="Strong")

    # 3. QUICK EXECUTION PANEL
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚡ Sniper Trigger")
    trade_lot = st.sidebar.number_input("Lot Size", value=1)
    
    if st.sidebar.button("BUY ATM CALL"):
        st.sidebar.warning("Buying Signal... Token mapping required.")
    
    if st.sidebar.button("BUY ATM PUT"):
        st.sidebar.warning("Selling Signal... Token mapping required.")

    time.sleep(2)
    st.rerun()
else:
    st.info("👈 Login from sidebar to access Terminal.")
