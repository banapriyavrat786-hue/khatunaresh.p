import streamlit as st
from SmartApi import SmartConnect
import pyotp, pandas as pd, requests, time
from datetime import datetime

# CONFIG
FIXED_CLIENT_ID = "P51646259"
API_KEY = "MT72qa1q"
TOTP_SECRET = "W6SCERQJX4RSU6TXECROABI7TA"

st.set_page_config(page_title="GRK Auto-Sniper V39", layout="wide")
st.title("🏹 MKPV Ultra Sniper V39 | Data Fixed")

# SESSION STATE
for key in ['connected','obj','token_df','active_trade','trade_history','price_history','last_valid_data']:
    if key not in st.session_state:
        if key == 'price_history': st.session_state[key] = []
        elif key == 'trade_history': st.session_state[key] = []
        elif key == 'last_valid_data':
            st.session_state[key] = {'ce_oi':0,'pe_oi':0,'ce_vol':0,'pe_vol':0}
        else: st.session_state[key] = None

# TIME
def get_time():
    try:
        return requests.get("http://worldtimeapi.org/api/timezone/Asia/Kolkata", timeout=5).json()['unixtime']
    except:
        return int(time.time())

# TOKENS
@st.cache_data(ttl=3600)
def load_tokens():
    df = pd.DataFrame(requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json").json())
    return df[df['exch_seg']=="NFO"]

# SIDEBAR
st.sidebar.title("Controls")
live_feed = st.sidebar.checkbox("Live Feed")
auto_trade = st.sidebar.checkbox("Auto Trade")

index = st.sidebar.radio("Index", ["NIFTY","BANKNIFTY"])
expiry = st.sidebar.text_input("Expiry","07APR26").upper()
lots = st.sidebar.number_input("Lots",1,10,1)

tgt = st.sidebar.number_input("Target",40)
sl = st.sidebar.number_input("Stoploss",20)

mpin = st.sidebar.text_input("MPIN", type="password")

# LOGIN
if st.sidebar.button("Connect"):
    st.session_state.token_df = load_tokens()
    otp = pyotp.TOTP(TOTP_SECRET).at(get_time())
    obj = SmartConnect(api_key=API_KEY)
    login = obj.generateSession(FIXED_CLIENT_ID, mpin, otp)
    if login.get('status'):
        st.session_state.connected = True
        st.session_state.obj = obj
        st.success("Connected")

# MAIN
if st.session_state.connected and live_feed:

    obj = st.session_state.obj
    df = st.session_state.token_df

    step = 50 if index=="NIFTY" else 100
    lot_size = 50 if index=="NIFTY" else 15
    qty = lot_size * lots

    name = "Nifty 50" if index=="NIFTY" else "Nifty Bank"
    token = "26000" if index=="NIFTY" else "26009"

    res = obj.ltpData("NSE", name, token)

    if res.get('status'):
        spot = float(res['data']['ltp'])

        # PRICE HISTORY
        ph = st.session_state.price_history
        ph.append(spot)
        if len(ph)>10: ph.pop(0)

        sma = sum(ph)/len(ph)
        atm = int(round(spot/step)*step)

        prefix = f"{index}{expiry}{atm}"

        ce_row = df[df['symbol']==f"{prefix}CE"].iloc[0]
        pe_row = df[df['symbol']==f"{prefix}PE"].iloc[0]

        ce_tok = str(ce_row['token']).split('.')[0]
        pe_tok = str(pe_row['token']).split('.')[0]

        # DEFAULT MEMORY
        ce_oi = st.session_state.last_valid_data['ce_oi']
        pe_oi = st.session_state.last_valid_data['pe_oi']
        ce_vol = st.session_state.last_valid_data['ce_vol']
        pe_vol = st.session_state.last_valid_data['pe_vol']

        ce_ltp = pe_ltp = 0

        try:
            md = obj.getMarketData("FULL", {"NFO":[ce_tok,pe_tok]})

            if md and md.get('status'):
                for item in md['data']['fetched']:

                    tok = item['symbolToken']

                    fetched_oi = item.get('opnInterest',0)
                    fetched_vol = item.get('tradeVolume',0)
                    fetched_ltp = item.get('lastTradedPrice',0)

                    # CE
                    if tok == ce_tok:
                        if fetched_oi > 0:
                            ce_oi = fetched_oi
                            st.session_state.last_valid_data['ce_oi'] = fetched_oi
                        if fetched_vol > 0:
                            ce_vol = fetched_vol
                            st.session_state.last_valid_data['ce_vol'] = fetched_vol
                        ce_ltp = fetched_ltp

                    # PE
                    if tok == pe_tok:
                        if fetched_oi > 0:
                            pe_oi = fetched_oi
                            st.session_state.last_valid_data['pe_oi'] = fetched_oi
                        if fetched_vol > 0:
                            pe_vol = fetched_vol
                            st.session_state.last_valid_data['pe_vol'] = fetched_vol
                        pe_ltp = fetched_ltp

        except:
            pass

        # VALID DATA CHECK
        valid = (ce_oi>0 and pe_oi>0 and ce_vol>0 and pe_vol>0)

        # LOGIC
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

        ce_safe = sum([c_price,c_mom,c_oi,c_vol]) / 4 * 100
        pe_safe = sum([p_price,p_mom,p_oi,p_vol]) / 4 * 100

        # UI
        st.metric("Spot", spot)
        st.metric("SMA", round(sma,2))
        st.write(f"CE Safety: {ce_safe}% | PE Safety: {pe_safe}%")

        # TRADE
        if st.session_state.active_trade is None and auto_trade and valid:

            if ce_safe >= 75:
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

            elif pe_safe >= 75:
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

        # EXIT
        if st.session_state.active_trade:
            t = st.session_state.active_trade
            pnl = spot - t['entry'] if t['type']=="CE" else t['entry'] - spot

            st.info(f"P&L: {pnl}")

            if (t['type']=="CE" and (spot>=t['target'] or spot<=t['sl'])) or \
               (t['type']=="PE" and (spot<=t['target'] or spot>=t['sl'])):

                st.session_state.trade_history.append(pnl)
                st.session_state.active_trade = None
                st.success("Trade Closed")

        time.sleep(2)
        st.rerun()

else:
    st.info("Connect + Enable Live Feed")
