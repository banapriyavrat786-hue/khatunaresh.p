import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Sniper V18", layout="wide")
st.title("🎯 MKPV Ultra Sniper | Point Catcher")

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
st.sidebar.subheader("🎯 Target & StopLoss (In Points)")
# 💡 FIX: Percentage hata kar Points kar diya
tgt_points = st.sidebar.number_input("Target (Points)", value=10, step=1)
sl_points = st.sidebar.number_input("StopLoss (Points)", value=5, step=1)

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
        
        search_prefix = f"{index}{expiry_str}{atm}"
        ce_match = df[df['symbol'] == f"{search_prefix}CE"]
        pe_match = df[df['symbol'] == f"{search_prefix}PE"]

        if not ce_match.empty and not pe_match.empty:
            ce_row, pe_row = ce_match.iloc[0], pe_match.iloc[0]
            
            ce_tok = str(ce_row['token']).split('.')[0]
            pe_tok = str(pe_row['token']).split('.')[0]
            
            ce_res = obj.ltpData("NFO", ce_row['symbol'], ce_tok)
            pe_res = obj.ltpData("NFO", pe_row['symbol'], pe_tok)

            ce_ltp = float(ce_res['data']['ltp']) if ce_res.get('status') else 0.0
            pe_ltp = float(pe_res['data']['ltp']) if pe_res.get('status') else 0.0

            # 📋 1. SYSTEM CHECKLIST
            st.divider()
            chk1, chk2, chk3 = st.columns(3)
            chk1.success("✅ Spot Data Active")
            chk2.success(f"✅ Exact Tokens Found")
            if ce_ltp > 0 and pe_ltp > 0: chk3.success("✅ Premium Feeds Active")
            else: chk3.error("🚨 Market Closed / Fetching Error")

            # 🛡️ 2. SAFETY PERCENTAGE (MOMENTUM)
            st.subheader("🛡️ Safety & Momentum Check")
            total_premium = ce_ltp + pe_ltp
            if total_premium > 0:
                ce_safety = round((ce_ltp / total_premium) * 100, 1)
                pe_safety = round((pe_ltp / total_premium) * 100, 1)
            else:
                ce_safety, pe_safety = 0, 0

            # Progress bar style display
            saf1, saf2 = st.columns(2)
            saf1.metric("🟢 CALL Safety (Momentum Strength)", f"{ce_safety}%")
            saf2.metric("🔴 PUT Safety (Momentum Strength)", f"{pe_safety}%")
            
            if ce_safety > 55: st.info("📈 **Trend:** Call side is currently safer & dominating.")
            elif pe_safety > 55: st.info("📉 **Trend:** Put side is currently safer & dominating.")
            else: st.warning("⚖️ **Trend:** Market is completely Sideways. Risky to trade.")

            # FUNCTION TO PLACE ORDER
            def place_buy_order(symbol, token):
                try:
                    orderparams = {
                        "variety": "NORMAL", "tradingsymbol": symbol, "symboltoken": str(token),
                        "transactiontype": "BUY", "exchange": "NFO", "ordertype": "MARKET",
                        "producttype": "INTRADAY", "duration": "DAY", "quantity": str(total_qty)
                    }
                    orderId = obj.placeOrder(orderparams)
                    st.success(f"✅ Order Placed! ID: {orderId}")
                except Exception as e: st.error(f"❌ Order Failed: {e}")

            # 🎯 3. TRADE PLANNER (POINTS BASED)
            st.markdown("---")
            st.subheader("🎯 Execution Panel (Points Captured)")
            
            colA, colB = st.columns(2)
            with colA:
                st.markdown(f"### 🟢 CALL ({ce_row['symbol']})")
                st.metric("Entry Premium", f"₹{ce_ltp}")
                # Points Math
                st.write(f"**🎯 Target (+{tgt_points} Pts):** ₹{round(ce_ltp + tgt_points, 2)}")
                st.write(f"**🛡️ Stoploss (-{sl_points} Pts):** ₹{round(ce_ltp - sl_points, 2)}")
                if ce_ltp > 0 and st.button("🚀 BUY CALL AT MARKET"): place_buy_order(ce_row['symbol'], ce_tok)
            
            with colB:
                st.markdown(f"### 🔴 PUT ({pe_row['symbol']})")
                st.metric("Entry Premium", f"₹{pe_ltp}")
                # Points Math
                st.write(f"**🎯 Target (+{tgt_points} Pts):** ₹{round(pe_ltp + tgt_points, 2)}")
                st.write(f"**🛡️ Stoploss (-{sl_points} Pts):** ₹{round(pe_ltp - sl_points, 2)}")
                if pe_ltp > 0 and st.button("🚀 BUY PUT AT MARKET"): place_buy_order(pe_row['symbol'], pe_tok)

        else: st.error(f"🚨 Tokens missing for {search_prefix}")

    time.sleep(2)
    st.rerun()
else:
    st.info("Enter MPIN and Connect to start the Sniper.")
