import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Indian Stock Dashboard", layout="wide")
st.title("Indian Stock Dashboard")
st.caption("Analyst consensus signals for research only. Not financial advice.")

DEFAULT_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS",
    "ICICIBANK.NS", "ITC.NS", "LT.NS", "SBIN.NS",
]

# ---------- Sidebar ----------
st.sidebar.header("Settings")
ticker_input = st.sidebar.text_area(
    "Tickers (comma separated, use .NS for NSE or .BO for BSE)",
    value=", ".join(DEFAULT_TICKERS),
)
tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

buy_cutoff = st.sidebar.slider("BUY if mean rating at or below", 1.0, 3.0, 2.0, 0.1)
sell_cutoff = st.sidebar.slider("SELL if mean rating above", 2.0, 5.0, 3.0, 0.1)
min_analysts = st.sidebar.number_input("Minimum analysts for a signal", 1, 20, 3)


# ---------- Data layer ----------
@st.cache_data(ttl=900)
def fetch_stock(ticker):
    t = yf.Ticker(ticker)
    info = t.info
    return {
        "Ticker": ticker,
        "Name": info.get("shortName", ticker),
        "Price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "Target": info.get("targetMeanPrice"),
        "Rating": info.get("recommendationMean"),
        "Analysts": info.get("numberOfAnalystOpinions"),
    }


@st.cache_data(ttl=900)
def fetch_history(ticker, period):
    return yf.Ticker(ticker).history(period=period)


# ---------- Analysis layer ----------
def get_signal(rating, analysts):
    if rating is None or analysts is None or analysts < min_analysts:
        return "LOW COVERAGE"
    if rating <= buy_cutoff:
        return "BUY"
    if rating > sell_cutoff:
        return "SELL"
    return "HOLD"


rows = []
for tk in tickers:
    try:
        rows.append(fetch_stock(tk))
    except Exception as e:
        st.warning(f"Could not load {tk}: {e}")

df = pd.DataFrame(rows)

if df.empty:
    st.error("No data loaded. Check your tickers.")
    st.stop()

df["Signal"] = df.apply(lambda r: get_signal(r["Rating"], r["Analysts"]), axis=1)
df["Upside %"] = ((df["Target"] / df["Price"] - 1) * 100).round(1)


# ---------- Display layer ----------
def colour(val):
    colours = {
        "BUY": "background-color: #1b7f3b; color: white",
        "SELL": "background-color: #b3261e; color: white",
        "HOLD": "background-color: #b58900; color: white",
    }
    return colours.get(val, "background-color: #555; color: white")


c1, c2, c3 = st.columns(3)
c1.metric("BUY signals", int((df["Signal"] == "BUY").sum()))
c2.metric("HOLD signals", int((df["Signal"] == "HOLD").sum()))
c3.metric("SELL signals", int((df["Signal"] == "SELL").sum()))

st.subheader("Consensus overview")
show = df[["Name", "Ticker", "Price", "Target", "Upside %", "Rating", "Analysts", "Signal"]]
st.dataframe(show.style.map(colour, subset=["Signal"]), use_container_width=True)

st.subheader("Price chart")
col_a, col_b = st.columns([1, 3])
choice = col_a.selectbox("Stock", df["Ticker"])
period = col_a.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "5y"], index=3)

hist = fetch_history(choice, period)
fig = go.Figure(go.Candlestick(
    x=hist.index, open=hist["Open"], high=hist["High"],
    low=hist["Low"], close=hist["Close"],
))
fig.update_layout(xaxis_rangeslider_visible=False, height=450)
col_b.plotly_chart(fig, use_container_width=True)
