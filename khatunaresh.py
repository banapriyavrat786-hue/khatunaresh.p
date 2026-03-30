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
    except:
        return time.time()

if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None

st.set_page_config(page_title="GRK WARRIOR DASHBOARD", layout="wide")

# --- SIDEBAR LOGIN ---
st.sidebar.title("🚀 GRK SNIPER V12")
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
        else:
            st.sidebar.error(f"❌ Error: {data['message']}")
    except Exception as e:
        st.sidebar.error(f"❌ Error: {e}")

# --- MAIN DASHBOARD ---
if st.session_state.connected:
    st.title("🎯 MKPV LIVE TRADING TERMINAL")
    st.divider()

    # 1. Fetch Profile & Funds
    profile = st.session_state.obj.getProfile()
    funds = st.session_state.obj.getMarginDetails()
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("User", profile['data']['name'])
    with c2:
        # Available Cash
        cash = funds['data']['net'] if funds['status'] else "0.0"
        st.metric("Available Margin", f"₹{cash}")
    with c3:
        st.metric("Status", "LIVE 🟢")

    st.divider()

    # 2. LIVE PRICE TICKER
    st.subheader("📊 Market Watch")
    cols = st.columns(2)
    
    indices = [
        {"name": "NIFTY 50", "token": "26000"},
        {"name": "BANKNIFTY", "token": "26009"}
    ]

    for i, index in enumerate(indices):
        res = st.session_state.obj.ltpData("NSE", index['name'], index['token'])
        if res['status']:
            price = res['data']['ltp']
            cols[i].metric(index['name'], f"₹{price}", delta="Live")

    # 3. QUICK TRADE BUTTONS (Placeholder)
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚡ Quick Sniper Actions")
    if st.sidebar.button("BUY ATM CALL"):
        st.sidebar.info("Strategy logic loading...")
    if st.sidebar.button("BUY ATM PUT"):
        st.sidebar.info("Strategy logic loading...")

    time.sleep(2)
    st.rerun()

else:
    st.info("👈 Login from sidebar to access Warrior Dashboard.")
