# ============================================================
# File: src/fetch_prices.py
# Purpose: Fetches live prices from two external sources:
#   1. Gold prices  → scraped from goodreturns.in (Singapore)
#   2. Stock prices → fetched from Yahoo Finance via yfinance
#   3. USD/SGD rate → fetched from Yahoo Finance
#
# If any fetch fails, a fallback price is used so the app
# never crashes. A clear message tells you which data is live
# and which is a fallback.
# ============================================================

import yfinance as yf
from datetime import datetime

# These fallback values are used if the internet is unavailable
# or a price fetch fails. Update occasionally to keep them accurate.
FALLBACK_USD_SGD     = 1.35
FALLBACK_GOLD_PRICES = {'24k': 205.00, '22k': 187.00}


def fetch_gold_prices():
    """
    Scrapes live 24k and 22k gold prices in SGD per gram from:
      https://www.goodreturns.in/gold-rates/singapore.html

    Uses curl_cffi to impersonate a Chrome browser (the site blocks
    plain Python requests). BeautifulSoup then parses the HTML.

    Returns: dict like {'24k': 204.90, '22k': 186.50, 'source': 'live'}
             or fallback values with 'source': 'fallback' if fetch fails.
    """
    try:
        from curl_cffi import requests as cffi_requests
        from bs4 import BeautifulSoup
    except ImportError:
        return {**FALLBACK_GOLD_PRICES, 'source': 'fallback (curl_cffi not installed)'}

    url = 'https://www.goodreturns.in/gold-rates/singapore.html'

    try:
        response = cffi_requests.get(url, impersonate='chrome120', timeout=10)

        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        soup     = BeautifulSoup(response.text, 'html.parser')
        sections = soup.find_all('section', class_='section-sec4')
        prices   = {}

        for section in sections:
            # Find the heading element that identifies purity and currency
            heading_el   = section.find(['h2', 'h3', 'h4', 'div', 'span'])
            heading_text = heading_el.get_text(strip=True) if heading_el else ''

            # Skip tables not priced in SGD
            if '(SGD)' not in heading_text:
                continue

            # Identify 24k or 22k from the heading text
            if '24' in heading_text:
                purity = '24k'
            elif '22' in heading_text:
                purity = '22k'
            else:
                continue  # skip 18k or other purities

            table = section.find('table')
            if not table:
                continue

            rows = table.find_all('tr')
            if len(rows) < 2:
                continue

            # Row 0 is the header. Row 1 is the 1-gram price row.
            cells = rows[1].find_all('td')
            if len(cells) < 2:
                continue

            price_text  = cells[1].get_text(strip=True)
            price_clean = price_text.replace('$', '').replace(',', '').strip()
            prices[purity] = float(price_clean)

        # Fill in any purity we didn't find with fallback values
        for purity, fallback_price in FALLBACK_GOLD_PRICES.items():
            if purity not in prices:
                prices[purity] = fallback_price

        prices['source'] = 'live'
        return prices

    except Exception as error:
        # If anything goes wrong, return safe fallback values
        return {**FALLBACK_GOLD_PRICES, 'source': f'fallback ({error})'}


def fetch_usd_sgd_rate():
    """
    Fetches the live USD to SGD exchange rate from Yahoo Finance.
    Used to convert US stock prices into SGD for the dashboard.

    Returns: float — e.g. 1.3450
             Falls back to FALLBACK_USD_SGD if the fetch fails.
    """
    try:
        ticker = yf.Ticker("USDSGD=X")
        rate   = ticker.fast_info['last_price']
        return float(rate)
    except Exception:
        return FALLBACK_USD_SGD


def fetch_stock_prices(stock_holdings, ticker_map):
    """
    Fetches the latest price for each stock in your portfolio
    using Yahoo Finance (via the yfinance library).

    Input:
        stock_holdings — list of stock dicts from holdings.json
        ticker_map     — dict mapping your ticker labels to Yahoo Finance symbols

    Returns: dict keyed by ticker label, e.g.:
        {
          'VOO': {'price_local': 512.30, 'price_sgd': 690.61,
                  'currency': 'USD', 'source': 'live'},
          ...
        }
    """
    usd_sgd = fetch_usd_sgd_rate()
    results = {'_usd_sgd': usd_sgd, '_fetched_at': datetime.now().strftime('%d %b %Y  %H:%M')}

    for stock in stock_holdings:
        ticker_label = stock['ticker']
        info         = ticker_map.get(ticker_label)

        if not info:
            # No Yahoo Finance symbol registered — use purchase price as fallback
            results[ticker_label] = _build_fallback(stock, usd_sgd, reason='not in ticker_map')
            continue

        yf_symbol    = info['yf']
        traded_ccy   = info['currency']

        try:
            yf_ticker   = yf.Ticker(yf_symbol)
            price_local = float(yf_ticker.fast_info['last_price'])

            # Convert to SGD if the stock trades in USD
            price_sgd = price_local if traded_ccy == 'SGD' else price_local * usd_sgd

            results[ticker_label] = {
                'price_local': price_local,
                'price_sgd':   price_sgd,
                'currency':    traded_ccy,
                'source':      'live',
            }

        except Exception as error:
            results[ticker_label] = _build_fallback(stock, usd_sgd, reason=str(error))

    return results


def _build_fallback(stock, usd_sgd, reason=''):
    """
    Helper: builds a fallback price entry using the stock's original
    purchase price when a live fetch fails or isn't possible.
    """
    purchase_price = stock['purchase_price']
    currency       = stock['currency']
    price_sgd      = purchase_price if currency == 'SGD' else purchase_price * usd_sgd

    return {
        'price_local': purchase_price,
        'price_sgd':   price_sgd,
        'currency':    currency,
        'source':      f'fallback ({reason})',
    }


def fetch_all_prices(holdings):
    """
    Convenience function: fetches gold prices and all stock prices
    in one call. Returns a single prices dict used by portfolio.py.

    Input:  holdings — the full holdings dict from data_store.load_holdings()
    Returns: dict with keys: gold_prices, stocks, _usd_sgd, _fetched_at
    """
    gold_prices  = fetch_gold_prices()
    stock_prices = fetch_stock_prices(holdings['stocks'], holdings.get('ticker_map', {}))

    return {
        'gold_prices': gold_prices,
        'stocks':      stock_prices,
        '_usd_sgd':    stock_prices.get('_usd_sgd', FALLBACK_USD_SGD),
        '_fetched_at': stock_prices.get('_fetched_at', '—'),
    }
