import streamlit as st
from SmartApi import SmartConnect
import pyotp
import time
import datetime

# --- AAPKA SAHI DATA ---
FIXED_CLIENT_ID = "P51646259" 
MY_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.sidebar.title("🛠️ Login Debugger")

# 1. Check System Time
now = datetime.datetime.now()
st.sidebar.write(f"Sytem Time: {now.strftime('%H:%M:%S')}")

# 2. Manual TOTP Check
if st.sidebar.button("Generate Test OTP"):
    clean_secret = MY_SECRET.strip().replace(" ", "")
    totp = pyotp.TOTP(clean_secret)
    current_otp = totp.now()
    st.sidebar.info(f"Aapka Current OTP: {current_otp}")
    st.sidebar.write("Ise apne mobile app ke OTP se milaiye. Agar match nahi ho raha, toh Time Sync kijiye.")

# 3. Login Attempt
if st.sidebar.button("Try Login Again"):
    try:
        otp = pyotp.TOTP(MY_SECRET.strip().replace(" ", "")).now()
        obj = SmartConnect(api_key="MT72qa1q")
        data = obj.generateSession(FIXED_CLIENT_ID, "1234", otp) # '1234' ki jagah apna sahi MPIN daalein
        
        if data['status']:
            st.sidebar.success("✅ Finally Connected!")
        else:
            st.sidebar.error(f"❌ Server Reject: {data['message']}")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")
