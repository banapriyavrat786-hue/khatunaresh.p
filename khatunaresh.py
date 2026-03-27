import streamlit as st
import pandas as pd
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import pyotp
import re
import time
import threading

# ==========================================
# 1. FIXED CONFIGURATION (Yahan Details Fix Hain)
# ==========================================
FIXED_API_KEY = "W6SCERQJX4RSU6TXECROABI7TA" # Aapke screenshot se li gayi
FIXED_CLIENT_ID = "P51646259"

# --- Page Config ---
st.set_page_config(page_title="GRK WARRIOR PRO", layout="wide")

# --- Initialize Session States ---
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'ltp_data' not in st.session_state:
    st.session_state.ltp_data = {"NIFTY": 0.0, "BANKNIFTY": 0.0}
if 'oi_data' not in st.session_state:
    st.session_state.oi_data = {"NIFTY": 0, "BANKNIFTY": 0}

# --- Function to Fix TOTP Padding & Spaces ---
def clean_totp(key):
    key = re.sub(r'\s+', '', key).upper()
    key = re.sub(r'[^A-Z2-7]', '', key)
    missing_padding = len(key) % 8
    if missing_padding:
        key += '=' * (8 - missing_padding)
    return key

# --- WebSocket Setup ---
def on_data(wsapp, msg):
    token = msg.get('token')
    price = msg.get('last_traded_price', 0) / 100
    oi = msg.get('open_interest', 0)
    
    if token == "26000":
        st.session_state.ltp_data["NIFTY"] = price
        st.session_state.oi_data["NIFTY"] = oi
    elif token == "26009":
        st.session_state.ltp_data["BANKNIFTY"] = price
        st.session_state.oi_data["BANKNIFTY"] = oi

def start_ws(jwt, feed_token):
    try:
        sws = SmartWebSocketV2(jwt, FIXED_API_KEY, FIXED_CLIENT_ID, feed_token)
        sws.on_data = on_data
        sws.on_open = lambda ws: sws.subscribe("grk_warrior", 3, [{"exchangeType": 1, "tokens": ["26000", "26009"]}])
        sws.connect()
    except Exception as e:
        print(f"WebSocket Connection Error: {e}")

# --- Sidebar UI ---
st.sidebar.title("🔑 GRK Bot Login")
st.sidebar.info(f"Client ID: {FIXED_CLIENT_ID}")
index_choice = st.sidebar.radio("Select Index", ["NIFTY", "BANKNIFTY"])

# Sirf ye do cheezein aapko daalni hongi
password = st.sidebar.text_input("Angel Password", type="password")
totp_secret = st.sidebar.text_input("TOTP Secret Key (Alphanumeric)", type="password")

if st.sidebar.button("🚀 Start Sniper Bot"):
    if not password or not totp_secret:
        st.sidebar.warning("Password aur TOTP Secret dono daalein!")
    else:
        try:
            # 1. Clean and Generate TOTP
            clean_key = clean_totp(totp_secret)
            otp = pyotp.TOTP(clean_key).now()
            
            # 2. Login to Angel One
            obj = SmartConnect(api_key=FIXED_API_KEY)
            data = obj.generateSession(FIXED_CLIENT_ID, password, otp)
            
            if data['status']:
                st.session_state.connected = True
                ft = obj.getfeedToken()
                jwt = data['data']['jwtToken']
                
                # 3. Start Threaded WebSocket
                t = threading.Thread(target=start_ws, args=(jwt, ft))
                t.daemon = True
                t.start()
                
                st.sidebar.success("✅ Bot Connected Successfully!")
            else:
                st.sidebar.error(f"❌ Login Failed: {data['message']}")
        except Exception as e:
            st.sidebar.error(f"⚠️ Error: {str(e)}")

# --- Main Dashboard ---
st.title("🚀 MKPV ULTRA SNIPER V3 | LIVE")
st.divider()

col1, col2, col3 = st.columns(3)

# Display Metrics
l_val = st.session_state.ltp_data[index_choice]
o_val = st.session_state.oi_data[index_choice]

with col1:
    st.metric(label=f"LTP ({index_choice})", value=f"₹{l_val}", delta="LIVE" if l_val > 0 else None)
with col2:
    st.metric(label="Data Pipeline", value="Connected ✅" if st.session_state.connected else "Offline ❌")
with col3:
    st.metric(label=f"Open Interest (OI)", value=o_val, delta="Updated" if o_val > 0 else None)

# --- Auto-Refresh ---
if st.session_state.connected:
    time.sleep(1)
    st.rerun()
