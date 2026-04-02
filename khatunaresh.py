import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time
from datetime import datetime

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Auto-Sniper V37", layout="wide")
st.title("🏹 MKPV Ultra Sniper | Safe Data Mode")

# -- SESSION STATE --
if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None
if 'token_df' not in st.session_state: st.session_state.token_df = None
if 'active_trade' not in st.session_state: st.session_state.active_trade = None
if 'trade_history' not in st.session_state: st.session_state.trade_history = []
if 'price_history' not in st.session_state: st.session_state.price_history = []

def get_internet_time():
    try:
        return requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5).json()['unixtime']
    except: return int(time.time())

@st.cache_data(ttl=3600, show_spinner="Downloading Angel One Tokens (50MB)...")
def load_tokens():
    try:
        res = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json", timeout=30)
        if res.status_code == 200:
            df = pd.DataFrame(res.json())
            return df[df['exch_seg'] == 'NFO']
        return None
    except: return None

# -- SIDEBAR CONTROLS --
st.sidebar.title("⚙️ Robot Controls")
live_feed = st.sidebar.checkbox("🟢 LIVE FEED (Auto-Refresh)", value=False)
auto_trade = st.sidebar.checkbox("🤖 Enable Auto-Trade Mode", value=False)

st.sidebar.markdown("---")
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry_str = st.sidebar.text_input("Expiry (e.g. 07APR26)", "07APR26").upper()
qty_multiplier = st.sidebar.number_input("Lots", min_value=1, value=1)

st.sidebar.subheader("🎯 Spot Index Targets")
tgt_points = st.sidebar.number_input("Target Points", value=40.0, step=5.0)
sl_points = st.sidebar.number_input("StopLoss Points", value=20.0, step=5.0)
mpin = st.sidebar.text_input("MPIN", type="password", max_chars=4)

if st.sidebar.button("🔑 Connect"):
    st.session_state.active_trade = None 
    st.session_state.token_df = load_tokens() 
    if st.session_state.token_df is not None:
        otp = pyotp.TOTP(TOTP_SECRET.strip().replace(" ", "")).at(get_internet_time())
        smart_obj = SmartConnect(api_key=API_KEY)
        login = smart_obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
        if login.get('status'):
            st.session_state.connected = True
            st.session_state.obj = smart_obj
            st.sidebar.success("✅ System Online! Turn ON Live Feed.")
        else: st.sidebar.error("❌ Login Failed.")
    else: st.sidebar.error("❌ Token file failed.")

# -- MAIN DASHBOARD --
if st.session_state.connected:
    if live_feed:
        obj = st.session_state.obj
        df = st.session_state.token_df
        if df is None or df.empty: st.stop()

        lot_size = 50 if index == "NIFTY" else 15
        total_qty = lot_size * int(qty_multiplier)
        step = 50 if index=="NIFTY" else 100

        t_name = "Nifty 50" if index=="NIFTY" else "Nifty Bank"
        t_tok = "26000" if index=="NIFTY" else "26009"
        
        try:
            res = obj.ltpData("NSE", t_name, t_tok)
            if res and res.get('status'):
                spot = float(res['data']['ltp'])
                st.session_state.price_history.append(spot)
                if len(st.session_state.price_history) > 10: st.session_state.price_history.pop(0)
                sma = round(sum(st.session_state.price_history) / len(st.session_state.price_history), 2)
                atm = int(round(spot / step) * step)
                search_prefix = f"{index}{expiry_str}"

                try:
                    atm_ce_row = df[df['symbol'] == f"{search_prefix}{atm}CE"].iloc[0]
                    atm_pe_row = df[df['symbol'] == f"{search_prefix}{atm}PE"].iloc[0]
                    atm_ce_tok = str(atm_ce_row['token']).split('.')[0]
                    atm_pe_tok = str(atm_pe_row['token']).split('.')[0]
                except:
                    atm_ce_tok, atm_pe_tok = "", ""

                if atm_ce_tok and atm_pe_tok:
                    strikes_to_scan = [atm - step*3, atm - step*2, atm - step, atm, atm + step, atm + step*2, atm + step*3]
                    ce_tokens = []
                    pe_tokens = []
                    strike_map = {}

                    for s in strikes_to_scan:
                        c_df = df[df['symbol'] == f"{search_prefix}{s}CE"]
                        p_df = df[df['symbol'] == f"{search_prefix}{s}PE"]
                        if not c_df.empty and not p_df.empty:
                            c_tok = str(c_df.iloc[0]['token']).split('.')[0]
                            p_tok = str(p_df.iloc[0]['token']).split('.')[0]
                            ce_tokens.append(c_tok)
                            pe_tokens.append(p_tok)
                            strike_map[c_tok] = {'type': 'CE', 'strike': s}
                            strike_map[p_tok] = {'type': 'PE', 'strike': s}

                    max_ce_oi, resistance_strike = 0, atm + (step*3) 
                    max_pe_oi, support_strike = 0, atm - (step*3)
                    ce_ltp, pe_ltp, ce_oi, pe_oi, ce_vol, pe_vol = 0.0, 0.0, 0, 0, 0, 0

                    # 💡 V37 FIX: Batched API Calls to prevent 0 OI Error (API Limit/Timeout Protection)
                    try:
                        # Fetch CE data
                        ce_data = obj.getMarketData("FULL", {"NFO": ce_tokens})
                        if ce_data and ce_data.get('status'):
                            for item in ce_data['data']['fetched']:
                                tok = item['symbolToken']
                                if tok not in strike_map: continue
                                t_strike = strike_map[tok]['strike']
                                
                                if t_strike >= atm and item['opnInterest'] > max_ce_oi:
                                    max_ce_oi = item['opnInterest']
                                    resistance_strike = t_strike

                                if t_strike == atm:
                                    ce_ltp = item.get('lastTradedPrice', 0.0)
                                    ce_oi = item.get('opnInterest', 0)
                                    ce_vol = item.get('volume', 0)
                                    
                        # Small delay to respect Angel One rate limits
                        time.sleep(0.5)
                        
                        # Fetch PE data
                        pe_data = obj.getMarketData("FULL", {"NFO": pe_tokens})
                        if pe_data and pe_data.get('status'):
                            for item in pe_data['data']['fetched']:
                                tok = item['symbolToken']
                                if tok not in strike_map: continue
                                t_strike = strike_map[tok]['strike']

                                if t_strike <= atm and item['opnInterest'] > max_pe_oi:
                                    max_pe_oi = item['opnInterest']
                                    support_strike = t_strike

                                if t_strike == atm:
                                    pe_ltp = item.get('lastTradedPrice', 0.0)
                                    pe_oi = item.get('opnInterest', 0)
                                    pe_vol = item.get('volume', 0)
                                    
                    except Exception as e: 
                        st.error(f"Market Data Fetch Error: {e}")

                    # DIAGNOSTIC PRINT: Agar 0 aa raha hai, toh screen pe saaf dikhega kyon!
                    if ce_oi == 0 or pe_oi == 0:
                        st.warning(f"⚠️ Angel One API returned zero OI for ATM Strike ({atm}). Waiting for next refresh...")

                    market_state = "Sideways / Conflicting ⚖️"
                    if spot > sma and pe_oi > ce_oi: market_state = "Bullish Trending 📈"
                    elif spot < sma and ce_oi > pe_oi: market_state = "Bearish Trending 📉"

                    st.subheader(f"📊 Market Condition: {market_state}")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Live Index (Spot)", f"₹{spot}")
                    c2.metric("Trend (SMA)", f"₹{sma}")
                    c3.metric("True Resistance (CE)", f"Strike: {resistance_strike}")
                    c4.metric("True Support (PE)", f"Strike: {support_strike}")

                    st.divider()

                    # 💡 V37 LOGIC EVALUATION
                    valid_data = (ce_oi > 0 and pe_oi > 0 and ce_vol > 0 and pe_vol > 0)
                    
                    c_price = spot > sma
                    c_mom = ce_ltp > pe_ltp
                    p_price = spot < sma
                    p_mom = pe_ltp > ce_ltp

                    if valid_data:
                        c_oi = (pe_oi > ce_oi)
                        c_vol = (pe_vol > ce_vol)
                        p_oi = (ce_oi > pe_oi)
                        p_vol = (ce_vol > pe_vol)
                    else:
                        c_oi = c_vol = p_oi = p_vol = False

                    ce_score = sum([c_price, c_mom, c_oi, c_vol])
                    pe_score = sum([p_price, p_mom, p_oi, p_vol])
                    ce_safety = (ce_score / 4) * 100
                    pe_safety = (pe_score / 4) * 100

                    # 🚀 1. EVALUATE EXITS
                    if st.session_state.active_trade is not None:
                        trade = st.session_state.active_trade
                        if trade['type'] == 'CE':
                            pnl_spot = round(spot - trade['entry_spot'], 2)
                            is_target, is_sl = spot >= trade['target_spot'], spot <= trade['sl_spot']
                        else:
                            pnl_spot = round(trade['entry_spot'] - spot, 2)
                            is_target, is_sl = spot <= trade['target_spot'], spot >= trade['sl_spot']

                        if is_target or is_sl:
                            res_msg = "✅ Target Hit" if is_target else "❌ StopLoss Hit"
                            st.session_state.trade_history.append({"Time": datetime.now().strftime("%H:%M:%S"), "Symbol": trade['symbol'], "Type": trade['type'], "Entry (Spot)": trade['entry_spot'], "Exit (Spot)": round(spot, 2), "Target Level": trade['target_spot'], "SL Level": trade['sl_spot'], "P&L (Pts)": pnl_spot, "Status": res_msg})
                            st.session_state.active_trade = None
                            st.success(f"⚡ Trade Closed: {res_msg} at {spot}!")
                            time.sleep(1)
                            st.rerun()

                    # 📋 2. SNIPER ENTRY CHECKLIST UI
                    def check_icon(val): return "✅" if val else ("⚠️ Data Pending" if not valid_data else "❌")

                    st.subheader("📋 Strict Sniper Checklist")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"### 🟢 CALL Sniper ({ce_safety}%)")
                        st.write(f"Trend UP (Spot > SMA): {'✅' if c_price else '❌'}")
                        st.write(f"Momentum (CE > PE): {'✅' if c_mom else '❌'}")
                        st.write(f"Support Strong (PE OI > CE OI): {check_icon(c_oi)}")
                        st.write(f"Put Writers Active (PE Vol > CE Vol): {check_icon(c_vol)}")
                    with col_b:
                        st.markdown(f"### 🔴 PUT Sniper ({pe_safety}%)")
                        st.write(f"Trend DOWN (Spot < SMA): {'✅' if p_price else '❌'}")
                        st.write(f"Momentum (PE > CE): {'✅' if p_mom else '❌'}")
                        st.write(f"Resistance Strong (CE OI > PE OI): {check_icon(p_oi)}")
                        st.write(f"Call Writers Active (CE Vol > PE Vol): {check_icon(p_vol)}")

                    st.divider()

                    # 🚀 3. TRADE EXECUTION / MONITORING
                    if st.session_state.active_trade is None:
                        if auto_trade:
                            st.info("🤖 Auto-Trade ENABLED: Waiting for 75% setup (Data must be valid)...")
                            target_sym = f"{search_prefix}{atm}"
                            curr_time = datetime.now().strftime("%H:%M:%S")
                            
                            # MUST HAVE VALID OI/VOL DATA TO EXECUTE
                            if valid_data:
                                if ce_safety >= 75.0 and c_price and ce_ltp > 0:
                                    try:
                                        order_id = obj.placeOrder({"variety":"NORMAL", "tradingsymbol":f"{target_sym}CE", "symboltoken":atm_ce_tok, "transactiontype":"BUY", "exchange":"NFO", "ordertype":"MARKET", "producttype":"INTRADAY", "duration":"DAY", "quantity":str(total_qty)})
                                        if order_id:
                                            st.session_state.active_trade = {'type': 'CE', 'symbol': f"{target_sym}CE", 'entry_spot': float(spot), 'target_spot': float(spot + tgt_points), 'sl_spot': float(spot - sl_points), 'time': curr_time}
                                            st.success(f"🤖 BOUGHT CALL! Order ID: {order_id}")
                                    except Exception as e: st.error(f"❌ Order Failed: {e}") 

                                elif pe_safety >= 75.0 and p_price and pe_ltp > 0:
                                    try:
                                        order_id = obj.placeOrder({"variety":"NORMAL", "tradingsymbol":f"{target_sym}PE", "symboltoken":atm_pe_tok, "transactiontype":"BUY", "exchange":"NFO", "ordertype":"MARKET", "producttype":"INTRADAY", "duration":"DAY", "quantity":str(total_qty)})
                                        if order_id:
                                            st.session_state.active_trade = {'type': 'PE', 'symbol': f"{target_sym}PE", 'entry_spot': float(spot), 'target_spot': float(spot - tgt_points), 'sl_spot': float(spot + sl_points), 'time': curr_time}
                                            st.success(f"🤖 BOUGHT PUT! Order ID: {order_id}")
                                    except Exception as e: st.error(f"❌ Order Failed: {e}")
                        else:
                            st.warning("⚠️ Auto-Trade is OFF. Tick 'Enable Auto-Trade Mode' in the sidebar.")
                    else:
                        trade = st.session_state.active_trade
                        pnl_spot = round(spot - trade['entry_spot'] if trade['type'] == 'CE' else trade['entry_spot'] - spot, 2)
                            
                        st.info(f"🚀 **ACTIVE {trade['type']} TRADE** ({trade['symbol']})")
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Live Index (Spot)", f"₹{spot}")
                        col2.metric("Spot Entry", f"₹{trade['entry_spot']}")
                        col3.metric("Target Level", f"₹{trade['target_spot']}")
                        col4.metric("StopLoss Level", f"₹{trade['sl_spot']}")
                        st.metric(label="Live P&L (Index Points)", value=f"{pnl_spot} Pts", delta=pnl_spot)
                        
                        if st.button("🚨 MANUAL EXIT NOW", use_container_width=True):
                            st.session_state.trade_history.append({"Time": datetime.now().strftime("%H:%M:%S"), "Symbol": trade['symbol'], "Type": trade['type'], "Entry (Spot)": trade['entry_spot'], "Exit (Spot)": round(spot, 2), "Target Level": trade['target_spot'], "SL Level": trade['sl_spot'], "P&L (Pts)": pnl_spot, "Status": "⚠️ Manual Exit"})
                            st.session_state.active_trade = None
                            st.rerun()

            # 📚 4. SHOW TRADE HISTORY
            if st.session_state.trade_history:
                st.divider()
                st.subheader("📚 Today's Trade History Ledger")
                hist_df = pd.DataFrame(st.session_state.trade_history)
                st.dataframe(hist_df, use_container_width=True)
                
        except Exception as e:
            st.error(f"🚨 Logic Error: {e}")
            
        time.sleep(3)
        st.rerun()
    else:
        st.info("⏸️ Live Feed is PAUSED.")
        if st.session_state.trade_history:
            st.dataframe(pd.DataFrame(st.session_state.trade_history), use_container_width=True)
else:
    st.info("Enter MPIN and Connect.")
