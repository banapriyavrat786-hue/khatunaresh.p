import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time

# -- CONFIGURATION --
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Auto-Sniper V28", layout="wide")
st.title("🏹 MKPV Ultra Sniper V28 | PRO MAX")

# -- SESSION STATE --
for key in ['connected','obj','token_df','active_trade','trade_history','price_history','last_trade_time']:
    if key not in st.session_state:
        st.session_state[key] = [] if key=='price_history' else None

# INIT
if st.session_state.trade_history is None:
    st.session_state.trade_history = []
if st.session_state.last_trade_time is None:
    st.session_state.last_trade_time = 0

# TIME
def get_time():
    try:
        r = requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5)
        return r.json()['unixtime']
    except:
        return int(time.time())

# TOKENS
@st.cache_data(ttl=3600)
def load_tokens():
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    df = pd.DataFrame(requests.get(url).json())
    return df[df['exch_seg'] == 'NFO']

# SIDEBAR
st.sidebar.title("⚙️ Controls")
live_feed = st.sidebar.toggle("🟢 Live Feed", value=False)
auto_trade = st.sidebar.checkbox("🤖 Auto Trade", value=False)

index = st.sidebar.radio("Index", ["NIFTY","BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry","07APR26").upper()
lots = st.sidebar.number_input("Lots",1,10,1)

tgt = st.sidebar.number_input("Target",40)
sl = st.sidebar.number_input("Stoploss",20)

mpin = st.sidebar.text_input("MPIN", type="password")

# LOGIN
if st.sidebar.button("Connect"):
    otp = pyotp.TOTP(TOTP_SECRET).at(get_time())
    obj = SmartConnect(api_key=API_KEY)
    login = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
    if login.get('status'):
        st.session_state.connected = True
        st.session_state.obj = obj
        st.session_state.token_df = load_tokens()
        st.success("✅ Connected")

# MAIN
if st.session_state.connected:
    if live_feed:

        obj = st.session_state.obj
        df = st.session_state.token_df

        lot_size = 50 if index=="NIFTY" else 15
        qty = lot_size * lots

        name = "Nifty 50" if index=="NIFTY" else "Nifty Bank"
        token = "26000" if index=="NIFTY" else "26009"
        step = 50 if index=="NIFTY" else 100

        res = obj.ltpData("NSE", name, token)

        if res.get('status'):
            spot = float(res['data']['ltp'])

            # PRICE HISTORY
            ph = st.session_state.price_history
            ph.append(spot)
            if len(ph) > 15:
                ph.pop(0)

            sma = sum(ph)/len(ph)

            # SIDEWAYS FILTER
            if len(ph) > 5:
                rng = max(ph) - min(ph)
                if rng < 15:
                    st.warning("⚠️ Sideways Market → No Trade")
                    auto_trade = False

            atm = int(round(spot/step)*step)

            sym = f"{index}{expiry}{atm}"

            try:
                ce_row = df[df['symbol']==f"{sym}CE"].iloc[0]
                pe_row = df[df['symbol']==f"{sym}PE"].iloc[0]

                ce_tok = str(ce_row['token']).split('.')[0]
                pe_tok = str(pe_row['token']).split('.')[0]

                ce_ltp = float(obj.ltpData("NFO", ce_row['symbol'], ce_tok)['data']['ltp'])
                pe_ltp = float(obj.ltpData("NFO", pe_row['symbol'], pe_tok)['data']['ltp'])

                # OI + VOL
                ce_oi = pe_oi = ce_vol = pe_vol = 0

                try:
                    md = obj.getMarketData("FULL", {"NFO":[ce_tok,pe_tok]})
                    for item in md['data']['fetched']:
                        if item['symbolToken']==ce_tok:
                            ce_oi, ce_vol = item['opnInterest'], item['volume']
                        if item['symbolToken']==pe_tok:
                            pe_oi, pe_vol = item['opnInterest'], item['volume']
                except:
                    pass

                # SMART VOLUME
                avg_vol = (ce_vol + pe_vol)/2 if (ce_vol+pe_vol)>0 else 1

                # CHECKLIST
                c_price = spot > sma
                c_mom = ce_ltp > pe_ltp
                c_oi = ce_oi > pe_oi
                c_vol = ce_vol > avg_vol * 1.2

                p_price = spot < sma
                p_mom = pe_ltp > ce_ltp
                p_oi = pe_oi > ce_oi
                p_vol = pe_vol > avg_vol * 1.2

                ce_score = sum([c_price,c_mom,c_oi,c_vol])
                pe_score = sum([p_price,p_mom,p_oi,p_vol])

                ce_safe = (ce_score/4)*100
                pe_safe = (pe_score/4)*100

                # BREAKOUT
                breakout_up = spot > sma + 15
                breakout_down = spot < sma - 15

                # UI
                st.metric("Spot", spot)
                st.metric("SMA", round(sma,2))
                st.write(f"CE Safety: {ce_safe}% | PE Safety: {pe_safe}%")

                # COOLDOWN
                if time.time() - st.session_state.last_trade_time < 300:
                    auto_trade = False
                    st.warning("⏳ Cooldown Active")

                # ACTIVE TRADE
                if st.session_state.active_trade:
                    t = st.session_state.active_trade
                    pnl = spot - t['entry'] if t['type']=="CE" else t['entry'] - spot

                    st.info(f"🚀 Active Trade P&L: {pnl}")

                    # TRAILING SL
                    if t['type']=="CE":
                        if pnl > 20:
                            t['sl'] = max(t['sl'], t['entry'] + 10)
                    else:
                        if pnl > 20:
                            t['sl'] = min(t['sl'], t['entry'] - 10)

                    exit_trade = False

                    if t['type']=="CE" and (spot >= t['target'] or spot <= t['sl']):
                        exit_trade = True
                    if t['type']=="PE" and (spot <= t['target'] or spot >= t['sl']):
                        exit_trade = True

                    if exit_trade:
                        st.session_state.trade_history.append(pnl)
                        st.session_state.active_trade = None
                        st.session_state.last_trade_time = time.time()
                        st.success("✅ Trade Closed")

                else:
                    if auto_trade:
                        if ce_safe >= 75 and (c_price or breakout_up):
                            obj.placeOrder({
                                "variety":"NORMAL",
                                "tradingsymbol":ce_row['symbol'],
                                "symboltoken":ce_tok,
                                "transactiontype":"BUY",
                                "exchange":"NFO",
                                "ordertype":"MARKET",
                                "producttype":"INTRADAY",
                                "duration":"DAY",
                                "quantity":str(qty)
                            })
                            st.session_state.active_trade = {
                                "type":"CE",
                                "entry":spot,
                                "target":spot+tgt,
                                "sl":spot-sl
                            }

                        elif pe_safe >= 75 and (p_price or breakout_down):
                            obj.placeOrder({
                                "variety":"NORMAL",
                                "tradingsymbol":pe_row['symbol'],
                                "symboltoken":pe_tok,
                                "transactiontype":"BUY",
                                "exchange":"NFO",
                                "ordertype":"MARKET",
                                "producttype":"INTRADAY",
                                "duration":"DAY",
                                "quantity":str(qty)
                            })
                            st.session_state.active_trade = {
                                "type":"PE",
                                "entry":spot,
                                "target":spot-tgt,
                                "sl":spot+sl
                            }

            except Exception as e:
                st.error(f"Data Error: {e}")

        time.sleep(2)
        st.rerun()

    else:
        st.info("⏸️ Live Feed OFF")

else:
    st.info("Enter MPIN and Connect")
