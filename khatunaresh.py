import streamlit as st
from SmartApi import SmartConnect
import pyotp
import re
import time

# ==========================================
# CONFIGURATION
# ==========================================
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

st.sidebar.markdown("---")
st.sidebar.subheader("🔑 Login Details")

# Aapki default keys maine fix kar di hain
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
            
            # Auth Request
            obj = SmartConnect(api_key=api_key_input.strip())
            data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
            
            if data['status']:
                # 🎯 THE REAL FIX: Save the entire working object, not just tokens
                st.session_state.smart_obj = obj 
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
            
        # 🎯 FIX: Use the saved object directly
        ltp_response = st.session_state.smart_obj.ltpData("NSE", trading_symbol, token)
        
        if isinstance(ltp_response, dict) and ltp_response.get('status'):
            live_price = ltp_response['data']['ltp']
            
            c1.metric(f"LTP {idx}", f"₹{live_price}", delta="LIVE Stream")
            c2.metric("Pipeline Status", "Online ✅")
            c3.metric(f"OI {idx}", "0", help="Spot Index par OI nahi hota.")
        else:
            st.error(f"Angel API Error during data fetch: {ltp_response.get('message', 'Unknown Error')}")
            
    except Exception as e:
        st.error(f"Data Fetch Exception: {e}")
        
    time.sleep(2)
    st.rerun()
else:
    c1.metric(f"LTP {idx}", "₹0")
    c2.metric("Pipeline Status", "Offline ❌")
    c3.metric(f"OI {idx}", "0")
