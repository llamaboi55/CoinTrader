import requests
import pandas as pd
import streamlit as st
from streamlit_image_select import image_select

@st.cache_data
def get_coin_list():
    resp = requests.get('https://api.coingecko.com/api/v3/coins/list')
    resp.raise_for_status()
    return resp.json()

@st.cache_data
def get_coin_data(coin_id):
    resp = requests.get(f'https://api.coingecko.com/api/v3/coins/{coin_id}')
    resp.raise_for_status()
    data = resp.json()
    return {
        'id': coin_id,
        'name': data['name'],
        'symbol': data['symbol'],
        'image': data['image'].get('thumb') or data['image'].get('large')
    }

@st.cache_data
def get_market_chart(coin_id, days=5):
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

# Only show a limited number of results for performance
filtered = filtered[:20]

coin_infos = [get_coin_data(c['id']) for c in filtered]

if coin_infos:
    idx = image_select(
        label='Select a coin',
        images=[c['image'] for c in coin_infos],
        captions=[f"{c['name']} ({c['id']})" for c in coin_infos],
        return_value='index'
    )
    coin = coin_infos[idx]
    st.image(coin['image'], width=64)
    df = get_market_chart(coin['id'])
    st.write(f"Price data for {coin['name']} (USD)")
else:
    st.write('No matching coins found.')
    st.line_chart(data=df.set_index('date')['price'])