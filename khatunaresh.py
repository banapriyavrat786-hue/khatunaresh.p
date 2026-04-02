import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Auto-Sniper V28", layout="wide")
st.title("🏹 MKPV Ultra Sniper | Flawless Execution")

# -- SESSION STATE --
if 'connected' not in st.session_state: st.session_state.connected = False
if 'obj' not in st.session_state: st.session_state.obj = None
if 'token_df' not in st.session_state: st.session_state.token_df = None
if 'active_trade' not in st.session_state: st.session_state.active_trade = None
if 'trade_history' not in st.session_state: st.session_state.trade_history = []
if 'price_history' not in st.session_state: st.session_state.price_history = []

def get_internet_time():
    try:
        r = requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5)
        return r.json()['unixtime']
    except: return int(time.time())

@st.cache_data(ttl=3600)
def load_tokens():
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    try:
        res = requests.get(url, timeout=10)
        df = pd.DataFrame(res.json())
        return df[df['exch_seg'] == 'NFO']
    except: return None

# -- SIDEBAR CONTROLS --
st.sidebar.title("⚙️ Robot Controls")
live_feed = st.sidebar.toggle("🟢 LIVE FEED (Auto-Refresh)", value=False)
auto_trade = st.sidebar.checkbox("🤖 Enable Auto-Trade Mode", value=False)

st.sidebar.markdown("---")
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry_str = st.sidebar.text_input("Expiry (e.g. 07APR26)", "07APR26").upper()
qty_multiplier = st.sidebar.number_input("Lots", min_value=1, value=1)

st.sidebar.subheader("🎯 Target & StopLoss (Spot Points)")
tgt_points = st.sidebar.number_input("Target Points", value=40)
sl_points = st.sidebar.number_input("StopLoss Points", value=20)
mpin = st.sidebar.text_input("MPIN", type="password", max_chars=4)

if st.sidebar.button("🔑 Connect"):
    otp = pyotp.TOTP(TOTP_SECRET.strip().replace(" ", "")).at(get_internet_time())
    smart_obj = SmartConnect(api_key=API_KEY)
    login = smart_obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
    if login.get('status'):
        st.session_state.connected = True
        st.session_state.obj = smart_obj
        st.session_state.token_df = load_tokens()
        st.sidebar.success("✅ System Online! Turn ON Live Feed.")

# -- MAIN DASHBOARD --
if st.session_state.connected:
    if live_feed:
        obj = st.session_state.obj
        df = st.session_state.token_df
        lot_size = 50 if index == "NIFTY" else 15
        total_qty = lot_size * int(qty_multiplier)

        # 1. LIVE SPOT FETCH
        t_name = "Nifty 50" if index=="NIFTY" else "Nifty Bank"
        t_tok = "26000" if index=="NIFTY" else "26009"
        res = obj.ltpData("NSE", t_name, t_tok)
        
        if res.get('status'):
            spot = float(res['data']['ltp'])
            st.session_state.price_history.append(spot)
            if len(st.session_state.price_history) > 10: st.session_state.price_history.pop(0)
            sma = round(sum(st.session_state.price_history) / len(st.session_state.price_history), 2)
            step = 50 if index=="NIFTY" else 100
            atm = int(round(spot / step) * step)

            # 2. FETCH TOKENS FOR ATM AND NEARBY STRIKES
            search_prefix = f"{index}{expiry_str}"
            strikes_to_scan = [atm - step, atm, atm + step]
            tokens_list = []
            strike_map = {}

            # Build list of tokens to fetch OI for Support/Resistance
            for s in strikes_to_scan:
                c_df = df[df['symbol'] == f"{search_prefix}{s}CE"]
                p_df = df[df['symbol'] == f"{search_prefix}{s}PE"]
                if not c_df.empty and not p_df.empty:
                    c_tok = str(c_df.iloc[0]['token']).split('.')[0]
                    p_tok = str(p_df.iloc[0]['token']).split('.')[0]
                    tokens_list.extend([c_tok, p_tok])
                    strike_map[c_tok] = {'type': 'CE', 'strike': s}
                    strike_map[p_tok] = {'type': 'PE', 'strike': s}

            # 3. FETCH FULL MARKET DATA (OI & VOLUME)
            max_ce_oi, resistance_strike = 0, atm
            max_pe_oi, support_strike = 0, atm
            ce_ltp, pe_ltp, ce_oi, pe_oi, ce_vol, pe_vol = 0.0, 0.0, 0, 0, 0, 0
            atm_ce_tok, atm_pe_tok = "", ""

            try:
                m_data = obj.getMarketData("FULL", {"NFO": tokens_list})
                if m_data and m_data.get('status'):
                    for item in m_data['data']['fetched']:
                        tok = item['symbolToken']
                        t_type = strike_map[tok]['type']
                        t_strike = strike_map[tok]['strike']
                        
                        # Find S/R using Max OI
                        if t_type == 'CE' and item['opnInterest'] > max_ce_oi:
                            max_ce_oi = item['opnInterest']
                            resistance_strike = t_strike
                        elif t_type == 'PE' and item['opnInterest'] > max_pe_oi:
                            max_pe_oi = item['opnInterest']
                            support_strike = t_strike

                        # Save ATM specific data for Checklist
                        if t_strike == atm:
                            if t_type == 'CE':
                                ce_ltp, ce_oi, ce_vol = item['lastTradedPrice'], item['opnInterest'], item['volume']
                                atm_ce_tok = tok
                            else:
                                pe_ltp, pe_oi, pe_vol = item['lastTradedPrice'], item['opnInterest'], item['volume']
                                atm_pe_tok = tok
            except Exception as e:
                st.warning("⚠️ Fetching Market Data...")

            # 📊 DASHBOARD METRICS
            st.subheader(f"📊 Market Overview (ATM: {atm})")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Live Index (Spot)", f"₹{spot}")
            c2.metric("Trend (SMA)", f"₹{sma}")
            c3.metric("Resistance (High CE OI)", f"Strike: {resistance_strike}")
            c4.metric("Support (High PE OI)", f"Strike: {support_strike}")

            st.divider()

            # 📋 4. STRICT CHECKLIST LOGIC (With 0 Error Handling)
            st.subheader("📋 Trade Confirmation Checklist")
            
            # 💡 Agar Angel One api 0 Volume bheje, toh us logic ko skip karke price action ko priority do
            valid_oi_vol = (ce_oi > 0 and pe_oi > 0)
            
            c_price = spot > sma
            c_mom = ce_ltp > pe_ltp
            c_oi = (ce_oi > pe_oi) if valid_oi_vol else True
            c_vol = (ce_vol > pe_vol) if valid_oi_vol else True

            p_price = spot < sma
            p_mom = pe_ltp > ce_ltp
            p_oi = (pe_oi > ce_oi) if valid_oi_vol else True
            p_vol = (pe_vol > ce_vol) if valid_oi_vol else True

            ce_score = sum([c_price, c_mom, c_oi, c_vol])
            pe_score = sum([p_price, p_mom, p_oi, p_vol])
            ce_safety = (ce_score / 4) * 100
            pe_safety = (pe_score / 4) * 100

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"### 🟢 CALL Sniper ({ce_safety}%)")
                st.write(f"Trend UP (Spot > SMA): {'✅' if c_price else '❌'}")
                st.write(f"Momentum (CE > PE): {'✅' if c_mom else '❌'}")
                st.write(f"OI Bias (CE > PE): {'✅' if c_oi else '❌'}")
                st.write(f"Volume (CE > PE): {'✅' if c_vol else '❌'}")
            with col_b:
                st.markdown(f"### 🔴 PUT Sniper ({pe_safety}%)")
                st.write(f"Trend DOWN (Spot < SMA): {'✅' if p_price else '❌'}")
                st.write(f"Momentum (PE > CE): {'✅' if p_mom else '❌'}")
                st.write(f"OI Bias (PE > CE): {'✅' if p_oi else '❌'}")
                st.write(f"Volume (PE > CE): {'✅' if p_vol else '❌'}")

            st.divider()

            # 🚀 5. AUTO-TRADE EXECUTION (With Error Catching)
            if st.session_state.active_trade is None:
                st.info("⏳ Waiting for 75% Safety Setup...")
                if auto_trade:
                    target_sym = f"{search_prefix}{atm}"
                    
                    if ce_safety >= 75.0 and ce_ltp > 0:
                        try:
                            order_id = obj.placeOrder({"variety":"NORMAL", "tradingsymbol":f"{target_sym}CE", "symboltoken":atm_ce_tok, "transactiontype":"BUY", "exchange":"NFO", "ordertype":"MARKET", "producttype":"INTRADAY", "duration":"DAY", "quantity":str(total_qty)})
                            if order_id:
                                st.session_state.active_trade = {'type':'CE', 'entry_spot':spot, 'target_spot':spot+tgt_points, 'sl_spot':spot-sl_points, 'symbol':f"{target_sym}CE"}
                                st.success(f"🤖 Auto-Trade: BOUGHT CALL! (Order ID: {order_id})")
                        except Exception as e:
                            st.error(f"❌ Order Failed: {e}") # 💡 Ab agar order reject hoga toh reason dikhega

                    elif pe_safety >= 75.0 and pe_ltp > 0:
                        try:
                            order_id = obj.placeOrder({"variety":"NORMAL", "tradingsymbol":f"{target_sym}PE", "symboltoken":atm_pe_tok, "transactiontype":"BUY", "exchange":"NFO", "ordertype":"MARKET", "producttype":"INTRADAY", "duration":"DAY", "quantity":str(total_qty)})
                            if order_id:
                                st.session_state.active_trade = {'type':'PE', 'entry_spot':spot, 'target_spot':spot-tgt_points, 'sl_spot':spot+sl_points, 'symbol':f"{target_sym}PE"}
                                st.success(f"🤖 Auto-Trade: BOUGHT PUT! (Order ID: {order_id})")
                        except Exception as e:
                            st.error(f"❌ Order Failed: {e}")

            # 📊 6. MONITORING & EXIT
            else:
                trade = st.session_state.active_trade
                pnl_spot = round(spot - trade['entry_spot'] if trade['type'] == 'CE' else trade['entry_spot'] - spot, 2)
                
                st.warning(f"🚀 ACTIVE TRADE: {trade['symbol']} | Live Index P&L: {pnl_spot} Pts")
                st.write(f"**Spot Entry:** ₹{trade['entry_spot']} | **Target:** ₹{trade['target_spot']} | **StopLoss:** ₹{trade['sl_spot']}")
                
                is_exit = False
                if trade['type'] == 'CE' and (spot >= trade['target_spot'] or spot <= trade['sl_spot']): is_exit = True
                if trade['type'] == 'PE' and (spot <= trade['target_spot'] or spot >= trade['sl_spot']): is_exit = True

                if is_exit or st.button("🚨 MANUAL EXIT NOW"):
                    res_msg = "✅ Target" if pnl_spot > 0 else ("❌ Stoploss" if pnl_spot < 0 else "⚠️ Manual")
                    st.session_state.trade_history.append({"Trade": trade['symbol'], "Spot P&L": pnl_spot, "Result": res_msg})
                    st.session_state.active_trade = None

        except Exception as e:
            st.error(f"Data Syncing... {e}")
        
        time.sleep(2)
        st.rerun()
    else:
        st.info("⏸️ Live Feed is PAUSED. Toggle '🟢 LIVE FEED' to start.")
        if st.session_state.trade_history:
            st.divider()
            st.subheader("📚 Today's Trade History")
            st.table(pd.DataFrame(st.session_state.trade_history))
else:
    st.info("Enter MPIN and Connect to start the Sniper.")
