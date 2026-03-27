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

# --- Function to Fix TOTP Padding ---
def clean_and_fix_key(key):
    # Spaces hatayein aur uppercase karein
    key = re.sub(r'\s+', '', key).upper()
    # Sirf A-Z aur 2-7 characters rakhein
    key = re.sub(r'[^A-Z2-7]', '', key)
    # Padding fix karein (Must be multiple of 8)
    missing_padding = len(key) % 8
    if missing_padding:
        key += '=' * (8 - missing_padding)
    return key

# --- WebSocket Callbacks ---
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

def start_websocket(jwt, api_key, client_id, feed_token):
    try:
        sws = SmartWebSocketV2(jwt, api_key, client_id, feed_token)
        sws.on_data = on_data
        sws.on_open = lambda ws: sws.subscribe("grk_warrior", 3, [{"exchangeType": 1, "tokens": ["26000", "26009"]}])
        sws.connect()
    except Exception as e:
        print(f"WS Error: {e}")

# --- Sidebar UI ---
st.sidebar.title("🔑 Bot Authentication")
index_choice = st.sidebar.radio("Select Index", ["NIFTY", "BANKNIFTY"])
api_key = st.sidebar.text_input("API Key", value="YOUR_API_KEY") # Apni Key Daalein
client_id = st.sidebar.text_input("Client ID", value="P51646259")
password = st.sidebar.text_input("Angel Password", type="password")
totp_key_input = st.sidebar.text_input("TOTP Secret Key", type="password")

if st.sidebar.button("Start GRK Warrior"):
    if not totp_key_input:
        st.sidebar.error("TOTP Key is missing!")
    else:
        try:
            # Padding Fix Apply Karein
            final_key = clean_and_fix_key(totp_key_input)
            totp_gen = pyotp.TOTP(final_key)
            current_otp = totp_gen.now()
            
            obj = SmartConnect(api_key=api_key)
            data = obj.generateSession(client_id, password, current_otp)
            
            if data['status']:
                st.session_state.connected = True
                feed_token = obj.getfeedToken()
                
                # WebSocket ko alag thread mein chalayein
                t = threading.Thread(target=start_websocket, args=(data['data']['jwtToken'], api_key, client_id, feed_token))
                t.daemon = True
                t.start()
                
                st.sidebar.success("✅ Bot Connected Successfully!")
            else:
                st.sidebar.error(f"❌ Login Failed: {data['message']}")
        except Exception as e:
            st.sidebar.error(f"⚠️ Logic Error: {str(e)}")

# --- Main Dashboard ---
st.title("🚀 MKPV ULTRA SNIPER V3 | ANGEL-ONE LIVE")
st.subheader("🛠️ Data Pipeline Status")

col1, col2, col3 = st.columns(3)

with col1:
    val = st.session_state.ltp_data.get(index_choice, 0)
    status = "✅" if val > 0 else "❌"
    st.metric(label=f"LTP: {status}", value=f"₹{val}")

with col2:
    st.metric(label="History: ✅", value="Connected")

with col3:
    oi_val = st.session_state.oi_data.get(index_choice, 0)
    status_oi = "✅" if oi_val > 0 else "❌"
    st.metric(label=f"OI Data: {status_oi}", value=oi_val)

# Auto Refresh logic
if st.session_state.connected:
    time.sleep(1)
    st.rerun()
