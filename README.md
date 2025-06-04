# CoinTrader

This project provides a Streamlit application to visualize cryptocurrency prices using the [CoinGecko](https://www.coingecko.com/) API.

## Requirements

* Python 3.12+
* `pip` to install dependencies

## Setup

```bash
pip install streamlit requests pandas streamlit-image-select
```

## Running the app

```bash
streamlit run app.py
```

The app lets you search for a cryptocurrency by name or symbol and displays a 5-day USD price chart. Coin images and IDs appear in the selector so you can easily pick the desired coin.
