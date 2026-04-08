# ============================================================
# File: src/data_store.py
# Purpose: Reads and writes all portfolio holdings to/from
#          Google Sheets. This replaces the local holdings.json
#          approach so the data lives in the cloud and is
#          accessible from any device, anywhere.
#
# Google Sheet structure (5 worksheets):
#   gold        — one row per gold purchase
#   stocks      — one row per stock holding
#   ticker_map  — maps your ticker labels to Yahoo Finance symbols
#   manual      — key/value pairs for Endowus, HSBC, Property, Jewellery
#   sc_accounts — one row per Standard Chartered account
#
# Credentials are stored in Streamlit secrets (never in code).
# ============================================================

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# The Google Sheets API scope we need: read and write spreadsheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Fallback values used if a live fetch fails
FALLBACK_GOLD_PRICES = {'24k': 205.00, '22k': 187.00}
FALLBACK_USD_SGD     = 1.35


# ─────────────────────────────────────────────────────────────
# Connection helper
# ─────────────────────────────────────────────────────────────

@st.cache_resource
def _get_spreadsheet():
    """
    Connects to Google Sheets using the service account credentials
    stored in Streamlit secrets, and returns the spreadsheet object.

    @st.cache_resource means this connection is created once and
    reused — we don't reconnect on every page load.
    """
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    client      = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(st.secrets["sheets"]["spreadsheet_id"])
    return spreadsheet


# ─────────────────────────────────────────────────────────────
# LOAD — read everything from Google Sheets
# ─────────────────────────────────────────────────────────────

def load_holdings():
    """
    Reads all portfolio data from Google Sheets and returns it
    as a dictionary — the same structure the rest of the app expects.

    Returns a dict with keys:
        gold, stocks, ticker_map, endowus, hsbc, sc, property, jewellery
    """
    spreadsheet = _get_spreadsheet()

    gold       = _read_gold(spreadsheet)
    stocks     = _read_stocks(spreadsheet)
    ticker_map = _read_ticker_map(spreadsheet)
    manual     = _read_manual(spreadsheet)
    sc         = _read_sc_accounts(spreadsheet)

    return {
        'gold':       gold,
        'stocks':     stocks,
        'ticker_map': ticker_map,
        'endowus':    manual['endowus'],
        'hsbc':       manual['hsbc'],
        'sc':         sc,
        'property':   manual['property'],
        'jewellery':  manual['jewellery'],
    }


def _read_gold(spreadsheet):
    """Reads the 'gold' worksheet. Returns a list of gold purchase dicts."""
    ws      = spreadsheet.worksheet("gold")
    records = ws.get_all_records()   # header row becomes dict keys automatically

    result = []
    for row in records:
        if not row.get('date'):
            continue
        raw_purity = str(row.get('purity', '24k')).strip()
        result.append({
            'date':          str(row['date']),
            'grams':         float(row['grams']),
            'cost_per_gram': float(row['cost_per_gram']),
            'purity':        '22k' if '22' in raw_purity else '24k',
        })
    return result


def _read_stocks(spreadsheet):
    """Reads the 'stocks' worksheet. Returns a list of stock holding dicts."""
    ws      = spreadsheet.worksheet("stocks")
    records = ws.get_all_records()

    result = []
    for row in records:
        if not row.get('ticker'):
            continue
        result.append({
            'ticker':         str(row['ticker']).upper(),
            'name':           str(row['name']),
            'market':         str(row['market']),
            'date':           str(row['date']),
            'shares':         int(row['shares']),
            'purchase_price': float(row['purchase_price']),
            'currency':       str(row['currency']),
        })
    return result


def _read_ticker_map(spreadsheet):
    """
    Reads the 'ticker_map' worksheet.
    Returns a dict like: {'VOO': {'yf': 'VOO', 'currency': 'USD'}, ...}
    """
    ws      = spreadsheet.worksheet("ticker_map")
    records = ws.get_all_records()

    result = {}
    for row in records:
        if not row.get('ticker'):
            continue
        result[str(row['ticker']).upper()] = {
            'yf':       str(row['yf_symbol']),
            'currency': str(row['currency']),
        }
    return result


def _read_manual(spreadsheet):
    """
    Reads the 'manual' worksheet (key/value pairs) and returns
    a dict containing endowus, hsbc, property, and jewellery sections.
    """
    ws      = spreadsheet.worksheet("manual")
    records = ws.get_all_records()

    # Build a flat key→value lookup from the sheet
    kv = {str(row['key']): row['value'] for row in records if row.get('key')}

    def get_float(key, default=0.0):
        try:
            return float(kv.get(key, default))
        except (ValueError, TypeError):
            return default

    def get_str(key, default=''):
        return str(kv.get(key, default))

    return {
        'endowus': {
            'total_invested': get_float('endowus_total_invested'),
            'total_return':   get_float('endowus_total_return'),
            'twr_pct':        get_float('endowus_twr_pct'),
        },
        'hsbc': {
            'total_invested':      get_float('hsbc_total_invested'),
            'total_current_value': get_float('hsbc_total_current_value'),
        },
        'property': {
            'purchase_price':   get_float('property_purchase_price'),
            'outstanding_loan': get_float('property_outstanding_loan'),
            'current_value':    get_float('property_current_value'),
        },
        'jewellery': {
            'grams':         get_float('jewellery_grams'),
            'purity':        get_str('jewellery_purity', '22k'),
            'cost_per_gram': get_float('jewellery_cost_per_gram'),
        },
    }


def _read_sc_accounts(spreadsheet):
    """Reads the 'sc_accounts' worksheet. Returns a list of account dicts."""
    ws      = spreadsheet.worksheet("sc_accounts")
    records = ws.get_all_records()

    result = []
    for row in records:
        if not row.get('account'):
            continue
        result.append({
            'account': str(row['account']),
            'balance': float(row['balance']),
        })
    return result


# ─────────────────────────────────────────────────────────────
# SAVE — write back to Google Sheets
# ─────────────────────────────────────────────────────────────

def update_manual_holdings(endowus=None, hsbc=None, sc=None, property_data=None, jewellery=None):
    """
    Updates the manually-entered sections of the Google Sheet.
    Only the arguments you pass are updated; the rest stay unchanged.

    After saving, clears the Streamlit cache so the dashboard
    immediately reflects the new values on next load.
    """
    spreadsheet = _get_spreadsheet()

    if endowus is not None or hsbc is not None or property_data is not None or jewellery is not None:
        _update_manual_sheet(spreadsheet, endowus, hsbc, property_data, jewellery)

    if sc is not None:
        _update_sc_sheet(spreadsheet, sc)

    # Reset the spreadsheet connection cache so fresh data is loaded
    _get_spreadsheet.clear()


def _update_manual_sheet(spreadsheet, endowus, hsbc, property_data, jewellery):
    """
    Rewrites the 'manual' worksheet completely.
    We always read the current values first, apply our changes,
    then write the whole sheet back — so nothing is lost.
    """
    # Read what's already there
    existing = _read_manual(spreadsheet)

    # Apply updates for whichever sections were passed in
    if endowus is not None:
        existing['endowus'] = endowus
    if hsbc is not None:
        existing['hsbc'] = hsbc
    if property_data is not None:
        existing['property'] = property_data
    if jewellery is not None:
        existing['jewellery'] = jewellery

    e = existing['endowus']
    h = existing['hsbc']
    p = existing['property']
    j = existing['jewellery']

    # Build the full list of rows to write
    rows = [
        ['key',                          'value'],
        ['endowus_total_invested',        e['total_invested']],
        ['endowus_total_return',          e['total_return']],
        ['endowus_twr_pct',               e['twr_pct']],
        ['hsbc_total_invested',           h['total_invested']],
        ['hsbc_total_current_value',      h['total_current_value']],
        ['property_purchase_price',       p['purchase_price']],
        ['property_outstanding_loan',     p['outstanding_loan']],
        ['property_current_value',        p['current_value']],
        ['jewellery_grams',               j['grams']],
        ['jewellery_purity',              j['purity']],
        ['jewellery_cost_per_gram',       j['cost_per_gram']],
    ]

    ws = spreadsheet.worksheet("manual")
    ws.clear()
    ws.update('A1', rows)


def _update_sc_sheet(spreadsheet, sc_accounts):
    """Rewrites the 'sc_accounts' worksheet with the updated balances."""
    rows = [['account', 'balance']]
    for account in sc_accounts:
        rows.append([account['account'], account['balance']])

    ws = spreadsheet.worksheet("sc_accounts")
    ws.clear()
    ws.update('A1', rows)


def add_stock_purchase(ticker, name, market, date, shares, purchase_price, currency, yf_symbol):
    """
    Appends a new stock row to the 'stocks' worksheet and adds
    the ticker to the 'ticker_map' worksheet.
    """
    spreadsheet = _get_spreadsheet()

    # Add to stocks sheet
    stocks_ws = spreadsheet.worksheet("stocks")
    stocks_ws.append_row([
        ticker.upper(), name, market, date,
        int(shares), float(purchase_price), currency
    ])

    # Add to ticker_map sheet
    tm_ws = spreadsheet.worksheet("ticker_map")
    tm_ws.append_row([ticker.upper(), yf_symbol, currency])

    _get_spreadsheet.clear()


def add_gold_purchase(date, grams, cost_per_gram, purity):
    """Appends a new gold purchase row to the 'gold' worksheet."""
    spreadsheet = _get_spreadsheet()

    ws = spreadsheet.worksheet("gold")
    ws.append_row([date, float(grams), float(cost_per_gram), purity])

    _get_spreadsheet.clear()
