import streamlit as st
from SmartApi import SmartConnect
import pyotp
import requests
import time

# --- CONFIG ---
FIXED_CLIENT_ID = "P51646259"
MY_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

def get_internet_time():
    """Bina ntplib ke internet se sahi waqt lena"""
    try:
        response = requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5)
        return response.json()['unixtime']
    except:
        return time.time() # Fail hone par system time

st.sidebar.title("🚀 GRK SNIPER V11.1")

if st.sidebar.button("🚀 Sync & Connect"):
    try:
        # Internet ke sahi waqt se OTP nikalna
        accurate_time = get_internet_time()
        totp = pyotp.TOTP(MY_SECRET.strip().replace(" ", ""))
        accurate_otp = totp.at(accurate_time)
        
        st.sidebar.info(f"Generated OTP: {accurate_otp}")

        # Login Attempt
        obj = SmartConnect(api_key="MT72qa1q")
        # Apna 4-digit MPIN yahan daalein
        data = obj.generateSession(FIXED_CLIENT_ID, "1234", accurate_otp) 
        
        if data['status']:
            st.sidebar.success("✅ Login Success!")
            st.session_state.connected = True
        else:
            st.sidebar.error(f"❌ Error: {data['message']}")
    except Exception as e:
        st.sidebar.error(f"❌ Error: {e}")
