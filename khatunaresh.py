import streamlit as st
from SmartApi import SmartConnect
import pyotp
import ntplib
from datetime import datetime
import time

# --- CONFIG ---
FIXED_CLIENT_ID = "P51646259"
MY_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

def get_accurate_now():
    """Network se bilkul sahi waqt nikalne ke liye"""
    try:
        client = ntplib.NTPClient()
        response = client.request('pool.ntp.org', version=3)
        return response.tx_time
    except:
        # Agar network fail ho toh system time (Lekin ye galat ho sakta hai)
        return time.time()

st.sidebar.title("🚀 GRK SNIPER V11")

if st.sidebar.button("🚀 Connect with Sync Time"):
    try:
        # 1. Asli waqt ke hisab se OTP generate karna
        accurate_time = get_accurate_now()
        totp = pyotp.TOTP(MY_SECRET.strip().replace(" ", ""))
        # Force OTP generation based on network time
        accurate_otp = totp.at(accurate_time)
        
        st.sidebar.info(f"Generated OTP: {accurate_otp}")

        # 2. Login Attempt
        obj = SmartConnect(api_key="MT72qa1q")
        # MPIN yahan 1234 ki jagah apna asli daalein
        data = obj.generateSession(FIXED_CLIENT_ID, "1234", accurate_otp) 
        
        if data['status']:
            st.sidebar.success("✅ BINGO! Login Success.")
            st.session_state.connected = True
        else:
            st.sidebar.error(f"❌ Abhi bhi error: {data['message']}")
            
    except Exception as e:
        st.sidebar.error(f"❌ Error: {e}")

st.write("### 🕒 Time Debug Info")
st.write(f"Server Time (Galat): {datetime.now().strftime('%H:%M:%S')}")
st.write(f"Network Time (Sahi): {datetime.fromtimestamp(get_accurate_now()).strftime('%H:%M:%S')}")
