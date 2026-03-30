import streamlit as st
from SmartApi import SmartConnect
import pyotp
import requests
import time

# --- CONFIG ---
FIXED_CLIENT_ID = "P51646259"
MY_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

def get_internet_time():
    try:
        response = requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5)
        return response.json()['unixtime']
    except:
        return time.time()

st.sidebar.title("🚀 GRK SNIPER V11.2")

# Sidebar mein MPIN ka option
user_mpin = st.sidebar.text_input("Apna 4-Digit MPIN daalein", type="password", max_chars=4)

if st.sidebar.button("🚀 Sync & Connect"):
    if len(user_mpin) != 4:
        st.sidebar.error("Kripya sahi 4-digit MPIN daalein!")
    else:
        try:
            accurate_time = get_internet_time()
            totp = pyotp.TOTP(MY_SECRET.strip().replace(" ", ""))
            accurate_otp = totp.at(accurate_time)
            
            st.sidebar.info(f"Generated OTP: {accurate_otp}")

            obj = SmartConnect(api_key="MT72qa1q")
            # Ab ye wahi MPIN use karega jo aapne sidebar mein dala hai
            data = obj.generateSession(FIXED_CLIENT_ID, user_mpin, accurate_otp) 
            
            if data['status']:
                st.sidebar.success("✅ BINGO! Login Success.")
                st.session_state.connected = True
            else:
                st.sidebar.error(f"❌ Error: {data['message']}")
        except Exception as e:
            st.sidebar.error(f"❌ Error: {e}")
