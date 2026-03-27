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

# --- Sidebar UI ---
st.sidebar.title("🔑 Bot Authentication")
index_choice = st.sidebar.radio("Select Index", ["NIFTY", "BANKNIFTY"])
client_id = st.sidebar.text_input("Client ID")
password = st.sidebar.text_input("Angel Password", type="password")
totp_key = st.sidebar.text_input("TOTP Secret Key", type="password")

# --- WebSocket Callbacks ---
def on_data(wsapp, msg):
    token = msg.get('token')
    price = msg.get('last_traded_price', 0) / 100
    oi = msg.get('open_interest', 0)
    
    if token == "26000":
        st.session_state.ltp_data["NIFTY"] = price
        st.session_state.ltp_data["NIFTY_OI"] = oi
    elif token == "26009":
        st.session_state.ltp_data["BANKNIFTY"] = price
        st.session_state.ltp_data["BANKNIFTY_OI"] = oi

def start_websocket(jwt, api_key, client_id, feed_token):
    sws = SmartWebSocketV2(jwt, api_key, client_id, feed_token)
    sws.on_data = on_data
    sws.on_open = lambda ws: sws.subscribe("grk_warrior", 3, [{"exchangeType": 1, "tokens": ["26000", "26009"]}])
    sws.connect()

# --- Login Logic ---
if st.sidebar.button("Start GRK Warrior"):
    # CLEANING THE KEY (Fix for binascii error)
    clean_key = re.sub(r'[^A-Z2-7]', '', totp_key.upper().replace(" ", ""))
    
    try:
        obj = SmartConnect(api_key="YOUR_TRADING_API_KEY") # Apni API Key yahan dalo
        token = pyotp.TOTP(clean_key).now()
        data = obj.generateSession(client_id, password, token)
        
        if data['status']:
            st.session_state.connected = True
            feed_token = obj.getfeedToken()
            
            # Start WebSocket in a separate thread to keep Streamlit alive
            t = threading.Thread(target=start_websocket, args=(data['data']['jwtToken'], "YOUR_TRADING_API_KEY", client_id, feed_token))
            t.daemon = True
            t.start()
            
            st.sidebar.success("Bot Connected Successfully!")
        else:
            st.sidebar.error(f"Login Failed: {data['message']}")
    except Exception as e:
        st.sidebar.error(f"Error: {str(e)}")

# --- Main Dashboard ---
st.title("🚀 MKPV ULTRA SNIPER V3 | ANGEL-ONE LIVE")
st.subheader("🛠️ Data Pipeline Status")

col1, col2, col3 = st.columns(3)

# LTP Status
with col1:
    val = st.session_state.ltp_data.get(index_choice, 0)
    status = "✅" if val > 0 else "❌"
    st.metric(label=f"LTP: {status}", value=f"₹{val}")

# History Status (Static for now)
with col2:
    st.metric(label="History: ✅", value="Connected")

# OI Data Status
with col3:
    oi_val = st.session_state.ltp_data.get(f"{index_choice}_OI", 0)
    status_oi = "✅" if oi_val > 0 else "❌"
    st.metric(label=f"OI Data: {status_oi}", value=oi_val)

# Auto Refresh UI
if st.session_state.connected:
    time.sleep(1)
    st.rerun()
