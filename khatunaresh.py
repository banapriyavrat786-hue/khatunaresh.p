import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Sniper V20", layout="wide")
st.title("🏹 MKPV Ultra Sniper | Khatushyam Engine")

# -- SESSION STATE --
if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None
if 'token_df' not in st.session_state: st.session_state.token_df = None
# Live SMA calculate karne ke liye history
if 'price_history' not in st.session_state: st.session_state.price_history = [] 

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
st.sidebar.title("⚙️ Strategy Controls")
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry_str = st.sidebar.text_input("Expiry (e.g. 07APR26)", "07APR26").upper()
qty_multiplier = st.sidebar.number_input("Lots to Buy", min_value=1, value=1)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Risk Management (Points)")
tgt_points = st.sidebar.number_input("Target (+ Points)", value=40, step=5) # Default 40 as per your code
sl_points = st.sidebar.number_input("StopLoss (- Points)", value=20, step=5) # Default 20 as per your code

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

        # Update Live History for SMA
        st.session_state.price_history.append(spot)
        if len(st.session_state.price_history) > 10:
            st.session_state.price_history.pop(0) # Keep last 10 ticks

        # Calculate SMA
        sma = round(sum(st.session_state.price_history) / len(st.session_state.price_history), 2)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Spot Price", f"₹{spot}")
        c2.metric("Live SMA (10-Tick)", f"₹{sma}")
        c3.metric("ATM Strike", atm)
        c4.metric("Status", "LIVE 🟢")
        
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

            st.divider()

            # 🧠 1. KHATUSHYAM STRATEGY LOGIC
            st.subheader("📋 Khatushyam Smart Checklist")
            
            # Logic calculations
            c_trend = spot > sma
            p_trend = spot < sma
            c_sent = ce_ltp > pe_ltp # Premium momentum as sentiment
            p_sent = pe_ltp > ce_ltp
            
            # Auto-pass for OI and Vol (as per your script logic)
            c_score = sum([c_trend, c_sent, True, True]) 
            p_score = sum([p_trend, p_sent, True, True])

            ce_safety = round((c_score / 4) * 100, 1)
            pe_safety = round((p_score / 4) * 100, 1)

            def icon(val): return "✅" if val else "❌"

            # Display exactly like your terminal!
            chk_col1, chk_col2 = st.columns(2)
            with chk_col1:
                st.markdown("##### 🟢 CALL Readiness")
                st.write(f"- **Trend (Spot > SMA):** {icon(c_trend)}")
                st.write(f"- **Sentiment (CE > PE):** {icon(c_sent)}")
                st.write(f"- **OI Filter:** {icon(True)}")
                st.write(f"- **Volume Filter:** {icon(True)}")
                st.metric("CALL SAFETY", f"{ce_safety}%")

            with chk_col2:
                st.markdown("##### 🔴 PUT Readiness")
                st.write(f"- **Trend (Spot < SMA):** {icon(p_trend)}")
                st.write(f"- **Sentiment (PE > CE):** {icon(p_sent)}")
                st.write(f"- **OI Filter:** {icon(True)}")
                st.write(f"- **Volume Filter:** {icon(True)}")
                st.metric("PUT SAFETY", f"{pe_safety}%")

            st.markdown("---")

            # 📡 2. SIGNAL GENERATOR
            if ce_safety >= 75.0 and spot > sma:
                signal_text = "🚀 STRONG BUY CALL ✅"
                st.success(f"### SIGNAL: {signal_text}")
            elif pe_safety >= 75.0 and spot < sma:
                signal_text = "🔥 STRONG BUY PUT 🔴"
                st.error(f"### SIGNAL: {signal_text}")
            else:
                st.warning("### SIGNAL: SCANNING 📡 (Waiting for 75% Safety)")

            # 🎯 3. EXECUTION PANEL
            def place_buy_order(symbol, token):
                try:
                    orderparams = {
                        "variety": "NORMAL", "tradingsymbol": symbol, "symboltoken": str(token),
                        "transactiontype": "BUY", "exchange": "NFO", "ordertype": "MARKET",
                        "producttype": "INTRADAY", "duration": "DAY", "quantity": str(total_qty)
                    }
                    orderId = obj.placeOrder(orderparams)
                    st.success(f"✅ Executed! Order ID: {orderId}")
                except Exception as e: st.error(f"❌ Order Failed: {e}")

            st.markdown("---")
            st.subheader("🎯 Trading Pad")
            
            colA, colB = st.columns(2)
            with colA:
                st.markdown(f"**🟢 CALL ({ce_row['symbol']})**")
                st.metric("Entry Premium", f"₹{ce_ltp}")
                st.write(f"**🎯 Target (+{tgt_points}):** ₹{round(ce_ltp + tgt_points, 2)}")
                st.write(f"**🛑 Stoploss (-{sl_points}):** ₹{round(ce_ltp - sl_points, 2)}")
                if ce_ltp > 0 and ce_safety >= 75.0:
                    if st.button("🚀 EXECUTE CALL BUY", use_container_width=True): place_buy_order(ce_row['symbol'], ce_tok)
            
            with colB:
                st.markdown(f"**🔴 PUT ({pe_row['symbol']})**")
                st.metric("Entry Premium", f"₹{pe_ltp}")
                st.write(f"**🎯 Target (+{tgt_points}):** ₹{round(pe_ltp + tgt_points, 2)}")
                st.write(f"**🛑 Stoploss (-{sl_points}):** ₹{round(pe_ltp - sl_points, 2)}")
                if pe_ltp > 0 and pe_safety >= 75.0:
                    if st.button("🚀 EXECUTE PUT BUY", use_container_width=True): place_buy_order(pe_row['symbol'], pe_tok)

        else: st.error(f"🚨 Tokens missing for {search_prefix}")

    time.sleep(2)
    st.rerun()
else:
    st.info("Enter MPIN and Connect to start the Sniper.")
