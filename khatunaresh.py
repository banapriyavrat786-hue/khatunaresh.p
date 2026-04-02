import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Auto-Sniper V26", layout="wide")
st.title("🏹 MKPV Ultra Sniper | Stable Action Mode")

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

# 💡 NAYA FEATURE: Feed ON/OFF karne ke liye taaki hang na ho
live_feed = st.sidebar.toggle("🟢 LIVE FEED (Auto-Refresh)", value=False)
auto_trade = st.sidebar.checkbox("🤖 Enable Auto-Trade Mode", value=False)

st.sidebar.markdown("---")
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry_str = st.sidebar.text_input("Expiry (e.g. 07APR26)", "07APR26").upper()
qty_multiplier = st.sidebar.number_input("Lots", min_value=1, value=1)

st.sidebar.subheader("🎯 Spot Index Targets")
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

        # 1. LIVE SPOT FETCH (FAST API)
        t_name = "Nifty 50" if index=="NIFTY" else "Nifty Bank"
        t_tok = "26000" if index=="NIFTY" else "26009"
        res = obj.ltpData("NSE", t_name, t_tok)
        
        if res.get('status'):
            spot = float(res['data']['ltp'])
            st.session_state.price_history.append(spot)
            if len(st.session_state.price_history) > 10: st.session_state.price_history.pop(0)
            sma = round(sum(st.session_state.price_history) / len(st.session_state.price_history), 2)
            atm = int(round(spot / (50 if index=="NIFTY" else 100)) * (50 if index=="NIFTY" else 100))

            # 2. TOKEN MAPPING (BUG FIXED: No Decimals)
            search_prefix = f"{index}{expiry_str}{atm}"
            try:
                ce_row = df[df['symbol'] == f"{search_prefix}CE"].iloc[0]
                pe_row = df[df['symbol'] == f"{search_prefix}PE"].iloc[0]
                
                ce_tok = str(ce_row['token']).split('.')[0]
                pe_tok = str(pe_row['token']).split('.')[0]

                # 3. FAST PREMIUM FETCH
                ce_res = obj.ltpData("NFO", ce_row['symbol'], ce_tok)
                pe_res = obj.ltpData("NFO", pe_row['symbol'], pe_tok)
                ce_ltp = float(ce_res['data']['ltp']) if ce_res.get('status') else 0.0
                pe_ltp = float(pe_res['data']['ltp']) if pe_res.get('status') else 0.0

                # 4. SAFE OI & VOLUME FETCH (Error Proof)
                ce_oi, ce_vol, pe_oi, pe_vol = 0, 0, 0, 0
                try:
                    m_data = obj.getMarketData("FULL", {"NFO": [ce_tok, pe_tok]})
                    if m_data and m_data.get('status'):
                        for item in m_data['data']['fetched']:
                            if item['symbolToken'] == ce_tok:
                                ce_oi, ce_vol = item['opnInterest'], item['volume']
                            elif item['symbolToken'] == pe_tok:
                                pe_oi, pe_vol = item['opnInterest'], item['volume']
                except: pass # Agar MarketData slow hai toh crash nahi hoga

                st.subheader(f"📊 Market Overview (ATM: {atm})")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Live Index (Spot)", f"₹{spot}")
                c2.metric("Trend (SMA)", f"₹{sma}")
                c3.metric(f"CE Premium", f"₹{ce_ltp}")
                c4.metric(f"PE Premium", f"₹{pe_ltp}")

                st.divider()

                # 📋 5. STRICT CHECKLIST LOGIC
                st.subheader("📋 Strict Trade Checklist")
                
                c_price, c_mom = (spot > sma), (ce_ltp > pe_ltp)
                c_oi, c_vol = (ce_oi > pe_oi), (ce_vol > pe_vol)

                p_price, p_mom = (spot < sma), (pe_ltp > ce_ltp)
                p_oi, p_vol = (pe_oi > ce_oi), (pe_vol > ce_vol)

                ce_score = sum([c_price, c_mom, c_oi, c_vol])
                pe_score = sum([p_price, p_mom, p_oi, p_vol])
                ce_safety, pe_safety = (ce_score / 4) * 100, (pe_score / 4) * 100

                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"### 🟢 CALL Sniper ({ce_safety}%)")
                    st.write(f"Trend UP: {'✅' if c_price else '❌'} | Momentum: {'✅' if c_mom else '❌'}")
                    st.write(f"OI Bias: {'✅' if c_oi else '➖'} | Volume: {'✅' if c_vol else '➖'}")
                with col_b:
                    st.markdown(f"### 🔴 PUT Sniper ({pe_safety}%)")
                    st.write(f"Trend DOWN: {'✅' if p_price else '❌'} | Momentum: {'✅' if p_mom else '❌'}")
                    st.write(f"OI Bias: {'✅' if p_oi else '➖'} | Volume: {'✅' if p_vol else '➖'}")

                # 🚀 6. AUTO-TRADE EXECUTION
                if st.session_state.active_trade is None and auto_trade:
                    if ce_safety >= 75.0:
                        obj.placeOrder({"variety":"NORMAL", "tradingsymbol":ce_row['symbol'], "symboltoken":ce_tok, "transactiontype":"BUY", "exchange":"NFO", "ordertype":"MARKET", "producttype":"INTRADAY", "duration":"DAY", "quantity":str(total_qty)})
                        st.session_state.active_trade = {'type':'CE', 'entry_spot':spot, 'target_spot':spot+tgt_points, 'sl_spot':spot-sl_points, 'symbol':ce_row['symbol']}
                        st.success(f"🤖 Auto-Trade: BOUGHT CALL!")
                    elif pe_safety >= 75.0:
                        obj.placeOrder({"variety":"NORMAL", "tradingsymbol":pe_row['symbol'], "symboltoken":pe_tok, "transactiontype":"BUY", "exchange":"NFO", "ordertype":"MARKET", "producttype":"INTRADAY", "duration":"DAY", "quantity":str(total_qty)})
                        st.session_state.active_trade = {'type':'PE', 'entry_spot':spot, 'target_spot':spot-tgt_points, 'sl_spot':spot+sl_points, 'symbol':pe_row['symbol']}
                        st.success(f"🤖 Auto-Trade: BOUGHT PUT!")

                # 📊 7. MONITORING & EXIT
                if st.session_state.active_trade:
                    trade = st.session_state.active_trade
                    pnl_spot = round(spot - trade['entry_spot'] if trade['type'] == 'CE' else trade['entry_spot'] - spot, 2)
                    st.warning(f"🚀 ACTIVE TRADE: {trade['symbol']} | Live Index P&L: {pnl_spot} Pts")
                    
                    is_exit = False
                    if trade['type'] == 'CE' and (spot >= trade['target_spot'] or spot <= trade['sl_spot']): is_exit = True
                    if trade['type'] == 'PE' and (spot <= trade['target_spot'] or spot >= trade['sl_spot']): is_exit = True

                    if is_exit or st.button("🚨 MANUAL EXIT NOW"):
                        res_msg = "✅ Target" if pnl_spot > 0 else ("❌ Stoploss" if pnl_spot < 0 else "⚠️ Manual")
                        st.session_state.trade_history.append({"Trade": trade['symbol'], "Spot P&L": pnl_spot, "Result": res_msg})
                        st.session_state.active_trade = None

            except Exception as e:
                st.error(f"Waiting for Correct Options Data... Check Expiry format. Error: {e}")
        
        # Auto-Refresh Loop
        time.sleep(2)
        st.rerun()
    else:
        # LIVE FEED OFF UI
        st.info("⏸️ Live Feed is PAUSED. Toggle '🟢 LIVE FEED (Auto-Refresh)' from sidebar to start tracking.")
        
        # 📚 SHOW HISTORY EVEN WHEN PAUSED
        if st.session_state.trade_history:
            st.divider()
            st.subheader("📚 Today's Trade History")
            st.table(pd.DataFrame(st.session_state.trade_history))
else:
    st.info("Enter MPIN and Connect to start the Sniper.")
