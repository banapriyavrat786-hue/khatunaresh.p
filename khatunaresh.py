import streamlit as st
from SmartApi import SmartConnect
import pyotp
import re
import time

# ==========================================
# CONFIGURATION
# ==========================================
FIXED_API_KEY = "W6SCERQJX4RSU6TXECROABI7TA"
FIXED_CLIENT_ID = "P51646259"

st.set_page_config(page_title="GRK WARRIOR PRO", layout="wide")

# --- Session States ---
if 'smart_obj' not in st.session_state:
    st.session_state.smart_obj = None
if 'connected' not in st.session_state:
    st.session_state.connected = False

def clean_totp(key):
    key = re.sub(r'\s+', '', key).upper()
    key = re.sub(r'[^A-Z2-7]', '', key)
    padding = len(key) % 8
    if padding: key += '=' * (8 - padding)
    return key

# --- Sidebar UI ---
st.sidebar.title("🚀 GRK WARRIOR V3")
idx = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])

mpin = st.sidebar.text_input("Angel 4-Digit MPIN", type="password", max_chars=4)
totp_secret = st.sidebar.text_input("True TOTP Secret Key", type="password")

if st.sidebar.button("Connect Bot"):
    if not totp_secret or not mpin:
        st.sidebar.error("MPIN aur Secret Key dono zaroori hain!")
    else:
        try:
            clean_key = clean_totp(totp_secret)
            otp = pyotp.TOTP(clean_key).now()
            
            obj = SmartConnect(api_key=FIXED_API_KEY)
            data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
            
            if data['status']:
                st.session_state.smart_obj = obj
                st.session_state.connected = True
                st.sidebar.success("✅ Bot Successfully Live!")
            else:
                st.sidebar.error(f"❌ Login Failed: {data['message']}")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

# --- Dashboard Layout ---
st.title("🚀 MKPV ULTRA SNIPER V3 | LIVE (REST MODE)")
st.divider()

c1, c2, c3 = st.columns(3)

if st.session_state.connected:
    try:
        # 🎯 FIX: Angel One ke exact trading symbols use kiye hain
        if idx == "NIFTY":
            trading_symbol = "Nifty 50"
            token = "26000"
        else:
            trading_symbol = "Nifty Bank"
            token = "26009"
            
        ltp_response = st.session_state.smart_obj.ltpData("NSE", trading_symbol, token)
        
        # 🛡️ FIX: Safe dictionary check taaki KeyError na aaye
        if isinstance(ltp_response, dict) and ltp_response.get('status'):
            live_price = ltp_response['data']['ltp']
            
            c1.metric(f"LTP {idx}", f"₹{live_price}", delta="LIVE Stream")
            c2.metric("Pipeline Status", "Online ✅")
            c3.metric(f"OI {idx}", "0", help="Spot Index par OI nahi hota.")
        else:
            # Agar limit cross hui ya market band hua toh error saaf dikhega
            st.error(f"Angel API Error: {ltp_response.get('message', 'Unknown Error')}")
            
    except Exception as e:
        st.error(f"Data Fetch Error: {e}")
        
    # Auto-Refresh loop (2 second ka gap taaki API block na kare)
    time.sleep(2)
    st.rerun()
else:
    # Default State
    c1.metric(f"LTP {idx}", "₹0")
    c2.metric("Pipeline Status", "Offline ❌")
    c3.metric(f"OI {idx}", "0")
