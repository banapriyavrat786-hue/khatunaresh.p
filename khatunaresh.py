import streamlit as st
from SmartApi import SmartConnect
import pyotp
import re
import time
import requests # 🎯 NAYA IMPORT: Direct API calling ke liye

# ==========================================
# CONFIGURATION
# ==========================================
FIXED_CLIENT_ID = "P51646259"
LTP_URL = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/getLtpData"

st.set_page_config(page_title="GRK WARRIOR PRO", layout="wide")

# --- Session States ---
if 'jwt_token' not in st.session_state:
    st.session_state.jwt_token = None
if 'api_key' not in st.session_state:
    st.session_state.api_key = None
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'last_price' not in st.session_state:
    st.session_state.last_price = 0.0

def clean_totp(key):
    key = re.sub(r'\s+', '', key).upper()
    key = re.sub(r'[^A-Z2-7]', '', key)
    padding = len(key) % 8
    if padding: key += '=' * (8 - padding)
    return key

# --- Sidebar UI ---
st.sidebar.title("🚀 GRK WARRIOR V3")
idx = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])

st.sidebar.markdown("---")
st.sidebar.subheader("🔑 Login Details")

# Aapki default keys set kar di hain
api_key_input = st.sidebar.text_input("1. SmartAPI Key", value="MT72qa1q")
mpin = st.sidebar.text_input("2. Angel 4-Digit MPIN", type="password", max_chars=4)
totp_secret = st.sidebar.text_input("3. TOTP Secret Key", type="password", value="W6SCERQJX4RSU6TXECROABI7TA")

if st.sidebar.button("Connect Bot"):
    if not api_key_input or not totp_secret or not mpin:
        st.sidebar.error("Sari details bharna zaroori hai!")
    else:
        try:
            clean_key = clean_totp(totp_secret)
            otp = pyotp.TOTP(clean_key).now()
            
            # Login ke liye library use karenge
            obj = SmartConnect(api_key=api_key_input.strip())
            data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
            
            if data['status']:
                # 🎯 Fix: Sirf Token save karenge, object nahi
                st.session_state.jwt_token = data['data']['jwtToken']
                st.session_state.api_key = api_key_input.strip()
                st.session_state.connected = True
                st.sidebar.success("✅ Bot Successfully Live!")
            else:
                st.sidebar.error(f"❌ Login Failed: {data['message']}")
        except Exception as e:
            st.sidebar.error(f"Error during login: {e}")

# --- Dashboard Layout ---
st.title("🚀 MKPV ULTRA SNIPER V3 | LIVE (REST)")
st.divider()

c1, c2, c3 = st.columns(3)

if st.session_state.connected:
    try:
        if idx == "NIFTY":
            trading_symbol = "Nifty 50"
            token = "26000"
        else:
            trading_symbol = "Nifty Bank"
            token = "26009"
            
        # 🎯 100% BULLETPROOF FIX: Direct HTTP Request bypassing the buggy library
        headers = {
            "Authorization": f"Bearer {st.session_state.jwt_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": st.session_state.api_key
        }
        
        payload = {
            "exchange": "NSE",
            "tradingsymbol": trading_symbol,
            "symboltoken": token
        }
        
        response = requests.post(LTP_URL, json=payload, headers=headers).json()
        
        if response.get('status'):
            live_price = response['data']['ltp']
            st.session_state.last_price = live_price # Price save kar liya
            
            c1.metric(f"LTP {idx}", f"₹{live_price}", delta="LIVE Stream")
            c2.metric("Pipeline Status", "Online ✅")
            c3.metric(f"OI {idx}", "0", help="Spot Index par OI nahi hota.")
        else:
            # Agar choti moti error aayi toh purana price dikhata rahega
            c1.metric(f"LTP {idx}", f"₹{st.session_state.last_price}", delta="Reconnecting...")
            c2.metric("Pipeline Status", "Warning ⚠️")
            c3.metric(f"OI {idx}", "0")
            st.error(f"Angel API Error: {response.get('message', 'Unknown Error')}")
            
    except Exception as e:
        st.error(f"Data Fetch Exception: {e}")
        
    time.sleep(2)
    st.rerun()
else:
    c1.metric(f"LTP {idx}", "₹0")
    c2.metric("Pipeline Status", "Offline ❌")
    c3.metric(f"OI {idx}", "0")
