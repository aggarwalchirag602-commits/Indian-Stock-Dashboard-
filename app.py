import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title='52-Week Low + Analyst Buy Screener', layout='wide')
st.title('Indian Stocks Near 52-Week Low with Analyst Buy Ratings')
st.caption('Screener for research only. Not financial advice.')

# Edit this list freely. Use .NS for NSE and .BO for BSE.
# Company tickers change over time, so check that each one loads.
DEFAULT_TICKERS = [
    'ADANIPORTS.NS', 'APOLLOHOSP.NS', 'ASIANPAINT.NS', 'AXISBANK.NS',
    'BAJAJ-AUTO.NS', 'BAJFINANCE.NS', 'BAJAJFINSV.NS', 'BHARTIARTL.NS',
    'CIPLA.NS', 'COALINDIA.NS', 'DRREDDY.NS', 'EICHERMOT.NS',
    'GRASIM.NS', 'HCLTECH.NS', 'HDFCBANK.NS', 'HDFCLIFE.NS',
    'HEROMOTOCO.NS', 'HINDALCO.NS', 'HINDUNILVR.NS', 'ICICIBANK.NS',
    'INDUSINDBK.NS', 'INFY.NS', 'ITC.NS', 'JSWSTEEL.NS',
    'KOTAKBANK.NS', 'LT.NS', 'M&M.NS', 'MARUTI.NS',
    'NESTLEIND.NS', 'NTPC.NS', 'ONGC.NS', 'POWERGRID.NS',
    'RELIANCE.NS', 'SBILIFE.NS', 'SBIN.NS', 'SUNPHARMA.NS',
    'TATACONSUMER.NS', 'TATASTEEL.NS', 'TCS.NS', 'TECHM.NS',
    'TITAN.NS', 'ULTRACEMCO.NS', 'WIPRO.NS',
]

# ---------- Sidebar ----------
st.sidebar.header('Settings')
ticker_input = st.sidebar.text_area(
    'Tickers (comma separated)', value=', '.join(DEFAULT_TICKERS), height=200
)
tickers = tuple(t.strip().upper() for t in ticker_input.split(',') if t.strip())

near_low_pct = st.sidebar.slider('Within this % of the 52-week low', 0, 30, 10)
buy_cutoff = st.sidebar.slider('Analyst BUY if mean rating at or below', 1.0, 3.0, 2.0, 0.1)
min_analysts = st.sidebar.number_input('Minimum analysts covering the stock', 1, 20, 3)
only_matches = st.sidebar.checkbox('Show only stocks that pass both filters', value=True)


# ---------- Data layer ----------
def fetch_stock(ticker):
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return None
    price = info.get('currentPrice') or info.get('regularMarketPrice')
    low = info.get('fiftyTwoWeekLow')
    high = info.get('fiftyTwoWeekHigh')
    if not price or not low:
        return None
    return {
        'Ticker': ticker,
        'Name': info.get('shortName', ticker),
        'Price': price,
        '52W Low': low,
        '52W High': high,
        'Target': info.get('targetMeanPrice'),
        'Rating': info.get('recommendationMean'),
        'Analysts': info.get('numberOfAnalystOpinions'),
    }


@st.cache_data(ttl=900, show_spinner='Loading prices and analyst ratings...')
def load_all(tickers):
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(fetch_stock, tickers))


@st.cache_data(ttl=900)
def fetch_history(ticker):
    return yf.Ticker(ticker).history(period='1y')


results = load_all(tickers)
rows = [r for r in results if r]
failed = [t for t, r in zip(tickers, results) if not r]

if failed:
    st.warning('No data found for: ' + ', '.join(failed))
if not rows:
    st.error('No data loaded. Check your tickers.')
    st.stop()

# ---------- Screening layer ----------
df = pd.DataFrame(rows)
df['Above 52W low %'] = ((df['Price'] / df['52W Low'] - 1) * 100).round(1)
df['Upside to target %'] = ((df['Target'] / df['Price'] - 1) * 100).round(1)

near_low = df['Above 52W low %'] <= near_low_pct
analyst_buy = (df['Rating'] <= buy_cutoff) & (df['Analysts'] >= min_analysts)


def get_status(is_near_low, is_buy):
    if is_near_low and is_buy:
        return 'MATCH'
    if is_near_low:
        return 'Near low only'
    if is_buy:
        return 'Analyst buy only'
    return 'No'


df['Status'] = [get_status(n, b) for n, b in zip(near_low, analyst_buy)]
order = {'MATCH': 0, 'Near low only': 1, 'Analyst buy only': 2, 'No': 3}
df['_order'] = df['Status'].map(order)
df = df.sort_values(['_order', 'Above 52W low %']).drop(columns='_order')

# ---------- Display layer ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric('Stocks scanned', len(df))
c2.metric('Near 52-week low', int(near_low.sum()))
c3.metric('Analyst Buy', int(analyst_buy.sum()))
c4.metric('Pass both', int((df['Status'] == 'MATCH').sum()))


def colour(val):
    colours = {
        'MATCH': 'background-color: #1b7f3b; color: white',
        'Near low only': 'background-color: #b58900; color: white',
        'Analyst buy only': 'background-color: #1f5f99; color: white',
    }
    return colours.get(val, 'background-color: #555; color: white')


view = df[df['Status'] == 'MATCH'] if only_matches else df
cols = ['Name', 'Ticker', 'Price', '52W Low', 'Above 52W low %', 'Target',
        'Upside to target %', 'Rating', 'Analysts', 'Status']

st.subheader('Screener results')
st.caption('Rating scale: 1 = strong buy, 3 = hold, 5 = strong sell.')
if view.empty:
    st.info('No stocks pass both filters right now. Try a wider distance from the '
            '52-week low or a looser analyst cutoff.')
else:
    st.dataframe(
        view[cols].style.map(colour, subset=['Status']),
        use_container_width=True, hide_index=True,
    )

st.subheader('Price vs 52-week low')
pick_from = view if not view.empty else df
choice = st.selectbox('Stock', pick_from['Ticker'])
row = df[df['Ticker'] == choice].iloc[0]
hist = fetch_history(choice)

fig = go.Figure(go.Scatter(x=hist.index, y=hist['Close'], mode='lines', name='Close'))
fig.add_hline(y=row['52W Low'], line_dash='dash', line_color='red',
              annotation_text='52-week low')
if pd.notna(row['Target']):
    fig.add_hline(y=row['Target'], line_dash='dot', line_color='green',
                  annotation_text='Analyst target')
fig.update_layout(height=450)
st.plotly_chart(fig, use_container_width=True)
