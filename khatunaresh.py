import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Auto-Sniper V22", layout="wide")
st.title("🤖 MKPV Auto-Sniper | OI & Volume Edition")

# -- SESSION STATE --
if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None
if 'token_df' not in st.session_state: st.session_state.token_df = None
if 'price_history' not in st.session_state: st.session_state.price_history = [] 
if 'active_trade' not in st.session_state: st.session_state.active_trade = None
if 'trade_history' not in st.session_state: st.session_state.trade_history = []

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
st.sidebar.title("⚙️ Robot Controls")
auto_trade = st.sidebar.checkbox("🤖 Enable Auto-Trade Mode", value=False)
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry_str = st.sidebar.text_input("Expiry (e.g. 07APR26)", "07APR26").upper()
qty_multiplier = st.sidebar.number_input("Lots to Buy", min_value=1, value=1)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Auto Target & SL (Points)")
tgt_points = st.sidebar.number_input("Target (+ Points)", value=40, step=5)
sl_points = st.sidebar.number_input("StopLoss (- Points)", value=20, step=5)

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

        st.session_state.price_history.append(spot)
        if len(st.session_state.price_history) > 15: st.session_state.price_history.pop(0)
        sma = round(sum(st.session_state.price_history) / len(st.session_state.price_history), 2)

        # 🔍 OI & VOLUME BASED SUPPORT / RESISTANCE
        # Scan 5 strikes near ATM
        strikes_to_scan = [atm - (step*2), atm - step, atm, atm + step, atm + (step*2)]
        tokens_to_fetch = []
        token_to_strike = {}

        for s in strikes_to_scan:
            sym_prefix = f"{index}{expiry_str}{s}"
            ce_df = df[df['symbol'] == f"{sym_prefix}CE"]
            pe_df = df[df['symbol'] == f"{sym_prefix}PE"]
            if not ce_df.empty and not pe_df.empty:
                c_tok = str(ce_df.iloc[0]['token']).split('.')[0]
                p_tok = str(pe_df.iloc[0]['token']).split('.')[0]
                tokens_to_fetch.extend([c_tok, p_tok])
                token_to_strike[c_tok] = {"type": "CE", "strike": s}
                token_to_strike[p_tok] = {"type": "PE", "strike": s}

        # Angel One API for Market Data (OI & Vol)
        max_ce_oi = 0; resistance_strike = atm
        max_pe_oi = 0; support_strike = atm

        try:
            # Using getMarketData to get Open Interest
            market_data = obj.getMarketData("FULL", {"NFO": tokens_to_fetch})
            if market_data and market_data.get('status'):
                for item in market_data['data']['fetched']:
                    tok = item['symbolToken']
                    oi = item['opnInterest']
                    t_data = token_to_strike.get(tok)
                    
                    if t_data['type'] == 'CE' and oi > max_ce_oi:
                        max_ce_oi = oi
                        resistance_strike = t_data['strike']
                    elif t_data['type'] == 'PE' and oi > max_pe_oi:
                        max_pe_oi = oi
                        support_strike = t_data['strike']
        except:
            pass # Fallback if MarketData API takes time

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Spot Price", f"₹{spot}")
        c2.metric("Live SMA", f"₹{sma}")
        c3.metric("Resistance (Max CE OI)", f"Strike: {resistance_strike}")
        c4.metric("Support (Max PE OI)", f"Strike: {support_strike}")
        
        # TARGET TOKENS
        search_prefix = f"{index}{expiry_str}{atm}"
        ce_match = df[df['symbol'] == f"{search_prefix}CE"]
        pe_match = df[df['symbol'] == f"{search_prefix}PE"]

        if not ce_match.empty and not pe_match.empty:
            ce_row, pe_row = ce_match.iloc[0], pe_match.iloc[0]
            ce_tok, pe_tok = str(ce_row['token']).split('.')[0], str(pe_row['token']).split('.')[0]
            
            ce_res = obj.ltpData("NFO", ce_row['symbol'], ce_tok)
            pe_res = obj.ltpData("NFO", pe_row['symbol'], pe_tok)
            ce_ltp = float(ce_res['data']['ltp']) if ce_res.get('status') else 0.0
            pe_ltp = float(pe_res['data']['ltp']) if pe_res.get('status') else 0.0

            st.divider()

            # 🧠 KHATUSHYAM LOGIC (Safety Calculation)
            # OI Check: If Price > Support, CE is safer. If Price < Resistance, PE is safer.
            c_score = sum([spot > sma, ce_ltp > pe_ltp, spot > support_strike, True]) 
            p_score = sum([spot < sma, pe_ltp > ce_ltp, spot < resistance_strike, True])
            ce_safety = round((c_score / 4) * 100, 1)
            pe_safety = round((p_score / 4) * 100, 1)

            # ⚙️ AUTO TRADE ENGINE
            def place_order(symbol, token, side):
                try:
                    orderparams = {
                        "variety": "NORMAL", "tradingsymbol": symbol, "symboltoken": str(token),
                        "transactiontype": "BUY", "exchange": "NFO", "ordertype": "MARKET",
                        "producttype": "INTRADAY", "duration": "DAY", "quantity": str(total_qty)
                    }
                    orderId = obj.placeOrder(orderparams)
                    return orderId
                except: return "SIMULATED_ORDER_ID" # Change for real trading

            st.subheader("⚡ Active Trade Monitor")
            
            # --- MANAGE ACTIVE TRADE ---
            if st.session_state.active_trade is not None:
                trade = st.session_state.active_trade
                curr_ltp = ce_ltp if trade['type'] == 'CE' else pe_ltp
                pnl = round(curr_ltp - trade['entry'], 2)
                
                st.info(f"🚀 **RUNNING TRADE:** {trade['symbol']} | Entry: ₹{trade['entry']} | **Live P&L: {pnl} Pts**")
                
                # Check Auto-Exit Conditions
                if curr_ltp >= trade['target']:
                    st.success(f"🎯 TARGET HIT! Exited at {curr_ltp}")
                    st.session_state.trade_history.append({"Symbol": trade['symbol'], "Safety": trade['safety'], "Entry": trade['entry'], "Exit": curr_ltp, "P&L": pnl, "Result": "✅ Target"})
                    st.session_state.active_trade = None
                
                elif curr_ltp <= trade['sl']:
                    st.error(f"🛑 STOPLOSS HIT! Exited at {curr_ltp}")
                    st.session_state.trade_history.append({"Symbol": trade['symbol'], "Safety": trade['safety'], "Entry": trade['entry'], "Exit": curr_ltp, "P&L": pnl, "Result": "❌ Stoploss"})
                    st.session_state.active_trade = None

                if st.button("🚨 MANUAL EXIT NOW"):
                    st.session_state.trade_history.append({"Symbol": trade['symbol'], "Safety": trade['safety'], "Entry": trade['entry'], "Exit": curr_ltp, "P&L": pnl, "Result": "⚠️ Manual"})
                    st.session_state.active_trade = None

            # --- FIND NEW TRADE ---
            else:
                st.write("⏳ Waiting for setup... No active trades.")
                colA, colB = st.columns(2)
                colA.metric(f"Call Safety ({ce_row['symbol']})", f"{ce_safety}%")
                colB.metric(f"Put Safety ({pe_row['symbol']})", f"{pe_safety}%")

                if auto_trade:
                    if ce_safety >= 75.0 and spot > sma and ce_ltp > 0:
                        order_id = place_order(ce_row['symbol'], ce_tok, "BUY")
                        st.session_state.active_trade = {'type': 'CE', 'symbol': ce_row['symbol'], 'entry': ce_ltp, 'target': ce_ltp + tgt_points, 'sl': ce_ltp - sl_points, 'safety': f"{ce_safety}%"}
                        st.success(f"🤖 Auto-Trade Executed: BOUGHT CALL! (ID: {order_id})")
                    
                    elif pe_safety >= 75.0 and spot < sma and pe_ltp > 0:
                        order_id = place_order(pe_row['symbol'], pe_tok, "BUY")
                        st.session_state.active_trade = {'type': 'PE', 'symbol': pe_row['symbol'], 'entry': pe_ltp, 'target': pe_ltp + tgt_points, 'sl': pe_ltp - sl_points, 'safety': f"{pe_safety}%"}
                        st.success(f"🤖 Auto-Trade Executed: BOUGHT PUT! (ID: {order_id})")
                else:
                    st.warning("🤖 Auto-Trade is OFF. Enable from sidebar to take automatic entries.")

            # 📚 TRADE HISTORY TABLE
            st.divider()
            st.subheader("📚 Today's Trade History")
            if len(st.session_state.trade_history) > 0:
                history_df = pd.DataFrame(st.session_state.trade_history)
                st.dataframe(history_df, use_container_width=True)
                
                total_pnl = round(history_df['P&L'].sum(), 2)
                if total_pnl > 0: st.success(f"### 💸 Total Profit: +{total_pnl} Points")
                else: st.error(f"### 📉 Total Loss: {total_pnl} Points")
            else:
                st.write("No trades taken yet.")

        else: st.error(f"🚨 Tokens missing for {search_prefix}")

    time.sleep(2)
    st.rerun()
else:
    st.info("Enter MPIN and Connect to start the Auto-Sniper.")
