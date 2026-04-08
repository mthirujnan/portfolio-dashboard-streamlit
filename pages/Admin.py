# ============================================================
# File: pages/Admin.py
# Purpose: The Admin module. Lets you update all manually-entered
#          portfolio values and add new stock purchases.
#
# Streamlit automatically adds this as a second page in the
# app sidebar because it lives in the pages/ folder.
# ============================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import streamlit as st
import yfinance as yf
from datetime import date

from src.data_store import (
    load_holdings,
    update_manual_holdings,
    add_stock_purchase,
    add_gold_purchase,
)

st.set_page_config(
    page_title="Admin — Portfolio Dashboard",
    page_icon="⚙️",
    layout="wide",
)

st.title("⚙️ Admin — Update Holdings")
st.caption("Changes saved here are written immediately to holdings.json and reflected on the Dashboard after refresh.")

# Load current holdings so we can pre-fill the forms with existing values
try:
    holdings = load_holdings()
except Exception as error:
    st.error(f"Could not load holdings: {error}")
    st.stop()

st.divider()

# ─────────────────────────────────────────────────────────────
# TAB LAYOUT
# We use tabs to separate the four admin areas cleanly.
# ─────────────────────────────────────────────────────────────
tab_manual, tab_add_stock, tab_add_gold, tab_manage_stocks = st.tabs([
    "📝 Update Manual Values",
    "➕ Add New Stock Purchase",
    "➕ Add New Gold Purchase",
    "📋 View All Holdings",
])


# ═════════════════════════════════════════════════════════════
# TAB 1: Update Manual Values
# ═════════════════════════════════════════════════════════════
with tab_manual:
    st.subheader("Update Manual Holdings")
    st.info("These values come from your Endowus app, HSBC app, bank statements, and property estimates. Update them whenever you check.")

    # ── Endowus ─────────────────────────────────────────────
    st.markdown("### 💼 Endowus")
    end = holdings['endowus']

    end_col1, end_col2, end_col3 = st.columns(3)
    with end_col1:
        end_invested = st.number_input(
            "Total Invested (SGD)",
            value=float(end['total_invested']),
            step=100.0,
            format="%.2f",
            key="end_invested",
            help="Total capital you have put into Endowus"
        )
    with end_col2:
        end_return = st.number_input(
            "Total Return (SGD)",
            value=float(end['total_return']),
            step=100.0,
            format="%.2f",
            key="end_return",
            help="Total profit earned so far, as shown in Endowus app"
        )
    with end_col3:
        end_twr = st.number_input(
            "Time-Weighted Return (%)",
            value=float(end['twr_pct']),
            step=0.01,
            format="%.2f",
            key="end_twr",
            help="TWR % shown in the Endowus app"
        )

    st.divider()

    # ── HSBC RSP ────────────────────────────────────────────
    st.markdown("### 🏦 HSBC RSP")
    hsbc = holdings['hsbc']

    hsbc_col1, hsbc_col2 = st.columns(2)
    with hsbc_col1:
        hsbc_invested = st.number_input(
            "Total Invested (SGD)",
            value=float(hsbc['total_invested']),
            step=100.0,
            format="%.2f",
            key="hsbc_invested",
            help="Total amount contributed to HSBC RSP to date"
        )
    with hsbc_col2:
        hsbc_value = st.number_input(
            "Current Portfolio Value (SGD)",
            value=float(hsbc['total_current_value']),
            step=100.0,
            format="%.2f",
            key="hsbc_value",
            help="Current value of your HSBC RSP portfolio"
        )

    st.divider()

    # ── SC Savings ──────────────────────────────────────────
    st.markdown("### 💰 Standard Chartered Savings")
    sc_accounts = holdings['sc']

    sc_updated = []
    sc_cols    = st.columns(len(sc_accounts)) if sc_accounts else []

    for idx, (col, account) in enumerate(zip(sc_cols, sc_accounts)):
        with col:
            new_balance = st.number_input(
                f"{account['account']} Balance (SGD)",
                value=float(account['balance']),
                step=100.0,
                format="%.2f",
                key=f"sc_{idx}",
            )
            sc_updated.append({'account': account['account'], 'balance': new_balance})

    st.divider()

    # ── Property ────────────────────────────────────────────
    st.markdown("### 🏠 Property")
    prop = holdings['property']

    prop_col1, prop_col2, prop_col3 = st.columns(3)
    with prop_col1:
        prop_purchase = st.number_input(
            "Purchase Price (SGD)",
            value=float(prop['purchase_price']),
            step=1000.0,
            format="%.2f",
            key="prop_purchase",
            help="Original price you paid for the property"
        )
    with prop_col2:
        prop_loan = st.number_input(
            "Outstanding Loan (SGD)",
            value=float(prop['outstanding_loan']),
            step=1000.0,
            format="%.2f",
            key="prop_loan",
            help="Remaining mortgage balance"
        )
    with prop_col3:
        prop_value = st.number_input(
            "Current Market Value (SGD)",
            value=float(prop['current_value']),
            step=1000.0,
            format="%.2f",
            key="prop_value",
            help="Estimated current market price of the property"
        )

    st.divider()

    # ── Jewellery ────────────────────────────────────────────
    st.markdown("### 💍 Jewellery")
    jwl = holdings['jewellery']

    jwl_col1, jwl_col2, jwl_col3 = st.columns(3)
    with jwl_col1:
        jwl_grams = st.number_input(
            "Total Weight (grams)",
            value=float(jwl['grams']),
            step=1.0,
            format="%.1f",
            key="jwl_grams",
        )
    with jwl_col2:
        jwl_purity = st.selectbox(
            "Purity",
            options=['22k', '24k'],
            index=0 if jwl['purity'] == '22k' else 1,
            key="jwl_purity",
        )
    with jwl_col3:
        jwl_cost = st.number_input(
            "Cost per Gram (SGD, enter 0 if unknown)",
            value=float(jwl['cost_per_gram']),
            step=1.0,
            format="%.2f",
            key="jwl_cost",
            help="If unknown, enter 0 — P&L will not be shown"
        )

    st.divider()

    # ── Save button ─────────────────────────────────────────
    if st.button("💾 Save All Changes", type="primary", use_container_width=True):
        try:
            update_manual_holdings(
                endowus={
                    'total_invested': end_invested,
                    'total_return':   end_return,
                    'twr_pct':        end_twr,
                },
                hsbc={
                    'total_invested':      hsbc_invested,
                    'total_current_value': hsbc_value,
                },
                sc=sc_updated,
                property_data={
                    'purchase_price':   prop_purchase,
                    'outstanding_loan': prop_loan,
                    'current_value':    prop_value,
                },
                jewellery={
                    'grams':         jwl_grams,
                    'purity':        jwl_purity,
                    'cost_per_gram': jwl_cost,
                },
            )

            # Clear the dashboard cache so it picks up the new values
            st.cache_data.clear()

            st.success("✅ All changes saved! The dashboard will now show your updated values.")
            st.balloons()

        except Exception as error:
            st.error(f"Could not save changes: {error}")


# ═════════════════════════════════════════════════════════════
# TAB 2: Add New Stock Purchase
# ═════════════════════════════════════════════════════════════
with tab_add_stock:
    st.subheader("Add a New Stock Purchase")
    st.info("Fill in the details of your new stock purchase. The app will look up the Yahoo Finance symbol to verify it exists before saving.")

    ns_col1, ns_col2 = st.columns(2)

    with ns_col1:
        new_ticker = st.text_input(
            "Your Ticker Label",
            placeholder="e.g. AAPL or NVDA",
            help="This is how the stock will be labelled in your dashboard",
        ).strip().upper()

        new_name = st.text_input(
            "Company Name",
            placeholder="e.g. Apple Inc",
        ).strip()

        new_market = st.selectbox(
            "Market",
            options=["US", "SGX"],
            help="US = New York Stock Exchange / NASDAQ. SGX = Singapore Exchange.",
        )

        new_currency = "USD" if new_market == "US" else "SGD"
        st.info(f"Currency will be set to **{new_currency}** based on market.")

    with ns_col2:
        new_yf_symbol = st.text_input(
            "Yahoo Finance Symbol",
            placeholder="e.g. AAPL  or  D05.SI  (SGX stocks end in .SI)",
            help="Find this at finance.yahoo.com — search your stock and copy the symbol shown.",
        ).strip().upper()

        new_date = st.date_input(
            "Date Purchased",
            value=date.today(),
        )

        new_shares = st.number_input(
            "Number of Shares",
            min_value=1,
            step=1,
            value=1,
        )

        new_price = st.number_input(
            f"Purchase Price per Share ({new_currency})",
            min_value=0.01,
            step=0.01,
            format="%.4f",
            value=1.0,
        )

    # ── Verify ticker button ──────────────────────────────
    st.divider()

    if st.button("🔍 Verify Ticker on Yahoo Finance", use_container_width=True):
        if not new_yf_symbol:
            st.warning("Please enter a Yahoo Finance symbol first.")
        else:
            with st.spinner(f"Looking up {new_yf_symbol} on Yahoo Finance..."):
                try:
                    test_ticker = yf.Ticker(new_yf_symbol)
                    live_price  = test_ticker.fast_info['last_price']
                    ticker_name = test_ticker.info.get('longName', new_yf_symbol)
                    st.success(f"✅ Found: **{ticker_name}** — Current price: **{new_currency} {live_price:.2f}**")
                    st.session_state['ticker_verified'] = True
                    st.session_state['verified_symbol'] = new_yf_symbol
                except Exception as error:
                    st.error(f"Could not find {new_yf_symbol} on Yahoo Finance: {error}")
                    st.session_state['ticker_verified'] = False

    # ── Save new stock button ─────────────────────────────
    ticker_ok = st.session_state.get('ticker_verified', False)

    if st.button(
        "➕ Add to Portfolio",
        type="primary",
        use_container_width=True,
        disabled=not ticker_ok,
    ):
        if not new_ticker or not new_name or not new_yf_symbol:
            st.warning("Please fill in all fields.")
        else:
            try:
                add_stock_purchase(
                    ticker         = new_ticker,
                    name           = new_name,
                    market         = new_market,
                    date           = new_date.strftime('%d/%m/%Y'),
                    shares         = int(new_shares),
                    purchase_price = float(new_price),
                    currency       = new_currency,
                    yf_symbol      = new_yf_symbol,
                )

                # Clear dashboard cache so new stock shows up immediately
                st.cache_data.clear()
                st.session_state['ticker_verified'] = False

                st.success(f"✅ {new_ticker} — {new_name} added to your portfolio!")
                st.balloons()

            except Exception as error:
                st.error(f"Could not save stock: {error}")


# ═════════════════════════════════════════════════════════════
# TAB 3: Add New Gold Purchase
# ═════════════════════════════════════════════════════════════
with tab_add_gold:
    st.subheader("Add a New Gold Purchase")

    gold_col1, gold_col2 = st.columns(2)

    with gold_col1:
        gold_date = st.date_input(
            "Date Purchased",
            value=date.today(),
            key="gold_date",
        )
        gold_grams = st.number_input(
            "Weight (grams)",
            min_value=0.1,
            step=0.1,
            format="%.1f",
            value=10.0,
            key="gold_grams",
        )

    with gold_col2:
        gold_purity = st.selectbox(
            "Purity",
            options=['24k', '22k'],
            key="gold_purity",
        )
        gold_cost = st.number_input(
            "Cost per Gram at Time of Purchase (SGD)",
            min_value=0.01,
            step=0.01,
            format="%.4f",
            value=200.0,
            key="gold_cost",
        )

    total_cost_preview = gold_grams * gold_cost
    st.info(f"Total purchase cost: **S${total_cost_preview:,.2f}**")

    if st.button("➕ Add Gold Purchase", type="primary", use_container_width=True):
        try:
            add_gold_purchase(
                date          = gold_date.strftime('%d/%m/%Y'),
                grams         = gold_grams,
                cost_per_gram = gold_cost,
                purity        = gold_purity,
            )

            st.cache_data.clear()
            st.success(f"✅ {gold_grams}g of {gold_purity} gold added (purchased at S${gold_cost:.4f}/g)!")
            st.balloons()

        except Exception as error:
            st.error(f"Could not save gold purchase: {error}")


# ═════════════════════════════════════════════════════════════
# TAB 4: View All Holdings (read-only overview)
# ═════════════════════════════════════════════════════════════
with tab_manage_stocks:
    st.subheader("Current Holdings (Read-Only Overview)")
    st.caption("This shows what is currently stored in holdings.json.")

    # Reload to reflect any changes just saved
    current_holdings = load_holdings()

    st.markdown("#### 🥇 Gold Purchases")
    if current_holdings['gold']:
        import pandas as pd
        gold_view = pd.DataFrame(current_holdings['gold'])
        gold_view.columns = ['Date', 'Grams', 'Cost/g (SGD)', 'Purity']
        st.dataframe(gold_view, use_container_width=True, hide_index=True)
    else:
        st.caption("No gold holdings.")

    st.markdown("#### 📈 Stock Holdings")
    if current_holdings['stocks']:
        import pandas as pd
        stocks_view = pd.DataFrame(current_holdings['stocks'])
        st.dataframe(stocks_view, use_container_width=True, hide_index=True)
    else:
        st.caption("No stock holdings.")

    st.markdown("#### 🗺️ Ticker Map (Yahoo Finance Symbols)")
    if current_holdings.get('ticker_map'):
        import pandas as pd
        tm_rows = [
            {'Ticker': k, 'YF Symbol': v['yf'], 'Currency': v['currency']}
            for k, v in current_holdings['ticker_map'].items()
        ]
        st.dataframe(pd.DataFrame(tm_rows), use_container_width=True, hide_index=True)
