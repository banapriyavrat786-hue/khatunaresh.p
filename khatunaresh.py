import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Sniper V17", layout="wide")
st.title("🎯 MKPV Ultra Sniper Bot | Execution Mode")

# -- SESSION STATE --
if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None
if 'token_df' not in st.session_state: st.session_state.token_df = None

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
        return df[df['exch_seg'] == 'NFO']
    except: return None

# -- SIDEBAR & LOGIN --
st.sidebar.title("⚙️ Controls")
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry_str = st.sidebar.text_input("Expiry (e.g. 07APR26)", "07APR26").upper()
qty_multiplier = st.sidebar.number_input("Lots to Buy", min_value=1, value=1)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Risk Management")
tgt_pct = st.sidebar.number_input("Target %", value=20, step=5)
sl_pct = st.sidebar.number_input("StopLoss %", value=10, step=5)

mpin = st.sidebar.text_input("MPIN", type="password", max_chars=4)

if st.sidebar.button("🔑 Connect"):
    if len(mpin) != 4: st.sidebar.error("Enter a 4-digit MPIN")
    else:
        otp = pyotp.TOTP(TOTP_SECRET.strip().replace(" ", "")).at(get_internet_time())
        smart_obj = SmartConnect(api_key=API_KEY)
        try:
            login = smart_obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
            if login and login.get('status'):
                st.session_state.connected = True
                st.session_state.obj = smart_obj
                df = load_tokens()
                if df is not None:
                    st.session_state.token_df = df
                    st.sidebar.success("✅ System Online!")
            else: st.sidebar.error("Login Failed")
        except Exception as e: st.sidebar.error(f"Error: {e}")

# -- MAIN DASHBOARD --
if st.session_state.connected:
    obj = st.session_state.obj
    df = st.session_state.token_df
    lot_size = 50 if index == "NIFTY" else 15
    total_qty = lot_size * int(qty_multiplier)

    t_name = "Nifty 50" if index=="NIFTY" else "Nifty Bank"
    t_tok = "26000" if index=="NIFTY" else "26009"
    step = 50 if index=="NIFTY" else 100
    
    res = obj.ltpData("NSE", t_name, t_tok)
    if res.get('status'):
        spot = float(res['data']['ltp'])
        atm = int(round(spot / step) * step)

        c1, c2, c3 = st.columns(3)
        c1.metric("Spot Price", f"₹{spot}")
        c2.metric("ATM Strike", atm)
        c3.metric("Trade Qty", f"{total_qty} units")
        
        # 1. TOKEN SEARCH
        search_prefix = f"{index}{expiry_str}{atm}"
        ce_match = df[df['symbol'] == f"{search_prefix}CE"]
        pe_match = df[df['symbol'] == f"{search_prefix}PE"]

        if not ce_match.empty and not pe_match.empty:
            ce_row, pe_row = ce_match.iloc[0], pe_match.iloc[0]
            
            # 💡 LTP FIX: Ensuring token is pure string without decimals
            ce_tok = str(ce_row['token']).split('.')[0]
            pe_tok = str(pe_row['token']).split('.')[0]
            
            ce_res = obj.ltpData("NFO", ce_row['symbol'], ce_tok)
            pe_res = obj.ltpData("NFO", pe_row['symbol'], pe_tok)

            ce_ltp = float(ce_res['data']['ltp']) if ce_res.get('status') else 0.0
            pe_ltp = float(pe_res['data']['ltp']) if pe_res.get('status') else 0.0

            # 📋 2. SYSTEM CHECKLIST
            st.divider()
            chk1, chk2, chk3 = st.columns(3)
            chk1.success("✅ Spot Data Active")
            chk2.success(f"✅ Exact Tokens Found")
            if ce_ltp > 0 and pe_ltp > 0:
                chk3.success("✅ Premium Feeds Active")
            else:
                chk3.error("🚨 Market Closed / Fetching Error")

            # 🎯 3. TRADE PLANNER
            st.subheader("🎯 Auto Trade Planner & Execution")
            
            if ce_ltp > pe_ltp * 1.2: safe_signal = "🟢 CALL looks stronger"
            elif pe_ltp > ce_ltp * 1.2: safe_signal = "🔴 PUT looks stronger"
            else: safe_signal = "⚖️ Market is Sideways / Indecisive"
            st.info(f"**Market Bias:** {safe_signal}")

            # FUNCTION TO PLACE ORDER
            def place_buy_order(symbol, token):
                try:
                    orderparams = {
                        "variety": "NORMAL",
                        "tradingsymbol": symbol,
                        "symboltoken": str(token),
                        "transactiontype": "BUY",
                        "exchange": "NFO",
                        "ordertype": "MARKET",
                        "producttype": "INTRADAY",
                        "duration": "DAY",
                        "quantity": str(total_qty)
                    }
                    orderId = obj.placeOrder(orderparams)
                    st.success(f"✅ Order Placed! ID: {orderId}")
                except Exception as e:
                    st.error(f"❌ Order Failed: {e}")

            # Calculation & Action Tables
            colA, colB = st.columns(2)
            
            with colA:
                st.markdown(f"### 🟢 CALL ({ce_row['symbol']})")
                st.metric("Entry Price (LTP)", f"₹{ce_ltp}")
                st.write(f"**🎯 Target (+{tgt_pct}%):** ₹{round(ce_ltp * (1 + tgt_pct/100), 2)}")
                st.write(f"**🛡️ Stoploss (-{sl_pct}%):** ₹{round(ce_ltp * (1 - sl_pct/100), 2)}")
                if ce_ltp > 0:
                    if st.button("🚀 BUY CALL AT MARKET"):
                        place_buy_order(ce_row['symbol'], ce_tok)
            
            with colB:
                st.markdown(f"### 🔴 PUT ({pe_row['symbol']})")
                st.metric("Entry Price (LTP)", f"₹{pe_ltp}")
                st.write(f"**🎯 Target (+{tgt_pct}%):** ₹{round(pe_ltp * (1 + tgt_pct/100), 2)}")
                st.write(f"**🛡️ Stoploss (-{sl_pct}%):** ₹{round(pe_ltp * (1 - sl_pct/100), 2)}")
                if pe_ltp > 0:
                    if st.button("🚀 BUY PUT AT MARKET"):
                        place_buy_order(pe_row['symbol'], pe_tok)

        else:
            st.error(f"🚨 Tokens missing for {search_prefix}")

    time.sleep(2)
    st.rerun()
else:
    st.info("Enter MPIN and Connect to start the Sniper.")
    
