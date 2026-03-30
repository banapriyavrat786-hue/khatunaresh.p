import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time
from datetime import datetime

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Sniper Pro", layout="wide")
st.title("🚀 Option Chain Sniper Bot")
st.sidebar.title("Controls")

# -- SESSION STATE INIT --
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
        if res.status_code == 200:
            df = pd.DataFrame(res.json())
            # ONLY keep NFO to save memory & speed up
            df = df[df['exch_seg'] == 'NFO']
            # Convert Expiry string to Datetime Object for easy comparison
            df['expiry'] = pd.to_datetime(df['expiry'], errors='coerce')
            # Convert strike price to float
            df['strike'] = pd.to_numeric(df['strike'], errors='coerce')
            return df
        return None
    except Exception as e:
        st.error(f"Failed to load token master: {e}")
        return None

# -- SIDEBAR INPUTS --
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])

# 💡 FIX 1: Expiry Input Format Change (Match the JSON format directly)
# Suggest standard format like "02APR26" and let code handle conversion
expiry_str = st.sidebar.text_input("Expiry (e.g. 02APR26 or 09MAY26)", "02APR26").upper()
mpin = st.sidebar.text_input("MPIN", type="password", max_chars=4)

if st.sidebar.button("🔑 Connect"):
    if len(mpin) != 4: st.sidebar.error("Enter a 4-digit MPIN")
    else:
        st.session_state.mpin = mpin
        otp = pyotp.TOTP(TOTP_SECRET.strip().replace(" ", "")).at(get_internet_time())
        smart_obj = SmartConnect(api_key=API_KEY.strip())
        
        try:
            login = smart_obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
            if login and login.get('status'):
                st.sidebar.success("✅ Connected")
                st.session_state.connected = True
                st.session_state.obj = smart_obj
                
                df = load_tokens()
                if df is not None:
                    st.session_state.token_df = df
                    st.sidebar.success("✅ Tokens mapped!")
                else: st.sidebar.error("Token load failed")
            else:
                msg = login.get('message') if login else "No response"
                st.sidebar.error(f"Login failed: {msg}")
        except Exception as e:
            st.sidebar.error(f"Login Error: {e}")

# -- MAIN AREA --
if st.session_state.connected:
    obj = st.session_state.obj
    df = st.session_state.token_df

    try:
        # 1. Spot Price Calculation
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

            # 💡 FIX 2: String-Based Symbol Matching (Bulletproof)
            # Instead of matching date and strike math, we build the exact Symbol String
            # Angel Symbol Format: NIFTY02APR2622450CE
            search_prefix = f"{index}{expiry_str}{atm}"
            ce_sym = f"{search_prefix}CE"
            pe_sym = f"{search_prefix}PE"

            # Search in the token dataframe
            ce_match = df[df['symbol'] == ce_sym]
            pe_match = df[df['symbol'] == pe_sym]

            if ce_match.empty or pe_match.empty:
                st.error(f"🚨 Tokens not found for: {ce_sym} or {pe_sym}")
                st.info("Check if you entered the exact Expiry String (e.g. '04APR24' instead of '04APR2024').")
                
                # Debug Mode
                if st.sidebar.checkbox("🔍 Debug: Show Available Symbols"):
                    # Show similar symbols to help user find correct format
                    similar = df[df['name'] == index]
                    # Filter by strike to limit results
                    similar = similar[similar['strike'] == (atm * 100)] 
                    st.write(similar[['symbol', 'expiry', 'strike']].head(10))
            else:
                ce_row = ce_match.iloc[0]
                pe_row = pe_match.iloc[0]

                # Fetch Real-Time LTP for Options
                ce_res = obj.ltpData("NFO", ce_row['symbol'], ce_row['token'])
                pe_res = obj.ltpData("NFO", pe_row['symbol'], pe_row['token'])

                ce_ltp = ce_res['data']['ltp'] if ce_res.get('status') else 0.0
                pe_ltp = pe_res['data']['ltp'] if pe_res.get('status') else 0.0
                
                colA, colB = st.columns(2)
                colA.metric(f"🟢 Call (CE) @ {atm}", f"₹{ce_ltp}")
                colB.metric(f"🔴 Put (PE) @ {atm}", f"₹{pe_ltp}")

                # --- ADVANCED ANALYSIS PLACEHOLDER ---
                # To calculate PCR, we need Open Interest (OI) from getQuote API
                st.markdown("---")
                st.subheader("⚙️ Trading Strategy Mode")
                st.warning("Next Step: Fetch Open Interest to calculate Put-Call Ratio (PCR).")

        else:
            st.error("Failed to fetch Spot Price. Checking connection...")
            
    except Exception as e:
        st.error(f"Runtime Error: {e}")
        
    time.sleep(1.5)
    st.rerun()

else:
    c1, c2, c3 = st.columns(3)
    c1.metric("Spot", "₹0")
    c2.metric("ATM Strike", "0")
    c3.metric("Status", "OFFLINE ❌")
