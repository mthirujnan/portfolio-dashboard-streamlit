# ============================================================
# File: src/portfolio.py
# Purpose: Takes your raw holdings and live prices and
#          calculates all the numbers shown on the dashboard:
#          current values, profit/loss, allocation percentages.
#
# This file contains no fetching and no file reading —
# it only does maths. That separation keeps it easy to test
# and understand.
# ============================================================

FALLBACK_GOLD_PRICES = {'24k': 205.00, '22k': 187.00}
FALLBACK_USD_SGD     = 1.35


def calculate_portfolio(holdings, prices):
    """
    The main calculation function. Takes all holdings and live prices,
    returns a fully computed portfolio summary ready to display.

    Input:
        holdings — dict from data_store.load_holdings()
        prices   — dict from fetch_prices.fetch_all_prices()

    Returns: a dict with keys:
        gold, stocks, endowus, hsbc, sc, property, jewellery,
        summary (totals + allocation), fetched_at
    """
    gold_prices = prices.get('gold_prices', FALLBACK_GOLD_PRICES)
    stock_prices = prices.get('stocks', {})
    usd_sgd      = prices.get('_usd_sgd', FALLBACK_USD_SGD)

    gold      = _calc_gold(holdings['gold'], gold_prices)
    stocks    = _calc_stocks(holdings['stocks'], stock_prices, usd_sgd)
    endowus   = _calc_endowus(holdings['endowus'])
    hsbc      = _calc_hsbc(holdings['hsbc'])
    sc        = _calc_sc(holdings['sc'])
    prop      = _calc_property(holdings['property'])
    jewellery = _calc_jewellery(holdings.get('jewellery', {}), gold_prices)

    # Roll everything up into a grand total
    summary = _calc_summary(gold, stocks, endowus, hsbc, sc, prop, jewellery)

    return {
        'gold':        gold,
        'stocks':      stocks,
        'endowus':     endowus,
        'hsbc':        hsbc,
        'sc':          sc,
        'property':    prop,
        'jewellery':   jewellery,
        'summary':     summary,
        'fetched_at':  prices.get('_fetched_at', '—'),
        'usd_sgd':     usd_sgd,
        'gold_prices': gold_prices,
    }


# ─────────────────────────────────────────────────────────────
# Individual asset class calculators
# ─────────────────────────────────────────────────────────────

def _calc_gold(gold_holdings, gold_prices):
    """
    Calculates current value and P&L for each gold purchase,
    then totals them up. Also calculates the DCA (average cost per gram).
    """
    rows = []
    total_grams    = 0.0
    total_invested = 0.0
    total_value    = 0.0

    for entry in gold_holdings:
        grams         = entry['grams']
        cost_per_gram = entry['cost_per_gram']
        purity        = entry.get('purity', '24k')

        total_cost    = grams * cost_per_gram
        live_price    = gold_prices.get(purity, gold_prices.get('24k', FALLBACK_GOLD_PRICES['24k']))
        current_value = grams * live_price
        pnl           = current_value - total_cost
        pnl_pct       = (pnl / total_cost * 100) if total_cost > 0 else 0.0

        rows.append({
            'date':                   entry['date'],
            'grams':                  grams,
            'purity':                 purity,
            'cost_per_gram':          cost_per_gram,
            'total_cost':             total_cost,
            'current_price_per_gram': live_price,
            'current_value':          current_value,
            'pnl':                    pnl,
            'pnl_pct':                pnl_pct,
        })

        total_grams    += grams
        total_invested += total_cost
        total_value    += current_value

    total_pnl     = total_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
    dca_cost      = total_invested / total_grams if total_grams > 0 else 0.0

    return {
        'rows':          rows,
        'total_grams':   total_grams,
        'total_invested': total_invested,
        'total_value':   total_value,
        'total_pnl':     total_pnl,
        'total_pnl_pct': total_pnl_pct,
        'dca_cost':      dca_cost,
        'price_source':  gold_prices.get('source', 'unknown'),
    }


def _calc_stocks(stock_holdings, stock_prices, usd_sgd):
    """
    Calculates current value and P&L for each stock holding.
    Converts USD-priced stocks to SGD using the live exchange rate.
    """
    rows = []
    total_invested = 0.0
    total_value    = 0.0

    for stock in stock_holdings:
        ticker         = stock['ticker']
        shares         = stock['shares']
        purchase_price = stock['purchase_price']
        currency       = stock['currency']

        # Convert purchase cost to SGD
        if currency == 'USD':
            purchase_cost_sgd = shares * purchase_price * usd_sgd
        else:
            purchase_cost_sgd = shares * purchase_price

        # Get current price (live or fallback)
        price_info        = stock_prices.get(ticker, {})
        current_price_sgd = price_info.get('price_sgd', purchase_cost_sgd / shares if shares else 0)
        current_value_sgd = shares * current_price_sgd
        pnl_sgd           = current_value_sgd - purchase_cost_sgd
        pnl_pct           = (pnl_sgd / purchase_cost_sgd * 100) if purchase_cost_sgd > 0 else 0.0

        rows.append({
            'ticker':              ticker,
            'name':                stock['name'],
            'market':              stock['market'],
            'date':                stock['date'],
            'shares':              shares,
            'purchase_price':      purchase_price,
            'currency':            currency,
            'purchase_cost_sgd':   purchase_cost_sgd,
            'current_price_local': price_info.get('price_local', purchase_price),
            'current_price_sgd':   current_price_sgd,
            'current_value_sgd':   current_value_sgd,
            'pnl_sgd':             pnl_sgd,
            'pnl_pct':             pnl_pct,
            'price_source':        price_info.get('source', 'unknown'),
        })

        total_invested += purchase_cost_sgd
        total_value    += current_value_sgd

    total_pnl     = total_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

    return {
        'rows':           rows,
        'total_invested': total_invested,
        'total_value':    total_value,
        'total_pnl':      total_pnl,
        'total_pnl_pct':  total_pnl_pct,
    }


def _calc_endowus(endowus_data):
    """Calculates Endowus portfolio totals from manually entered values."""
    total_invested = endowus_data.get('total_invested', 0.0)
    total_return   = endowus_data.get('total_return',   0.0)
    twr_pct        = endowus_data.get('twr_pct',        0.0)
    total_value    = total_invested + total_return
    pnl_pct        = (total_return / total_invested * 100) if total_invested > 0 else 0.0

    return {
        'total_invested': total_invested,
        'total_value':    total_value,
        'total_pnl':      total_return,
        'total_pnl_pct':  pnl_pct,
        'twr_pct':        twr_pct,
    }


def _calc_hsbc(hsbc_data):
    """Calculates HSBC RSP totals from manually entered values."""
    total_invested = hsbc_data.get('total_invested',      0.0)
    total_value    = hsbc_data.get('total_current_value', 0.0)
    pnl            = total_value - total_invested
    pnl_pct        = (pnl / total_invested * 100) if total_invested > 0 else 0.0

    return {
        'total_invested': total_invested,
        'total_value':    total_value,
        'total_pnl':      pnl,
        'total_pnl_pct':  pnl_pct,
    }


def _calc_sc(sc_accounts):
    """
    Calculates Standard Chartered savings totals.
    SC savings has no gain/loss — value = balance held.
    """
    rows        = []
    total_value = 0.0

    for account in sc_accounts:
        balance = account.get('balance', 0.0)
        rows.append({'account': account['account'], 'balance': balance})
        total_value += balance

    return {
        'rows':        rows,
        'total_value': total_value,
    }


def _calc_property(property_data):
    """
    Calculates property equity and unrealised gain.
    Equity = current market value minus outstanding loan.
    """
    purchase_price   = property_data.get('purchase_price',   0.0)
    outstanding_loan = property_data.get('outstanding_loan', 0.0)
    current_value    = property_data.get('current_value',    0.0)

    equity           = current_value - outstanding_loan
    unrealised_gain  = current_value - purchase_price
    gain_pct         = (unrealised_gain / purchase_price * 100) if purchase_price > 0 else 0.0

    return {
        'purchase_price':   purchase_price,
        'outstanding_loan': outstanding_loan,
        'current_value':    current_value,
        'equity':           equity,
        'unrealised_gain':  unrealised_gain,
        'gain_pct':         gain_pct,
    }


def _calc_jewellery(jewellery_data, gold_prices):
    """
    Calculates jewellery value using the live 22k gold price.
    P&L is only shown if a purchase cost_per_gram was provided.
    """
    grams         = jewellery_data.get('grams', 0.0)
    purity        = jewellery_data.get('purity', '22k')
    cost_per_gram = jewellery_data.get('cost_per_gram', 0.0)

    live_price    = gold_prices.get(purity, gold_prices.get('22k', 187.00))
    current_value = grams * live_price

    # Only calculate P&L if a purchase cost was entered
    if cost_per_gram > 0:
        total_cost = grams * cost_per_gram
        pnl        = current_value - total_cost
        pnl_pct    = (pnl / total_cost * 100) if total_cost > 0 else 0.0
    else:
        total_cost = None
        pnl        = None
        pnl_pct    = None

    return {
        'grams':         grams,
        'purity':        purity,
        'cost_per_gram': cost_per_gram,
        'live_price':    live_price,
        'current_value': current_value,
        'total_cost':    total_cost,
        'pnl':           pnl,
        'pnl_pct':       pnl_pct,
    }


def _calc_summary(gold, stocks, endowus, hsbc, sc, prop, jewellery):
    """
    Rolls all asset classes up into overall portfolio totals.
    Calculates allocation percentage for each asset class.

    For property: we use equity (current value minus loan) as the
    "investable value" rather than the full market price, because
    the loan portion is not your wealth yet.
    """
    # Map each asset class to its contribution to total investable wealth
    asset_values = {
        'Gold':      gold['total_value'],
        'Stocks':    stocks['total_value'],
        'Endowus':   endowus['total_value'],
        'HSBC RSP':  hsbc['total_value'],
        'SC Savings': sc['total_value'],
        'Property':  prop['equity'],        # equity only, not full market value
        'Jewellery': jewellery['current_value'],
    }

    total_value = sum(asset_values.values())

    # Invested amounts (where applicable)
    total_invested = (
        gold['total_invested']
        + stocks['total_invested']
        + endowus['total_invested']
        + hsbc['total_invested']
        # SC and Property don't have a simple "invested" figure in the same way
    )

    # Allocation % for each asset class
    allocation = {
        name: (value / total_value * 100) if total_value > 0 else 0.0
        for name, value in asset_values.items()
    }

    return {
        'asset_values':  asset_values,
        'total_value':   total_value,
        'total_invested': total_invested,
        'allocation':    allocation,
    }
