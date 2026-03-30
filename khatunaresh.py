import streamlit as st
from SmartApi import SmartConnect
import pyotp
import pandas as pd
import requests
import time
from datetime import datetime

# ========= CONFIG =========
API_KEY = "MT72qa1q"
CLIENT_ID = "P51646259"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(layout="wide")
st.title("🚀 MKPV SNIPER PRO MAX")

# ========= SESSION =========
if "connected" not in st.session_state:
    st.session_state.connected = False
if "obj" not in st.session_state:
    st.session_state.obj = None
if "df" not in st.session_state:
    st.session_state.df = None

# ========= FUNCTIONS =========
def get_time():
    try:
        return requests.get(
            "http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5
        ).json()["unixtime"]
    except:
        return int(time.time())

@st.cache_data(ttl=3600)
def load_tokens():
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    data = requests.get(url).json()
    df = pd.DataFrame(data)
    df["expiry"] = pd.to_datetime(df["expiry"]).dt.date
    return df

def reconnect():
    try:
        otp = pyotp.TOTP(TOTP_SECRET).at(get_time())
        res = st.session_state.obj.generateSession(
            CLIENT_ID, st.session_state.mpin, otp
        )
        return res.get("status", False)
    except:
        return False

# ========= SIDEBAR =========
st.sidebar.title("Controls")

index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
mpin = st.sidebar.text_input("MPIN", type="password", max_chars=4)

if st.sidebar.button("🔑 Connect"):
    if len(mpin) != 4:
        st.sidebar.error("Enter 4 digit MPIN")
    else:
        st.session_state.mpin = mpin
        otp = pyotp.TOTP(TOTP_SECRET).at(get_time())

        st.sidebar.info(f"OTP: {otp}")

        obj = SmartConnect(api_key=API_KEY)
        data = obj.generateSession(CLIENT_ID, mpin, otp)

        if data.get("status"):
            st.sidebar.success("✅ Connected")
            st.session_state.connected = True
            st.session_state.obj = obj
            st.session_state.df = load_tokens()
            st.sidebar.success("Tokens Loaded")
        else:
            st.sidebar.error(data.get("message"))

# ========= MAIN =========
col1, col2, col3 = st.columns(3)

if st.session_state.connected:

    obj = st.session_state.obj
    df = st.session_state.df

    try:
        # -------- SPOT --------
        if index == "NIFTY":
            symbol = "Nifty 50"
            token = "26000"
            name = "NIFTY"
        else:
            symbol = "Nifty Bank"
            token = "26009"
            name = "BANKNIFTY"

        res = obj.ltpData("NSE", symbol, token)

        if not res.get("status"):
            st.error("Session expired")
            if reconnect():
                st.experimental_rerun()
            else:
                st.stop()

        spot = res["data"]["ltp"]
        atm = round(spot / 50) * 50

        col1.metric("Spot", f"₹{spot}")
        col2.metric("ATM", atm)
        col3.metric("Status", "LIVE ✅")

        # -------- FILTER --------
        df_index = df[df["name"] == name]

        # ✅ AUTO EXPIRY
        expiry = sorted(df_index["expiry"].unique())[0]

        df_exp = df_index[df_index["expiry"] == expiry].copy()

        # ✅ STRIKE FIX
        df_exp["strike"] = df_exp["strike"].astype(float) / 100

        # ✅ NEAREST STRIKE
        nearest = df_exp.iloc[(df_exp["strike"] - atm).abs().argsort()[:1]]
        atm = int(nearest["strike"].values[0])

        # CE / PE
        ce = df_exp[(df_exp["strike"] == atm) & df_exp["symbol"].str.endswith("CE")]
        pe = df_exp[(df_exp["strike"] == atm) & df_exp["symbol"].str.endswith("PE")]

        if ce.empty or pe.empty:
            st.error("Option not found")

            if st.sidebar.checkbox("Debug"):
                st.write(df_exp.head(20))

            st.stop()

        ce = ce.iloc[0]
        pe = pe.iloc[0]

        # -------- LTP --------
        ce_data = obj.ltpData("NFO", ce["symbol"], ce["token"])
        pe_data = obj.ltpData("NFO", pe["symbol"], pe["token"])

        ce_ltp = ce_data["data"]["ltp"] if ce_data.get("status") else 0
        pe_ltp = pe_data["data"]["ltp"] if pe_data.get("status") else 0

        ce_oi = ce_data["data"].get("openInterest", 0)
        pe_oi = pe_data["data"].get("openInterest", 0)

        c1, c2 = st.columns(2)
        c1.metric("CALL CE", f"₹{ce_ltp}")
        c2.metric("PUT PE", f"₹{pe_ltp}")

        # -------- ANALYSIS --------
        total = ce_oi + pe_oi + 1
        pcr = round(pe_oi / total, 2)
        strength = int(pe_oi / total * 100)

        if pcr > 1:
            signal = "📈 BUY CALL"
        elif pcr < 0.7:
            signal = "📉 BUY PUT"
        else:
            signal = "⚖️ WAIT"

        support = atm if pe_oi > ce_oi else atm - 50
        resistance = atm if ce_oi > pe_oi else atm + 50

        st.markdown("### 📊 Analysis")
        st.write(f"PCR: {pcr}")
        st.write(f"Strength: {strength}%")
        st.write(f"Support: {support}")
        st.write(f"Resistance: {resistance}")

        st.markdown(f"## 🔥 {signal}")

    except Exception as e:
        st.error(e)

    time.sleep(1)
    st.experimental_rerun()

else:
    col1.metric("Spot", "0")
    col2.metric("ATM", "0")
    col3.metric("Status", "OFFLINE ❌")
