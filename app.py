import requests
import pandas as pd
import streamlit as st

@st.cache_data
def get_coin_list():
    resp = requests.get('https://api.coingecko.com/api/v3/coins/list')
    resp.raise_for_status()
    return resp.json()

@st.cache_data
def get_market_chart(coin_id, days=30):
    resp = requests.get(
        f'https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart',
        params={'vs_currency': 'usd', 'days': str(days)}
    )
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df[['date', 'price']]

st.title('CoinTrader')

coins = get_coin_list()

query = st.text_input('Search for a cryptocurrency')

if query:
    filtered = [c for c in coins if query.lower() in c['name'].lower() or query.lower() in c['symbol'].lower()]
else:
    filtered = coins

selected = st.selectbox(
    'Select a coin',
    filtered,
    format_func=lambda c: f"{c['name']} ({c['symbol'].upper()})"
)

if selected:
    df = get_market_chart(selected['id'])
    st.write(f"Price data for {selected['name']} (USD)")
    st.line_chart(data=df.set_index('date')['price'])
