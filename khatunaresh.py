import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time
from datetime import datetime

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Auto-Sniper V42", layout="wide")
st.title("🏹 MKPV Ultra Sniper | Live Data Feed Mode")

# -- SESSION STATE INITIALIZATION --
for key in ['connected', 'obj', 'token_df', 'active_trade', 'trade_history', 'price_history', 'last_valid_data']:
    if key not in st.session_state:
        if key == 'price_history': st.session_state[key] = []
        elif key == 'trade_history': st.session_state[key] = []
        elif key == 'last_valid_data': st.session_state[key] = {'ce_oi': 0, 'pe_oi': 0, 'ce_vol': 0, 'pe_vol': 0}
        else: st.session_state[key] = None

# -- TIME FUNCTION --
def get_time():
    try:
        return requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5).json()['unixtime']
    except:
        return int(time.time())

# -- TOKEN LOADER --
@st.cache_data(ttl=3600, show_spinner="Downloading Tokens...")
def load_tokens():
    try:
        res = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json", timeout=30)
        if res.status_code == 200:
            df = pd.DataFrame(res.json())
            return df[df['exch_seg'] == "NFO"]
    except: pass
    return None

# -- SIDEBAR CONTROLS --
st.sidebar.title("⚙️ Robot Controls")
live_feed = st.sidebar.checkbox("🟢 LIVE FEED (Auto-Refresh)", value=False)
auto_trade = st.sidebar.checkbox("🤖 Enable Auto-Trade Mode", value=False)

st.sidebar.markdown("---")
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (e.g. 07APR26)", "07APR26").upper()
lots = st.sidebar.number_input("Lots", 1, 10, 1)

st.sidebar.subheader("🎯 Target & StopLoss")
tgt = st.sidebar.number_input("Target Points", 40.0, step=5.0)
sl = st.sidebar.number_input("Stoploss Points", 20.0, step=5.0)

mpin = st.sidebar.text_input("MPIN", type="password")

# -- LOGIN --
if st.sidebar.button("🔑 Connect"):
    st.session_state.token_df = load_tokens()
    if st.session_state.token_df is not None:
        otp = pyotp.TOTP(TOTP_SECRET.strip().replace(" ", "")).at(get_time())
        obj = SmartConnect(api_key=API_KEY)
        login = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
        if login.get('status'):
            st.session_state.connected = True
            st.session_state.obj = obj
            st.sidebar.success("✅ Connected Successfully!")
        else: st.sidebar.error("❌ Login Failed.")
    else: st.sidebar.error("❌ Token Data Failed.")

# -- MAIN DASHBOARD --
if st.session_state.connected:
    if live_feed:
        obj = st.session_state.obj
        df = st.session_state.token_df

        if df is None or df.empty: st.stop()

        step = 50 if index == "NIFTY" else 100
        lot_size = 50 if index == "NIFTY" else 15
        qty = lot_size * lots

        name = "Nifty 50" if index == "NIFTY" else "Nifty Bank"
        token = "26000" if index == "NIFTY" else "26009"

        try:
            # 1. FETCH SPOT & TREND
            res = obj.ltpData("NSE", name, token)
            if res and res.get('status'):
                spot = float(res['data']['ltp'])

                ph = st.session_state.price_history
                ph.append(spot)
                if len(ph) > 10: ph.pop(0)

                sma = sum(ph) / len(ph)
                atm = int(round(spot / step) * step)
                prefix = f"{index}{expiry}{atm}"

                try:
                    ce_row = df[df['symbol'] == f"{prefix}CE"].iloc[0]
                    pe_row = df[df['symbol'] == f"{prefix}PE"].iloc[0]
                    ce_tok = str(ce_row['token']).split('.')[0]
                    pe_tok = str(pe_row['token']).split('.')[0]
                except:
                    ce_tok, pe_tok = "", ""

                # 2. MEMORY ENGINE
                ce_oi = st.session_state.last_valid_data['ce_oi']
                pe_oi = st.session_state.last_valid_data['pe_oi']
                ce_vol = st.session_state.last_valid_data['ce_vol']
                pe_vol = st.session_state.last_valid_data['pe_vol']
                ce_ltp = pe_ltp = 0.0
                max_ce_oi, resistance_strike = 0, atm + (step*3) 
                max_pe_oi, support_strike = 0, atm - (step*3)

                if ce_tok and pe_tok:
                    try:
                        md = obj.getMarketData("FULL", {"NFO": [ce_tok, pe_tok]})
                        if md and md.get('status'):
                            for item in md['data']['fetched']:
                                tok = item['symbolToken']
                                fetched_oi = item.get('opnInterest', 0)
                                fetched_vol = item.get('volume', item.get('tradeVolume', 0))
                                fetched_ltp = item.get('lastTradedPrice', 0.0)

                                if tok == ce_tok:
                                    if fetched_oi > 0: 
                                        ce_oi = fetched_oi
                                        st.session_state.last_valid_data['ce_oi'] = fetched_oi
                                    if fetched_vol > 0: 
                                        ce_vol = fetched_vol
                                        st.session_state.last_valid_data['ce_vol'] = fetched_vol
                                    ce_ltp = fetched_ltp

                                if tok == pe_tok:
                                    if fetched_oi > 0: 
                                        pe_oi = fetched_oi
                                        st.session_state.last_valid_data['pe_oi'] = fetched_oi
                                    if fetched_vol > 0: 
                                        pe_vol = fetched_vol
                                        st.session_state.last_valid_data['pe_vol'] = fetched_vol
                                    pe_ltp = fetched_ltp
                    except: pass

                # 3. VALIDATION & LOGIC
                valid = (ce_oi > 0 and pe_oi > 0 and ce_vol > 0 and pe_vol > 0)

                c_price = spot > sma
                p_price = spot < sma
                c_mom = ce_ltp > pe_ltp
                p_mom = pe_ltp > ce_ltp

                if valid:
                    c_oi = pe_oi > ce_oi
                    p_oi = ce_oi > pe_oi
                    c_vol = pe_vol > ce_vol
                    p_vol = ce_vol > pe_vol
                else:
                    c_oi = p_oi = c_vol = p_vol = False

                ce_safe = round((sum([c_price, c_mom, c_oi, c_vol]) / 4) * 100, 1)
                pe_safe = round((sum([p_price, p_mom, p_oi, p_vol]) / 4) * 100, 1)

                # 4. EXITS FIRST
                if st.session_state.active_trade is not None:
                    t = st.session_state.active_trade
                    pnl_spot = round(spot - t['entry'] if t['type'] == "CE" else t['entry'] - spot, 2)
                    
                    is_target = spot >= t['target'] if t['type'] == 'CE' else spot <= t['target']
                    is_sl = spot <= t['sl'] if t['type'] == 'CE' else spot >= t['sl']

                    if is_target or is_sl:
                        res_msg = "✅ Target Hit" if is_target else "❌ StopLoss Hit"
                        st.session_state.trade_history.append({"Time": datetime.now().strftime("%H:%M:%S"), "Symbol": t['symbol'], "Type": t['type'], "Entry (Spot)": t['entry'], "Exit (Spot)": round(spot, 2), "P&L (Pts)": pnl_spot, "Status": res_msg})
                        st.session_state.active_trade = None
                        st.success(f"⚡ Trade Closed: {res_msg} at {spot}!")
                        time.sleep(1)
                        st.rerun()

                # 5. UI DASHBOARD
                market_state = "Sideways / Conflicting ⚖️"
                if spot > sma and pe_oi > ce_oi: market_state = "Bullish Trending 📈"
                elif spot < sma and ce_oi > pe_oi: market_state = "Bearish Trending 📉"

                st.subheader(f"📊 Market Condition: {market_state} (ATM: {atm})")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Live Index (Spot)", f"₹{spot}")
                c2.metric("Trend (SMA)", f"₹{round(sma, 2)}")
                c3.metric("Call Score (Bullish)", f"{ce_safe}%")
                c4.metric("Put Score (Bearish)", f"{pe_safe}%")

                st.divider()

                # 💡 V42 NAYA FEATURE: LIVE OI & VOLUME DATA FEED 
                st.subheader("🔍 Live ATM Data Feed (Option Writers)")
                if valid:
                    d1, d2, d3, d4 = st.columns(4)
                    d1.metric(label="Call Sellers OI (CE OI)", value=f"{ce_oi:,}")
                    d2.metric(label="Put Sellers OI (PE OI)", value=f"{pe_oi:,}")
                    d3.metric(label="Call Volume (CE Vol)", value=f"{ce_vol:,}")
                    d4.metric(label="Put Volume (PE Vol)", value=f"{pe_vol:,}")
                else:
                    st.warning("⚠️ API Data Pending/Zero. Using last known data in memory...")

                st.divider()

                # 6. CHECKLIST RESTORED
                def check_icon(val): return "✅" if val else ("⚠️ Pending" if not valid else "❌")

                st.subheader("📋 Strict Sniper Checklist")
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"### 🟢 CALL Sniper ({ce_safe}%)")
                    st.write(f"Trend UP (Spot > SMA): {'✅' if c_price else '❌'}")
                    st.write(f"Momentum (CE > PE): {'✅' if c_mom else '❌'}")
                    st.write(f"Support Strong (PE OI > CE OI): {check_icon(c_oi)}")
                    st.write(f"Put Writers Active (PE Vol > CE Vol): {check_icon(c_vol)}")
                with col_b:
                    st.markdown(f"### 🔴 PUT Sniper ({pe_safe}%)")
                    st.write(f"Trend DOWN (Spot < SMA): {'✅' if p_price else '❌'}")
                    st.write(f"Momentum (PE > CE): {'✅' if p_mom else '❌'}")
                    st.write(f"Resistance Strong (CE OI > PE OI): {check_icon(p_oi)}")
                    st.write(f"Call Writers Active (CE Vol > PE Vol): {check_icon(p_vol)}")

                st.divider()

                # 7. AUTO-TRADE ENTRY
                if st.session_state.active_trade is None:
                    if auto_trade and valid:
                        st.info("🤖 Scanning for 75% Setup...")
                        curr_time = datetime.now().strftime("%H:%M:%S")

                        if ce_safe >= 75.0 and c_price:
                            try:
                                obj.placeOrder({"variety":"NORMAL", "tradingsymbol":ce_row['symbol'], "symboltoken":ce_tok, "transactiontype":"BUY", "exchange":"NFO", "ordertype":"MARKET", "producttype":"INTRADAY", "duration":"DAY", "quantity":str(qty)})
                                st.session_state.active_trade = {"type": "CE", "symbol": ce_row['symbol'], "entry": float(spot), "target": float(spot + tgt), "sl": float(spot - sl), "time": curr_time}
                                st.success("🤖 BOUGHT CALL!")
                            except Exception as e: st.error(f"Order Failed: {e}")

                        elif pe_safe >= 75.0 and p_price:
                            try:
                                obj.placeOrder({"variety":"NORMAL", "tradingsymbol":pe_row['symbol'], "symboltoken":pe_tok, "transactiontype":"BUY", "exchange":"NFO", "ordertype":"MARKET", "producttype":"INTRADAY", "duration":"DAY", "quantity":str(qty)})
                                st.session_state.active_trade = {"type": "PE", "symbol": pe_row['symbol'], "entry": float(spot), "target": float(spot - tgt), "sl": float(spot + sl), "time": curr_time}
                                st.success("🤖 BOUGHT PUT!")
                            except Exception as e: st.error(f"Order Failed: {e}")
                    else:
                        st.warning("⚠️ Auto-Trade is OFF or Data is Pending. Tick 'Enable Auto-Trade'.")
                else:
                    t = st.session_state.active_trade
                    pnl_spot = round(spot - t['entry'] if t['type'] == "CE" else t['entry'] - spot, 2)
                    
                    st.info(f"🚀 **ACTIVE {t['type']} TRADE** ({t['symbol']})")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Live Index (Spot)", f"₹{spot}")
                    col2.metric("Spot Entry", f"₹{t['entry']}")
                    col3.metric("Target Level", f"₹{t['target']}")
                    col4.metric("StopLoss Level", f"₹{t['sl']}")
                    st.metric(label="Live P&L (Index Points)", value=f"{pnl_spot} Pts", delta=pnl_spot)
                    
                    if st.button("🚨 MANUAL EXIT NOW", use_container_width=True):
                        st.session_state.trade_history.append({"Time": datetime.now().strftime("%H:%M:%S"), "Symbol": t['symbol'], "Type": t['type'], "Entry (Spot)": t['entry'], "Exit (Spot)": round(spot, 2), "P&L (Pts)": pnl_spot, "Status": "⚠️ Manual Exit"})
                        st.session_state.active_trade = None
                        st.rerun()

            # 8. HISTORY LEDGER
            if st.session_state.trade_history:
                st.divider()
                st.subheader("📚 Today's Trade History Ledger")
                st.dataframe(pd.DataFrame(st.session_state.trade_history), use_container_width=True)

        except Exception as e:
            st.error(f"🚨 Engine Error: {e}")

        time.sleep(3)
        st.rerun()
    else:
        st.info("⏸️ Live Feed is PAUSED.")
        if
