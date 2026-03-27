import streamlit as st
from SmartApi import SmartConnect
import pyotp
import time

# ==========================================
# CONFIGURATION
# ==========================================
FIXED_CLIENT_ID = "P51646259"

st.set_page_config(page_title="GRK WARRIOR PRO", layout="wide")

# ==========================================
# SESSION STATE INIT
# ==========================================
if 'connected' not in st.session_state:
    st.session_state.connected = False

if 'obj' not in st.session_state:
    st.session_state.obj = None

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.title("🚀 GRK WARRIOR V3")

idx = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])

st.sidebar.markdown("---")
st.sidebar.subheader("🔑 Secure Login")

api_key_input = st.sidebar.text_input("1. SmartAPI Key", value="MT72qa1q")
mpin = st.sidebar.text_input("2. Angel 4-Digit MPIN", type="password", max_chars=4)
totp_secret = st.sidebar.text_input("3. TOTP Secret Key", type="password")

# ==========================================
# CONNECT BUTTON
# ==========================================
if st.sidebar.button("Connect Bot"):
    try:
        otp = pyotp.TOTP(totp_secret).now()

        obj = SmartConnect(api_key=api_key_input.strip())
        data = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)

        if data['status']:
            st.session_state.obj = obj
            st.session_state.connected = True
            st.sidebar.success("✅ Live Connection Ready!")
        else:
            st.sidebar.error(f"❌ Login Failed: {data['message']}")

    except Exception as e:
        st.sidebar.error(f"❌ Error: {e}")

# ==========================================
# MAIN DASHBOARD
# ==========================================
st.title("🚀 MKPV ULTRA SNIPER V3 | LIVE")
st.divider()

col1, col2, col3 = st.columns(3)

# ==========================================
# LIVE DATA SECTION
# ==========================================
if st.session_state.connected:

    try:
        # SYMBOL SELECT
        t_sym = "Nifty 50" if idx == "NIFTY" else "Nifty Bank"
        t_tok = "26000" if idx == "NIFTY" else "26009"

        # ✅ LTP FETCH (Correct Way)
        ltp_data = st.session_state.obj.ltpData(
            exchange="NSE",
            tradingsymbol=t_sym,
            symboltoken=t_tok
        )

        if ltp_data['status']:
            ltp = ltp_data['data']['ltp']

            col1.metric(f"LTP {idx}", f"₹{ltp}", delta="LIVE")
            col2.metric("Pipeline Status", "Connected ✅")
            col3.metric(f"OI {idx}", "Updating...")

        else:
            # Session expired → reset
            st.session_state.connected = False
            st.warning("⚠️ Session expired. Please reconnect.")
            st.rerun()

    except Exception as e:
        st.error(f"❌ Data Fetch Error: {e}")

    # 🔁 Auto refresh
    time.sleep(1)
    st.rerun()

# ==========================================
# OFFLINE STATE
# ==========================================
else:
    col1.metric(f"LTP {idx}", "₹0")
    col2.metric("Pipeline Status", "Offline ❌")
    col3.metric(f"OI {idx}", "0")
