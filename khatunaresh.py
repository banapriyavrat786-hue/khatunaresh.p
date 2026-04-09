import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time
from datetime import datetime

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Auto-Sniper V56", layout="wide")
st.title("🏹 MKPV Ultra Sniper | Dynamic Target Engine")

# -- SESSION STATE INITIALIZATION --
for key in ['connected', 'obj', 'token_df', 'active_trade', 'trade_history', 'price_history', 'vol_history', 'last_valid_data']:
    if key not in st.session_state:
        if key == 'price_history': st.session_state[key] = []
        elif key == 'vol_history': st.session_state[key] = []
        elif key == 'trade_history': st.session_state[key] = []
        elif key == 'last_valid_data': st.session_state[key] = {'ce_oi': 0, 'pe_oi': 0, 'ce_vol': 0, 'pe_vol': 0, 'total_ce_oi': 0, 'total_pe_oi': 0}
        else: st.session_state[key] = None

def get_time():
    try:
        return requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5).json()['unixtime']
    except:
        return int(time.time())

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

st.sidebar.subheader("🎯 Auto Target/SL (VIX Based)")
# 💡 V56 NEW: Auto calculation multipliers based on Volatility
vix_tgt_mult = st.sidebar.number_input("Target Multiplier (VIX x)", value=3.0, step=0.5)
vix_sl_mult = st.sidebar.number_input("StopLoss Multiplier (VIX x)", value=1.5, step=0.5)

st.sidebar.subheader("🎛️ Institutional Filters")
history_ticks = st.sidebar.number_input("VWAP Speed (Ticks)", min_value=10, max_value=200, value=30, step=10)
min_vix = st.sidebar.number_input("Minimum VIX Required", value=11.5, step=0.5)
trend_buffer = st.sidebar.number_input("VWAP Noise Buffer", value=2.0, step=0.5)

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

        if df is None or df.empty: 
            st.error("Token List is empty.")
            st.stop()

        step = 50 if index == "NIFTY" else 100
        lot_size = 50 if index == "NIFTY" else 15
        qty = lot_size * lots

        name = "Nifty 50" if index == "NIFTY" else "Nifty Bank"
        token = "26000" if index == "NIFTY" else "26009"

        try:
            # 1. FETCH SPOT & VIX
            res = obj.ltpData("NSE", name, token)
            vix_res = obj.ltpData("NSE", "INDIA VIX", "26017") 
            
            if res and res.get('status'):
                spot = float(res['data']['ltp'])
                live_vix = float(vix_res['data']['ltp']) if (vix_res and vix_res.get('status')) else 12.0

                atm = int(round(spot / step) * step)
                search_prefix = f"{index}{expiry}"

                try:
                    ce_row = df[df['symbol'] == f"{search_prefix}{atm}CE"].iloc[0]
                    pe_row = df[df['symbol'] == f"{search_prefix}{atm}PE"].iloc[0]
                    ce_tok = str(ce_row['token']).split('.')[0]
                    pe_tok = str(pe_row['token']).split('.')[0]
                except:
                    ce_tok, pe_tok = "", ""

                # 2. FULL OPTION CHAIN RADAR (Macro Market Range)
                ce_oi = st.session_state.last_valid_data['ce_oi']
                pe_oi = st.session_state.last_valid_data['pe_oi']
                ce_vol = st.session_state.last_valid_data['ce_vol']
                pe_vol = st.session_state.last_valid_data['pe_vol']
                total_ce_oi = st.session_state.last_valid_data['total_ce_oi']
                total_pe_oi = st.session_state.last_valid_data['total_pe_oi']
                
                ce_ltp = pe_ltp = 0.0
                max_ce_oi, resistance_strike = 0, atm + (step*5) 
                max_pe_oi, support_strike = 0, atm - (step*5)

                if ce_tok and pe_tok:
                    strikes_to_scan = [atm + (step * i) for i in range(-10, 11)]
                    ce_tokens = []
                    pe_tokens = []
                    strike_map = {}

                    for s in strikes_to_scan:
                        c_df = df[df['symbol'] == f"{search_prefix}{s}CE"]
                        p_df = df[df['symbol'] == f"{search_prefix}{s}PE"]
                        if not c_df.empty and not p_df.empty:
                            c_tok_id = str(c_df.iloc[0]['token']).split('.')[0]
                            p_tok_id = str(p_df.iloc[0]['token']).split('.')[0]
                            ce_tokens.append(c_tok_id)
                            pe_tokens.append(p_tok_id)
                            strike_map[c_tok_id] = {'type': 'CE', 'strike': s}
                            strike_map[p_tok_id] = {'type': 'PE', 'strike': s}

                    try:
                        c_ltp_res = obj.ltpData("NFO", ce_row['symbol'], ce_tok)
                        p_ltp_res = obj.ltpData("NFO", pe_row['symbol'], pe_tok)
                        if c_ltp_res and c_ltp_res.get('status'): ce_ltp = float(c_ltp_res['data']['ltp'])
                        if p_ltp_res and p_ltp_res.get('status'): pe_ltp = float(p_ltp_res['data']['ltp'])

                        # PROCESS FULL CALL CHAIN
                        current_total_ce_oi = 0
                        ce_data = obj.getMarketData("FULL", {"NFO": ce_tokens})
                        if ce_data and ce_data.get('status'):
                            for item in ce_data['data']['fetched']:
                                tok_id = item['symbolToken']
                                if tok_id not in strike_map: continue
                                t_strike = strike_map[tok_id]['strike']
                                f_oi = item.get('opnInterest', 0)
                                current_total_ce_oi += f_oi
                                
                                if f_oi > max_ce_oi:
                                    max_ce_oi = f_oi
                                    resistance_strike = t_strike

                                if t_strike == atm:
                                    f_vol = item.get('volume', item.get('tradeVolume', 0))
                                    if f_oi > 0: ce_oi = f_oi
                                    if f_vol > 0: ce_vol = f_vol
                                        
                            if current_total_ce_oi > 0: total_ce_oi = current_total_ce_oi

                        time.sleep(0.5)

                        # PROCESS FULL PUT CHAIN
                        current_total_pe_oi = 0
                        pe_data = obj.getMarketData("FULL", {"NFO": pe_tokens})
                        if pe_data and pe_data.get('status'):
                            for item in pe_data['data']['fetched']:
                                tok_id = item['symbolToken']
                                if tok_id not in strike_map: continue
                                t_strike = strike_map[tok_id]['strike']
                                f_oi = item.get('opnInterest', 0)
                                current_total_pe_oi += f_oi

                                if f_oi > max_pe_oi:
                                    max_pe_oi = f_oi
                                    support_strike = t_strike

                                if t_strike == atm:
                                    f_vol = item.get('volume', item.get('tradeVolume', 0))
                                    if f_oi > 0: pe_oi = f_oi
                                    if f_vol > 0: pe_vol = f_vol
                                        
                            if current_total_pe_oi > 0: total_pe_oi = current_total_pe_oi
                    except: pass

                # DUAL-ENGINE CALCULATION (SMA + VWAP)
                current_total_vol = ce_vol + pe_vol
                ph = st.session_state.price_history
                vh = st.session_state.vol_history
                
                ph.append(spot)
                vh.append(current_total_vol)
                while len(ph) > int(history_ticks): 
                    ph.pop(0)
                    vh.pop(0)

                sma = sum(ph) / len(ph) if len(ph) > 0 else spot
                if sum(vh) > 0: vwap = sum(p * v for p, v in zip(ph, vh)) / sum(vh)
                else: vwap = sma

                pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 1.0

                # 3. 💡 V56: DYNAMIC SPOT-BASED TARGET & SL (The Immediate Fix)
                # Ye bot khud live market ki volatility (VIX) se nikalega!
                dynamic_tgt = round(live_vix * vix_tgt_mult, 1)
                dynamic_sl = round(live_vix * vix_sl_mult, 1)

                # Auto-Time Logic 
                current_hour = datetime.now().hour
                current_min = datetime.now().minute
                c_time = current_hour + (current_min / 60.0)
                is_good_time = (9.25 <= c_time <= 11.5) or (13.0 <= c_time <= 15.0)

                # 4. VALIDATION & BUYER LOGIC
                valid = (ce_oi > 0 and pe_oi > 0 and ce_vol > 0 and pe_vol > 0)
                vix_ok = live_vix >= min_vix

                c_price = (spot > (sma + trend_buffer)) and (spot > (vwap + trend_buffer))
                p_price = (spot < (sma - trend_buffer)) and (spot < (vwap - trend_buffer))
                
                c_mom = ce_ltp > pe_ltp
                p_mom = pe_ltp > ce_ltp

                if valid:
                    c_oi = ce_oi > pe_oi
                    c_vol = ce_vol > pe_vol
                    c_pcr = pcr <= 1.0  
                    
                    p_oi = pe_oi > ce_oi
                    p_vol = pe_vol > ce_vol
                    p_pcr = pcr >= 1.0  
                else:
                    c_oi = p_oi = c_vol = p_vol = c_pcr = p_pcr = False

                ce_safe = round((sum([c_price, c_mom, c_oi, c_vol, c_pcr]) / 5) * 100, 1)
                pe_safe = round((sum([p_price, p_mom, p_oi, p_vol, p_pcr]) / 5) * 100, 1)

                # 5. SMART EXITS 
                if st.session_state.active_trade is not None:
                    t = st.session_state.active_trade
                    pnl_spot = round(spot - t['entry'] if t['type'] == "CE" else t['entry'] - spot, 2)
                    
                    is_target = spot >= t['target'] if t['type'] == 'CE' else spot <= t['target']
                    is_sl = spot <= t['sl'] if t['type'] == 'CE' else spot >= t['sl']
                    
                    is_smart_exit = False
                    smart_reason = ""
                    
                    if valid:
                        if t['type'] == "CE" and ce_safe <= 40.0:
                            is_smart_exit = True
                            smart_reason = "Data Flipped Bearish"
                        elif t['type'] == "PE" and pe_safe <= 40.0:
                            is_smart_exit = True
                            smart_reason = "Data Flipped Bullish"

                    if is_target or is_sl or is_smart_exit:
                        if is_target: res_msg = "✅ Auto-Target Hit"
                        elif is_sl: res_msg = "❌ Auto-StopLoss Hit"
                        else: res_msg = f"🛡️ Smart Exit ({smart_reason})"
                            
                        trade_record = {"Time": datetime.now().strftime("%H:%M:%S"), "Symbol": t['symbol'], "Type": t['type'], "Entry": t['entry'], "Exit": round(spot, 2), "P&L": pnl_spot, "Status": res_msg}
                        st.session_state.trade_history.append(trade_record)
                        st.session_state.active_trade = None
                        st.success(f"⚡ Trade Closed: {res_msg} at {spot}!")
                        time.sleep(1.5)
                        st.rerun()

                # 6. UI DASHBOARD
                st.subheader(f"🌐 Macro Market Radar (Scanned 21 Strikes)")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Live Index (Spot)", f"₹{spot}")
                c2.metric("Macro Support (Base)", f"Strike: {support_strike}")
                c3.metric("Macro Resistance (Top)", f"Strike: {resistance_strike}")
                c4.metric("Market Range", f"{resistance_strike - support_strike} Pts")

                st.divider()

                # 💡 V56: Naya Immediate Geometry Panel
                st.subheader("🎯 Immediate Trade Geometry (Spot-Based)")
                if valid:
                    d1, d2, d3, d4 = st.columns(4)
                    d1.metric(label="Auto Target (VIX-Based)", value=f"+{dynamic_tgt} Pts", help="Automatically calculated from Volatility")
                    d2.metric(label="Auto StopLoss (VIX-Based)", value=f"-{dynamic_sl} Pts", help="Automatically calculated from Volatility")
                    d3.metric(label="Time Zone", value="Optimal" if is_good_time else "Dead Zone", delta="Active" if is_good_time else "Wait")
                    d4.metric(label="India VIX", value=f"{live_vix}", delta="Tradeable" if vix_ok else "Avoid Trading", delta_color="normal" if vix_ok else "inverse")
                else:
                    st.warning("⚠️ Fetching Data...")

                st.divider()

                def check_icon(val): return "✅" if val else ("⚠️ Pending" if not valid else "❌")

                st.subheader("📋 5-Star Auto-Sniper Checklist")
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"### 🟢 CALL Sniper ({ce_safe}%)")
                    st.write(f"1. Breakout (Spot > SMA & VWAP): {'✅' if c_price else '❌'}")
                    st.write(f"2. Premium Momentum (CE > PE): {'✅' if c_mom else '❌'} *(₹{ce_ltp})*")
                    st.write(f"3. Call Buyers Aggressive (CE OI > PE OI): {check_icon(c_oi)}")
                    st.write(f"4. Call Volume High (CE Vol > PE Vol): {check_icon(c_vol)}")
                    st.write(f"5. Global Sentiment Bullish (PCR <= 1.0): {check_icon(c_pcr)}")
                with col_b:
                    st.markdown(f"### 🔴 PUT Sniper ({pe_safe}%)")
                    st.write(f"1. Breakdown (Spot < SMA & VWAP): {'✅' if p_price else '❌'}")
                    st.write(f"2. Premium Momentum (PE > CE): {'✅' if p_mom else '❌'} *(₹{pe_ltp})*")
                    st.write(f"3. Put Buyers Aggressive (PE OI > CE OI): {check_icon(p_oi)}")
                    st.write(f"4. Put Volume High (PE Vol > CE Vol): {check_icon(p_vol)}")
                    st.write(f"5. Global Sentiment Bearish (PCR >= 1.0): {check_icon(p_pcr)}")

                st.divider()

                # 7. AUTO-TRADE ENTRY
                if st.session_state.active_trade is None:
                    if auto_trade and valid and vix_ok and is_good_time:
                        st.info("🤖 Scanning for 80% Confirmed Setup...")
                        curr_time = datetime.now().strftime("%H:%M:%S")

                        if ce_safe >= 80.0 and c_price and ce_tok:
                            try:
                                order_params = {"variety": "NORMAL", "tradingsymbol": ce_row['symbol'], "symboltoken": ce_tok, "transactiontype": "BUY", "exchange": "NFO", "ordertype": "MARKET", "producttype": "INTRADAY", "duration": "DAY", "quantity": str(qty)}
                                obj.placeOrder(order_params)
                                # 💡 V56: Execution uses Spot + Dynamic Target/SL
                                st.session_state.active_trade = {"type": "CE", "symbol": ce_row['symbol'], "entry": float(spot), "target": float(spot + dynamic_tgt), "sl": float(spot - dynamic_sl), "time": curr_time}
                                st.success("🤖 BOUGHT CALL!")
                            except Exception as e: st.error(f"Order Failed: {e}")

                        elif pe_safe >= 80.0 and p_price and pe_tok:
                            try:
                                order_params = {"variety": "NORMAL", "tradingsymbol": pe_row['symbol'], "symboltoken": pe_tok, "transactiontype": "BUY", "exchange": "NFO", "ordertype": "MARKET", "producttype": "INTRADAY", "duration": "DAY", "quantity": str(qty)}
                                obj.placeOrder(order_params)
                                # 💡 V56: Execution uses Spot +/- Dynamic Target/SL
                                st.session_state.active_trade = {"type": "PE", "symbol": pe_row['symbol'], "entry": float(spot), "target": float(spot - dynamic_tgt), "sl": float(spot + dynamic_sl), "time": curr_time}
                                st.success("🤖 BOUGHT PUT!")
                            except Exception as e: st.error(f"Order Failed: {e}")
                    else:
                        if not vix_ok and valid: st.warning(f"⚠️ Auto-Trade BLOCKED: VIX ({live_vix}) is below minimum requirement ({min_vix}).")
                        elif not is_good_time and valid: st.warning(f"⚠️ Auto-Trade BLOCKED: Currently in Dead Time Zone. Waiting for momentum hours.")
                        else: st.warning("⚠️ Waiting for Data Validation or Auto-Trade is OFF.")
                else:
                    t = st.session_state.active_trade
                    pnl_spot = round(spot - t['entry'] if t['type'] == "CE" else t['entry'] - spot, 2)
                    st.info(f"🚀 **ACTIVE {t['type']} TRADE** ({t['symbol']})")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Live Index (Spot)", f"₹{spot}")
                    col2.metric("Spot Entry", f"₹{t['entry']}")
                    col3.metric("Dynamic Target", f"₹{t['target']}")
                    col4.metric("Dynamic StopLoss", f"₹{t['sl']}")
                    st.metric(label="Live P&L (Index Points)", value=f"{pnl_spot} Pts", delta=pnl_spot)
                    
                    if st.button("🚨 MANUAL EXIT NOW", use_container_width=True):
                        trade_record = {"Time": datetime.now().strftime("%H:%M:%S"), "Symbol": t['symbol'], "Type": t['type'], "Entry": t['entry'], "Exit": round(spot, 2), "P&L": pnl_spot, "Status": "⚠️ Manual Exit"}
                        st.session_state.trade_history.append(trade_record)
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
        if st.session_state.trade_history:
            st.dataframe(pd.DataFrame(st.session_state.trade_history), use_container_width=True)
else:
    st.info("Enter MPIN and Connect.")
