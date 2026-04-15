import streamlit as st
from SmartApi import SmartConnect
import pyotp
import pandas as pd
import requests
import time
from datetime import datetime

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Sniper V72 | Institutional", layout="wide")

# --- CSS STYLING ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #00ffcc; }
    .stProgress > div > div > div > div { background-color: #10b981; }
    /* Highlight the S/R rows */
    .stDataFrame tr.highlight { background-color: rgba(255, 215, 0, 0.2); }
    </style>
    """, unsafe_allow_html=True)

# -- SESSION STATE INITIALIZATION --
for key in ['connected', 'obj', 'token_df', 'active_trade', 'trade_history', 'price_history']:
    if key not in st.session_state:
        st.session_state[key] = [] if key in ['price_history', 'trade_history'] else None

def get_time():
    try: return requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5).json()['unixtime']
    except: return int(time.time())

# -- SIDEBAR CONTROLS --
st.sidebar.title("🚀 Sniper V72")
live_feed = st.sidebar.checkbox("🟢 LIVE FEED", value=True)
auto_trade = st.sidebar.checkbox("🤖 Enable Auto-Trade", value=False)

st.sidebar.divider()
index = st.sidebar.radio("Index", ["NIFTY", "BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry (e.g. 16APR26)", "16APR26").upper()
lots = st.sidebar.number_input("Lots", 1, 30, 1)

st.sidebar.subheader("🎯 Trade Setup")
tgt = st.sidebar.number_input("Target Pts", 40.0, step=5.0)
sl = st.sidebar.number_input("SL Pts", 20.0, step=5.0)
min_vix = st.sidebar.number_input("Min VIX", value=11.5)
mpin = st.sidebar.text_input("MPIN", type="password")

# --- SECURE LOGIN LOGIC ---
if st.sidebar.button("🔑 Connect Securely"):
    try:
        raw_data = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json", timeout=15).json()
        df_temp = pd.DataFrame(raw_data)
        st.session_state.token_df = df_temp[df_temp['exch_seg'] == "NFO"]
        
        otp = pyotp.TOTP(TOTP_SECRET.replace(" ", "")).at(get_time())
        obj = SmartConnect(api_key=API_KEY)
        login = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
        
        if login.get('status'):
            st.session_state.connected, st.session_state.obj = True, obj
            st.sidebar.success("✅ Connected & Ready!")
        else:
            st.sidebar.error("❌ Invalid Login Credentials")
    except Exception as e:
        st.sidebar.error(f"❌ Network/API Error: {e}")

# -- MAIN TRADING ENGINE --
if st.session_state.connected and live_feed:
    obj = st.session_state.obj
    df = st.session_state.token_df
    
    step = 50 if index == "NIFTY" else 100
    qty = (50 if index == "NIFTY" else 15) * lots

    try:
        # 1. SPOT & VIX FETCH
        idx_tok = "26000" if index == "NIFTY" else "26009"
        res = obj.ltpData("NSE", index, idx_tok)
        vix_res = obj.ltpData("NSE", "INDIA VIX", "26017")
        
        if res and res.get('status'):
            spot = float(res['data']['ltp'])
            vix = float(vix_res['data']['ltp']) if (vix_res and vix_res.get('status')) else 12.0
            atm = int(round(spot / step) * step)

            st.session_state.price_history.append(spot)
            if len(st.session_state.price_history) > 30: 
                st.session_state.price_history.pop(0)
                
            sma = sum(st.session_state.price_history) / len(st.session_state.price_history)
            price_trend = "Rising" if spot > sma else "Falling"

            # 2. TOKEN GENERATOR (SAFE LIMIT)
            tokens_to_fetch = []
            token_map = {}
            for i in range(-10, 11):
                for sfx in ["CE", "PE"]:
                    sym = f"{index}{expiry}{atm+(i*step)}{sfx}"
                    t_rows = df[df['symbol'] == sym]
                    if not t_rows.empty:
                        tk = str(t_rows.iloc[0]['token'])
                        tokens_to_fetch.append(tk)
                        token_map[tk] = {"type": sfx, "strike": atm+(i*step), "sym": sym}

            if len(tokens_to_fetch) == 0:
                st.error(f"⚠️ Expiry '{expiry}' Match Nahi Hui. Kripya Expiry Date Format Check Karein.")
                st.stop()

            # 3. GET FULL DEPTH (OPTION CHAIN)
            full_data = obj.getMarketData("FULL", {"NFO": tokens_to_fetch})
            master_list = []
            ce_oi = pe_oi = ce_bid = ce_ask = pe_bid = pe_ask = 0
            atm_ce_ltp = atm_pe_ltp = 0
            total_vol = 0 # Dummy for real volume if available

            if full_data and full_data.get('status') and 'fetched' in full_data.get('data', {}):
                for item in full_data['data']['fetched']:
                    m = token_map.get(item['symbolToken'])
                    if not m: continue
                    
                    b = float(item.get('totalBuyQty', 0))
                    a = float(item.get('totalSellQty', 0))
                    o = float(item.get('opnInterest', 0))
                    ltp = float(item.get('ltp', 0))
                    v = float(item.get('volume', item.get('tradeVolume', 0))) # Fallback for volume
                    total_vol += v
                    
                    if m['type'] == "CE": 
                        ce_oi += o; ce_bid += b; ce_ask += a
                        if m['strike'] == atm: atm_ce_ltp = ltp
                    else: 
                        pe_oi += o; pe_bid += b; pe_ask += a
                        if m['strike'] == atm: atm_pe_ltp = ltp
                        
                    master_list.append({"Strike": m['strike'], "Type": m['type'], "LTP": ltp, "Bids": b, "Asks": a, "OI": o, "Vol": v})

            df_m = pd.DataFrame(master_list)
            
            # --- CALCULATE INSTITUTIONAL S/R & OI TREND ---
            pcr = round(pe_oi/ce_oi, 2) if ce_oi > 0 else 1.0
            
            inst_resistance = 0
            inst_support = 0
            
            if not df_m.empty:
                # Max CE OI is Resistance
                ce_data = df_m[df_m['Type'] == 'CE']
                if not ce_data.empty: inst_resistance = ce_data.loc[ce_data['OI'].idxmax()]['Strike']
                
                # Max PE OI is Support
                pe_data = df_m[df_m['Type'] == 'PE']
                if not pe_data.empty: inst_support = pe_data.loc[pe_data['OI'].idxmax()]['Strike']

            # Basic OI Trend Logic (Needs historical OI to be perfect, using proxy here)
            # Assumption: High PCR + Price Rising = Bullish OI Trend
            oi_trend = "Bullish" if (pcr > 1.0 and price_trend == "Rising") else ("Bearish" if (pcr < 1.0 and price_trend == "Falling") else "Mixed")

            # Determine Overall Outlook
            market_outlook = "Sideways ⚖️"
            outlook_color = "normal"
            if pcr > 1.1 and spot > sma and pe_bid > (ce_ask * 1.2):
                market_outlook = "Bullish 🚀"
                outlook_color = "normal"
            elif pcr < 0.9 and spot < sma and ce_ask > (pe_bid * 1.2):
                market_outlook = "Bearish 🩸"
                outlook_color = "inverse"

            # --- UI: MARKET DASHBOARD ---
            st.title(f"🏹 {index} COMMAND CENTER V72")
            st.subheader(f"📊 Institutional Dashboard | Spot: ₹{spot}")
            
            # Big Overarching Label
            if market_outlook == "Bullish 🚀":
                st.success(f"**MARKET OUTLOOK:** {market_outlook}")
            elif market_outlook == "Bearish 🩸":
                st.error(f"**MARKET OUTLOOK:** {market_outlook}")
            else:
                st.warning(f"**MARKET OUTLOOK:** {market_outlook}")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("India VIX", vix, delta="Safe" if vix >= min_vix else "Low Vol", delta_color="normal" if vix >= min_vix else "inverse")
            c2.metric("Global PCR", pcr, delta="Bullish" if pcr > 1 else "Bearish")
            c3.metric("Trend (SMA 30)", round(sma, 2), delta=price_trend)
            c4.metric("ATM CE/PE LTP", f"{atm_ce_ltp} / {atm_pe_ltp}")

            st.divider()
            
            # --- UI: NEW S/R METRICS ---
            s1, s2 = st.columns(2)
            s1.metric("Institutional Support (Max PE OI)", inst_support, delta="Holding" if spot > inst_support else "Breached", delta_color="normal" if spot > inst_support else "inverse")
            s2.metric("Institutional Resistance (Max CE OI)", inst_resistance, delta="Holding" if spot < inst_resistance else "Breached", delta_color="inverse" if spot > inst_resistance else "normal")
            
            st.divider()

            # --- UI: BATTLEGROUND ---
            t1, t2 = st.columns(2)
            
            if not df_m.empty:
                with t1:
                    st.subheader("🔴 Resistance Zone (CE Asks)")
                    ce_df = df_m[(df_m['Type']=="CE") & (df_m['Strike'] >= atm - (step*2))].sort_values("Strike").head(10)
                    
                    # Highlight Resistance Logic (Streamlit styling trick)
                    def highlight_res(s):
                        return ['background-color: rgba(255, 99, 71, 0.3)' if v == inst_resistance else '' for v in s]
                    
                    st.dataframe(ce_df.style.apply(highlight_res, subset=['Strike']), hide_index=True, use_container_width=True)
                    
                with t2:
                    st.subheader("🟢 Support Zone (PE Bids)")
                    pe_df = df_m[(df_m['Type']=="PE") & (df_m['Strike'] <= atm + (step*2))].sort_values("Strike", ascending=False).head(10)
                    
                    # Highlight Support Logic
                    def highlight_sup(s):
                        return ['background-color: rgba(60, 179, 113, 0.3)' if v == inst_support else '' for v in s]

                    st.dataframe(pe_df.style.apply(highlight_sup, subset=['Strike']), hide_index=True, use_container_width=True)

            # --- UI: EXECUTION LOGIC (V72 Pro Logic) ---
            st.divider()
            st.subheader("📋 Detailed Market Strength Checklist (V72 Logic)")
            
            # Extended Institutional Logic
            chk_ce = {
                "Spot > SMA (Bull Trend)": spot > sma,
                "PCR > 1.0 (Put Writers Active)": pcr > 1.0,
                "Heavy Demand (Bids > Asks by 20%)": pe_bid > (ce_ask * 1.2),
                "CE Premium Expanding": atm_ce_ltp > atm_pe_ltp,
                "Support Holds (LTP > Inst. Support)": spot > inst_support,
                "Bullish OI Trend": oi_trend == "Bullish"
            }
            chk_pe = {
                "Spot < SMA (Bear Trend)": spot < sma,
                "PCR < 1.0 (Call Writers Active)": pcr < 1.0,
                "Heavy Supply (Asks > Bids by 20%)": ce_ask > (pe_bid * 1.2),
                "PE Premium Expanding": atm_pe_ltp > atm_ce_ltp,
                "Resistance Holds (LTP < Inst. Resistance)": spot < inst_resistance,
                "Bearish OI Trend": oi_trend == "Bearish"
            }

            st.caption(f"⚔️ **Live Battle:** Total Bids (PE Support): {int(pe_bid)}  |  Total Asks (CE Resistance): {int(ce_ask)}")

            l1, l2 = st.columns(2)
            with l1:
                for txt, val in chk_ce.items(): st.write(f"{'✅' if val else '❌'} {txt}")
                ce_score = sum(chk_ce.values())
                ce_conf = (ce_score / len(chk_ce)) * 100
                st.metric("CALL Confidence", f"{ce_conf}%")
                st.progress(ce_score/len(chk_ce))
            with l2:
                for txt, val in chk_pe.items(): st.write(f"{'✅' if val else '❌'} {txt}")
                pe_score = sum(chk_pe.values())
                pe_conf = (pe_score / len(chk_pe)) * 100
                st.metric("PUT Confidence", f"{pe_conf}%")
                st.progress(pe_score/len(chk_pe))

            # --- ACTIVE TRADE TRACKER (Highly Detailed) ---
            st.divider()
            st.subheader("⏱️ Active Trade Status")
            
            # --- AUTO TRADE ENGINE ---
            if st.session_state.active_trade is None:
                st.info("No active trades currently. Monitoring conditions...")
                if auto_trade and vix >= min_vix:
                    # Require 5-Star condition (e.g., >80% confidence)
                    if ce_conf > 80 and atm_ce_ltp > 0:
                        st.success("🚀 CRITERIA MET: AUTO-BUYING CALL")
                        st.session_state.active_trade = {
                            "type": "CE", "entry": spot, "target": spot+tgt, "sl": spot-sl, 
                            "time": datetime.now().strftime("%H:%M:%S"), "conf": ce_conf
                        }
                    elif pe_conf > 80 and atm_pe_ltp > 0:
                        st.error("🩸 CRITERIA MET: AUTO-BUYING PUT")
                        st.session_state.active_trade = {
                            "type": "PE", "entry": spot, "target": spot-tgt, "sl": spot+sl,
                            "time": datetime.now().strftime("%H:%M:%S"), "conf": pe_conf
                        }
            else:
                t = st.session_state.active_trade
                pnl = round(spot - t['entry'] if t['type']=="CE" else t['entry'] - spot, 2)
                
                # Detailed Active Trade Display
                st.warning(f"⚠️ **TRADE RUNNING**")
                tr1, tr2, tr3, tr4, tr5 = st.columns(5)
                tr1.metric("Type", t['type'])
                tr2.metric("Entry Time", t['time'])
                tr3.metric("Entry Spot", t['entry'])
                tr4.metric("Current Spot", f"₹{spot}")
                tr5.metric("Live P&L (Pts)", pnl, delta=pnl)
                
                st.write(f"**Safety/Confidence at Entry:** {t.get('conf', 0)}%")
                st.write(f"**Targets:** Exit expected around **₹{t['target']}** | Stoploss around **₹{t['sl']}**")
                
                is_tgt = spot >= t['target'] if t['type']=="CE" else spot <= t['target']
                is_sl = spot <= t['sl'] if t['type']=="CE" else spot >= t['sl']
                
                if is_tgt or is_sl:
                    res_status = "✅ TARGET HIT" if is_tgt else "❌ SL HIT"
                    st.session_state.trade_history.append({
                        "Time In": t['time'], "Time Out": datetime.now().strftime("%H:%M:%S"),
                        "Type": t['type'], "Entry": t['entry'], "Exit": spot, "PnL": pnl, "Result": res_status
                    })
                    st.session_state.active_trade = None
                    st.success(f"Trade Closed Automatically: {res_status}")
                    time.sleep(2)
                    st.rerun()

                if st.button("🚨 MANUAL EXIT NOW", use_container_width=True):
                    st.session_state.trade_history.append({
                        "Time In": t['time'], "Time Out": datetime.now().strftime("%H:%M:%S"),
                        "Type": t['type'], "Entry": t['entry'], "Exit": spot, "PnL": pnl, "Result": "Manual Exit"
                    })
                    st.session_state.active_trade = None
                    st.rerun()

            # --- LEDGER ---
            if st.session_state.trade_history:
                st.divider()
                st.subheader("📚 Detailed Trade Ledger")
                st.dataframe(pd.DataFrame(st.session_state.trade_history), use_container_width=True)

            time.sleep(2)
            st.rerun()

    except Exception as e:
        st.warning(f"⚠️ System Syncing... Loading Data ({e})")
        time.sleep(2)
        st.rerun()
else:
    if not st.session_state.connected:
        st.info("🔌 System Offline. Enter MPIN and Click Connect.")
