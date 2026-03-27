import streamlit as st
import pandas as pd
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import pyotp
import re
import time
import threading

# --- Page Config ---
st.set_page_config(page_title="GRK WARRIOR PRO", layout="wide")

# --- Initialize Session States ---
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'ltp_data' not in st.session_state:
    st.session_state.ltp_data = {"NIFTY": 0, "BANKNIFTY": 0}
if 'oi_data' not in st.session_state:
    st.session_state.oi_data = {"NIFTY": 0, "BANKNIFTY": 0}
if 'error_msg' not in st.session_state:
    st.session_state.error_msg = ""

# --- Helper Functions ---
def clean_and_fix_key(key):
    key = re.sub(r'\s+', '', key).upper()
    key = re.sub(r'[^A-Z2-7]', '', key)
    missing_padding = len(key) % 8
    if missing_padding:
        key += '=' * (8 - missing_padding)
    return key

# --- WebSocket Setup ---
def on_data(wsapp, msg):
    token = msg.get('token')
    # Angel One sends price in paise, so divide by 100
    price = msg.get('last_traded_price', 0) / 100
    oi = msg.get('open_interest', 0)
    
    if token == "26000":
        st.session_state.ltp_data["NIFTY"] = price
        st.session_state.oi_data["NIFTY"] = oi
    elif token == "26009":
        st.session_state.ltp_data["BANKNIFTY"] = price
        st.session_state.oi_data["BANKNIFTY"] = oi

def start_websocket(jwt, api_key, client_id, feed_token):
    try:
        sws = SmartWebSocketV2(jwt, api_key, client_id, feed_token)
        sws.on_data = on_data
        def on_open(wsapp):
            # Subscribe to Nifty (26000) and BankNifty (26009)
            tokens = [{"exchangeType": 1, "tokens": ["26000", "26009"]}]
            sws.subscribe("grk_warrior_v3", 3, tokens)
        
        sws.on_open = on_open
        sws.connect()
    except Exception as e:
        st.session_state.error_msg = f"WebSocket Error: {str(e)}"

# --- Sidebar UI ---
st.sidebar.title("🔑 Bot Authentication")
index_choice = st.sidebar.radio("Select Index", ["NIFTY", "BANKNIFTY"])

# Yahan apni actual API Key bhariye
api_key_input = st.sidebar.text_input("API Key", placeholder="Enter your Angel Trading API Key")
client_id = st.sidebar.text_input("Client ID", value="P51646259")
password = st.sidebar.text_input("Angel Password", type="password")
totp_key_input = st.sidebar.text_input("TOTP Secret Key", type="password")

if st.sidebar.button("Start GRK Warrior"):
    if not api_key_input or not totp_key_input or not password:
        st.sidebar.error("Sari details bhariye!")
    else:
        try:
            # 1. Fix TOTP Key & Generate OTP
            final_key = clean_and_fix_key(totp_key_input)
            totp_gen = pyotp.TOTP(final_key)
            current_otp = totp_gen.now()
            
            # 2. Authenticate
            obj = SmartConnect(api_key=api_key_input)
            data = obj.generateSession(client_id, password, current_otp)
            
            if data['status']:
                st.session_state.connected = True
                feed_token = obj.getfeedToken()
                
                # 3. Start WebSocket in Background Thread
                t = threading.Thread(target=start_websocket, 
                                     args=(data['data']['jwtToken'], api_key_input, client_id, feed_token))
                t.daemon = True
                t.start()
                
                st.sidebar.success("✅ Bot Connected!")
            else:
                st.sidebar.error(f"❌ Login Failed: {data['message']}")
        except Exception as e:
            st.sidebar.error(f"⚠️ Connection Error: {str(e)}")

# --- Main Dashboard ---
st.title("🚀 MKPV ULTRA SNIPER V3 | ANGEL-ONE LIVE")

if st.session_state.error_msg:
    st.error(st.session_state.error_msg)

st.subheader("🛠️ Data Pipeline Status")
col1, col2, col3 = st.columns(3)

# LTP Metric
current_ltp = st.session_state.ltp_data.get(index_choice, 0)
ltp_status = "✅" if current_ltp > 0 else "❌"
col1.metric(label=f"LTP ({index_choice}): {ltp_status}", value=f"₹{current_ltp}")

# History Metric
col2.metric(label="History: ✅", value="Connected")

# OI Metric
current_oi = st.session_state.oi_data.get(index_choice, 0)
oi_status = "✅" if current_oi > 0 else "❌"
col3.metric(label=f"OI Data: {oi_status}", value=f"{current_oi}")

# --- Auto Refresh ---
if st.session_state.connected:
    time.sleep(1)
    st.rerun()
