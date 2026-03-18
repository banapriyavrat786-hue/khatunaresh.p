import time, pandas as pd
import streamlit as st
from api_helper import ShoonyaApiPy

# --- PAGE SETUP ---
st.set_page_config(page_title="GRK SNIPER V3", layout="wide")
st.title("🏹 MKPV ULTRA SNIPER V3")

# --- CONFIG ---
USER, PWD, VC, KEY = "FN183822", "PSbana@321", "FN183822_U", "e6006270e8270b71a12afe278e927f19"

# --- SESSION STATE (Data Storage) ---
if 'api' not in st.session_state: st.session_state.api = ShoonyaApiPy()
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'locked_entry' not in st.session_state: st.session_state.locked_entry = 0
if 'entry_data' not in st.session_state: st.session_state.entry_data = {}
if 'stats' not in st.session_state: st.session_state.stats = {"Target": 0, "SL": 0}
if 'history' not in st.session_state: st.session_state.history = []

if not st.session_state.logged_in:
    # --- LOGIN UI ---
    st.subheader("🔑 Broker Login")
    idx_choice = st.radio("Select Index:", ["NIFTY", "BANKNIFTY"])
    totp = st.text_input("Enter Fresh TOTP:", type="password")
    if st.button("Start Bot 🚀"):
        ret = st.session_state.api.login(userid=USER, password=PWD, twoFA=totp, vendor_code=VC, api_secret=KEY, imei="abc1234")
        if ret and ret.get('stat') == 'Ok':
            st.session_state.logged_in = True
            st.session_state.token = "26000" if idx_choice == "NIFTY" else "26009"
            st.rerun()
else:
    placeholder = st.empty()
    while True:
        try:
            q = st.session_state.api.get_quotes(exchange="NSE", token=st.session_state.token)
            if q and 'lp' in q:
                lp = float(q['lp'])
                pc = float(q.get('c', lp))
                high, low = float(q.get('h', lp)), float(q.get('l', lp))
                vol = q.get('v', '0')
                oi = q.get('toi', '0')
                
                # --- CALCULATION ---
                pivot = round((high + low + pc) / 3, 2)
                r1, s1 = round((2*pivot)-low, 2), round((2*pivot)-high, 2)
                
                # Indicator Checks
                trend_ok = lp > pivot
                sent_ok = lp > pc
                safety = 100 if (trend_ok and sent_ok) or (not trend_ok and not sent_ok) else 50
                signal = "CALL BUY ✅" if trend_ok else "PUT BUY 🔥"
                color = "blue" if trend_ok else "red"

                with placeholder.container():
                    # 1. TOP STATS
                    cols = st.columns(4)
                    cols[0].metric("LTP", f"₹{lp}", delta=round(lp-pc, 2))
                    cols[1].metric("SAFETY", f"{safety}%")
                    cols[2].success(f"🎯 TARGETS: {st.session_state.stats['Target']}")
                    cols[3].error(f"🛑 SL HITS: {st.session_state.stats['SL']}")

                    # 2. SIGNAL & LEVELS
                    st.markdown(f"<div style='background-color:{color};padding:15px;border-radius:10px;text-align:center'><h1 style='color:white'>SIGNAL: {signal}</h1></div>", unsafe_allow_html=True)
                    st.write(f"📊 **Levels:** Support (S1): `{s1}` | Resistance (R1): `{r1}` | OI: `{oi}` | Vol: `{vol}`")

                    # 3. TRADE TRACKER
                    if st.session_state.locked_entry > 0:
                        is_call = st.session_state.entry_data['type'] == "CALL BUY ✅"
                        pnl = round(lp - st.session_state.locked_entry if is_call else st.session_state.locked_entry - lp, 2)
                        st.warning(f"🚀 ACTIVE TRADE | ENTRY: {st.session_state.locked_entry} | TYPE: {st.session_state.entry_data['type']}")
                        st.metric("LIVE P&L", f"{pnl} Pts", delta=pnl)
                        
                        if pnl >= 40 or pnl <= -20:
                            res = "🎯 Target" if pnl >= 40 else "🛑 SL"
                            if pnl >= 40: st.session_state.stats["Target"] += 1
                            else: st.session_state.stats["SL"] += 1
                            
                            # Add to History
                            st.session_state.history.append({
                                "Time": time.strftime("%H:%M:%S"),
                                "Type": st.session_state.entry_data['type'],
                                "Safety": f"{st.session_state.entry_data['safety']}%",
                                "Entry": st.session_state.locked_entry,
                                "Exit": lp,
                                "P&L": pnl,
                                "Result": res,
                                "Indicators": "Trend+Sent" if st.session_state.entry_data['safety'] == 100 else "Trend Only"
                            })
                            st.session_state.locked_entry = 0
                            if pnl >= 40: st.balloons()
                    else:
                        if st.button("Take Entry 🎯"):
                            st.session_state.locked_entry = lp
                            st.session_state.entry_data = {"type": signal, "safety": safety}

                    # 4. HISTORY TABLE
                    if st.session_state.history:
                        st.subheader("📜 Trade Log & Analysis")
                        st.table(pd.DataFrame(st.session_state.history))

            time.sleep(2)
        except: break
