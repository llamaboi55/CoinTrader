import re
import time
import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import nltk
from nltk.tokenize import RegexpTokenizer

# Ensure NLTK regexp tokenizer is available
nltk.download('punkt')

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
TRENDING_URL      = "https://dexscreener.com/?rankBy=trendingScoreH6&order=desc&ads=1&boosted=1&profile=1"
HEADERS           = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0", "cache-control": "max-age=0", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"}
TOP_N             = 100
SEARCH_MAX        = 10

# Regular expressions for extracting fields from each <a> block
PAT_ANCHOR = r'<a class="ds-dex-table-row ds-dex-table-row-top" href="[^"]*".*?</a>'
RE_PAIR_ID      = re.compile(r'href="/[^/]+/([^"]+)"')
RE_RANK         = re.compile(r'<span class="ds-dex-table-row-badge-pair-no">#\s*?(\d+)</span>')
RE_CHAIN        = re.compile(r'<img class="ds-dex-table-row-chain-icon"[^>]*title="([^"]+)"')
RE_LOGO         = re.compile(r'<img class="ds-dex-table-row-token-icon-img"[^>]*src="([^"]+)"')
RE_BASE_SYMBOL  = re.compile(r'<span class="ds-dex-table-row-base-token-symbol">([^<]+)</span>')
RE_BASE_NAME    = re.compile(r'<span class="ds-dex-table-row-base-token-name-text">([^<]+)</span>')
RE_PRICE        = re.compile(r'<div class="ds-dex-table-row-col-price">\s*\$\s*([^<]+)</div>')
RE_PCT_H24      = re.compile(r'<div class="ds-dex-table-row-col-price-change-h24"><span[^>]*>([^<]+)</span></div>')

# ─── 1) SCRAPE TRENDING HTML USING NLTK REGEXP TOKENIZER ──────────────────────
@st.cache_data
def scrape_trending_nltk(max_results: int = TOP_N) -> pd.DataFrame:
    resp = requests.get(TRENDING_URL, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        return pd.DataFrame()
    html = resp.text

    tokenizer = RegexpTokenizer(PAT_ANCHOR, flags=re.DOTALL)
    anchors = tokenizer.tokenize(html)

    rows = []
    for idx, block in enumerate(anchors):
        if idx >= max_results:
            break

        pair_id_match = RE_PAIR_ID.search(block)
        pair_id = pair_id_match.group(1) if pair_id_match else None

        rank_match = RE_RANK.search(block)
        rank = rank_match.group(1) if rank_match else None

        chain_match = RE_CHAIN.search(block)
        chain = chain_match.group(1) if chain_match else None

        logo_match = RE_LOGO.search(block)
        logo = logo_match.group(1) if logo_match else None

        bsym_match = RE_BASE_SYMBOL.search(block)
        base_symbol = bsym_match.group(1) if bsym_match else None

        bname_match = RE_BASE_NAME.search(block)
        base_name = bname_match.group(1) if bname_match else None

        price_match = RE_PRICE.search(block)
        price_usd = price_match.group(1) if price_match else None

        pct24_match = RE_PCT_H24.search(block)
        pct_h24 = pct24_match.group(1) if pct24_match else None

        rows.append({
            "rank": rank,
            "chain": chain,
            "pair_id": pair_id,
            "token_logo": logo,
            "base_symbol": base_symbol,
            "base_name": base_name,
            "price_usd": price_usd,
            "pct_h24": pct_h24,
        })

    return pd.DataFrame(rows)

# ─── 2) SEARCH DEXSCREENER BY NAME/SYMBOL ───────────────────────────────────────
@st.cache_data
def fetch_search_results(query: str, max_results: int = SEARCH_MAX) -> list[dict]:
    resp = requests.get(SEARCH_API_URL, params={"q": query}, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    if resp.status_code != 200:
        return []
    hits = resp.json() or []
    return hits[:max_results]

# ─── 3) FETCH 5-DAY PRICE HISTORY FOR A PAIR ────────────────────────────────────
@st.cache_data
def fetch_pair_chart(chain: str, pair_id: str, retries: int = 3, delay: int = 2) -> pd.DataFrame:
    url = PAIR_API_URL.format(chain=chain, pair=pair_id)
    for _ in range(retries):
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code == 429:
            time.sleep(delay)
            continue
        if r.status_code != 200:
            return pd.DataFrame(columns=["date", "price"])
        history = r.json().get("pair", {}).get("priceHistory", [])
        if not history:
            return pd.DataFrame(columns=["date", "price"])
        df = pd.DataFrame(history, columns=["timestamp", "price"])
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df[["date", "price"]]
    return pd.DataFrame(columns=["date", "price"])


# ─── STREAMLIT APPLICATION ────────────────────────────────────────────────────
st.set_page_config(page_title="CoinTrader (DexScreener)", layout="centered")
st.title("CoinTrader (DexScreener Trending + Charts)")

# 1) Scrape trending pairs via NLTK
df_trending = scrape_trending_nltk(TOP_N)
mapping_trend = {}
for _, row in df_trending.iterrows():
    name   = row["base_name"]
    symbol = row["base_symbol"]
    chain  = row["chain"]
    pair   = row["pair_id"]
    label  = f"{name} ({symbol}) — {chain}"
    mapping_trend[label] = {
        "chain": chain,
        "pair_id": pair,
        "logo": row["token_logo"],
        "name": name,
        "symbol": symbol,
        "price_usd": row["price_usd"],
        "pct_h24": row["pct_h24"],
        "pct_7d": "N/A"
    }

st.subheader(f"🔥 Top {len(mapping_trend)} Trending Tokens")
chosen_trending = st.selectbox("Select from Trending:", [""] + list(mapping_trend.keys()))

selected = None
if chosen_trending:
    selected = mapping_trend[chosen_trending]
else:
    # 2) If not chosen, show search
    st.subheader("🔍 Search by Name or Symbol")
    q = st.text_input("Type to search…", "")
    if q:
        hits = fetch_search_results(q, SEARCH_MAX)
        mapping_search = {}
        for h in hits:
            base   = h.get("baseToken", {}) or {}
            name   = base.get("name", "Unknown")
            symbol = base.get("symbol", "").upper()
            chain  = h.get("chainId", "")
            pair   = h.get("pairAddress", "")
            label  = f"{name} ({symbol}) — {chain}"
            mapping_search[label] = {
                "chain": chain,
                "pair_id": pair,
                "logo": base.get("logoURI", ""),
                "name": name,
                "symbol": symbol,
                "price_usd": h.get("priceUsd", "N/A"),
                "pct_h24": h.get("priceChange24h") or h.get("priceChange") or "N/A",
                "pct_7d": h.get("priceChange7d", "N/A")
            }
        if mapping_search:
            chosen_search = st.selectbox("Select from Matches:", [""] + list(mapping_search.keys()))
            if chosen_search:
                selected = mapping_search[chosen_search]

if selected:
    chain    = selected["chain"]
    pair_id  = selected["pair_id"]
    name     = selected["name"]
    symbol   = selected["symbol"]
    logo     = selected["logo"]
    price_usd= selected["price_usd"]
    pct_h24  = selected["pct_h24"]
    pct_7d   = selected["pct_7d"]

    st.markdown("---")
    if logo:
        st.image(logo, width=48)
    st.markdown(f"### {name} ({symbol})")
    st.markdown(f"**Chain:** `{chain}`   |   **Pair ID:** `{pair_id}`")

    if price_usd not in (None, "N/A"):
        try:
            pval = float(price_usd)
            st.markdown(f"**Current Price (USD):**  ${pval:,.6f}")
        except:
            st.markdown(f"**Current Price (USD):**  {price_usd}")
    else:
        st.markdown("**Current Price (USD):**  N/A")

    if pct_h24 not in (None, "N/A"):
        try:
            c24 = float(str(pct_h24).replace("%", ""))
            st.markdown(f"**24 h % Change:**  `{c24:.2f}%`")
        except:
            st.markdown(f"**24 h % Change:**  {pct_h24}")
    else:
        st.markdown("**24 h % Change:**  N/A")

    if pct_7d not in (None, "N/A"):
        try:
            c7 = float(str(pct_7d).replace("%", ""))
            st.markdown(f"**7 d % Change:**  `{c7:.2f}%`")
        except:
            st.markdown(f"**7 d % Change:**  {pct_7d}")
    else:
        st.markdown("**7 d % Change:**  N/A")

    # 3) Plot 5-day price history
    df_chart = fetch_pair_chart(chain, pair_id)
    if not df_chart.empty:
        fig = go.Figure(
            go.Scatter(
                x=df_chart["date"],
                y=df_chart["price"],
                mode="lines+markers",
                line=dict(color="cyan", width=2),
                marker=dict(size=4),
                name=f"{symbol} Price",
            )
        )
        fig.update_layout(
            title=f"5-Day Price Chart: {name} ({symbol})",
            xaxis_title="Date",
            yaxis_title="Price (USD)",
            margin=dict(l=20, r=20, t=40, b=20),
            height=450,
            template="plotly_dark",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("Chart data unavailable.")
else:
    st.info("Choose a trending token or search above.")
