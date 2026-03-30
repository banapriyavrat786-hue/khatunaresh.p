import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time
from datetime import datetime

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Sniper V15", layout="wide")
st.title("🚀 Option Chain Sniper Bot")
st.sidebar.title("Controls")

# -- SESSION STATE --
if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None
if 'token_df' not in st.session_state: st.session_state.token_df = None
if 'mpin' not in st.session_state: st.session_state.mpin = ""

# -- HELPER FUNCTIONS --
def get_internet_time():
    try:
        r = requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5)
        return r.json()['unixtime']
    except: return int(time.time())

@st.cache_data(ttl=3600, show_spinner="Loading Master File (50MB)...")
def load_tokens():
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    try:
        res = requests.get(url, timeout=15)
        df = pd.DataFrame(res.json())
        # Only keep NFO to make search lightning fast
        df = df[df['exch_seg'] == 'NFO']
        return df
    except: return None

# -- SIDEBAR --
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
# 💡 Default set to Angel's exact string
expiry_str = st.sidebar.text_input("Expiry String (e.g. 07APR26)", "07APR26").upper()
mpin = st.sidebar.text_input("MPIN", type="password", max_chars=4)

if st.sidebar.button("🔑 Connect"):
    if len(mpin) != 4: st.sidebar.error("Enter a 4-digit MPIN")
    else:
        st.session_state.mpin = mpin
        otp = pyotp.TOTP(TOTP_SECRET.strip().replace(" ", "")).at(get_internet_time())
        smart_obj = SmartConnect(api_key=API_KEY)
        
        try:
            login = smart_obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
            if login and login.get('status'):
                st.session_state.connected = True
                st.session_state.obj = smart_obj
                st.sidebar.success("✅ Connected")
                
                df = load_tokens()
                if df is not None:
                    st.session_state.token_df = df
                    st.sidebar.success("✅ Tokens mapped!")
                else: st.sidebar.error("Token load failed")
            else:
                st.sidebar.error(f"Login failed: {login.get('message')}")
        except Exception as e:
            st.sidebar.error(f"Login Error: {e}")

# -- MAIN AREA --
if st.session_state.connected:
    obj = st.session_state.obj
    df = st.session_state.token_df

    try:
        t_name = "Nifty 50" if index=="NIFTY" else "Nifty Bank"
        t_tok = "26000" if index=="NIFTY" else "26009"
        step = 50 if index=="NIFTY" else 100
        
        res = obj.ltpData("NSE", t_name, t_tok)
        if res.get('status'):
            spot = float(res['data']['ltp'])
            atm = int(round(spot / step) * step)

            c1, c2, c3 = st.columns(3)
            c1.metric("Spot", f"₹{spot}")
            c2.metric("ATM Strike", atm)
            c3.metric("Status", "LIVE ✅")
            
            st.markdown("### 📊 Live ATM Option Data")

            # 💡 THE ULTIMATE SYMBOL MATCHER
            # Creates EXACT string: NIFTY07APR2622450CE
            search_prefix = f"{index}{expiry_str}{atm}"
            ce_sym = f"{search_prefix}CE"
            pe_sym = f"{search_prefix}PE"

            ce_match = df[df['symbol'] == ce_sym]
            pe_match = df[df['symbol'] == pe_sym]

            if ce_match.empty or pe_match.empty:
                st.error(f"🚨 Target Missing: {search_prefix}")
                st.info("Check Expiry format in Sidebar. Must exactly match Angel's naming.")
            else:
                ce_row = ce_match.iloc[0]
                pe_row = pe_match.iloc[0]

                ce_res = obj.ltpData("NFO", ce_row['symbol'], ce_row['token'])
                pe_res = obj.ltpData("NFO", pe_row['symbol'], pe_row['token'])

                ce_ltp = ce_res['data']['ltp'] if ce_res.get('status') else "0.0"
                pe_ltp = pe_res['data']['ltp'] if pe_res.get('status') else "0.0"
                
                colA, colB = st.columns(2)
                colA.metric(f"🟢 Call (CE) @ {atm}", f"₹{ce_ltp}")
                colB.metric(f"🔴 Put (PE) @ {atm}", f"₹{pe_ltp}")
                
                st.success("🎯 Target Locked! Fetching Open Interest next...")
                
        else:
            st.error("Session Expired. Please Reconnect.")
            
    except Exception as e:
        st.error(f"Runtime Error: {e}")
        
    time.sleep(1.5)
    st.rerun()
else:
    st.info("Enter MPIN and Connect to start the Sniper.")
