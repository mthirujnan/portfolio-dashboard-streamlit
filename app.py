# ============================================================
# File: app.py
# Purpose: The main dashboard screen of the Portfolio app.
#          Shows a summary of total portfolio value, per-asset
#          breakdown, allocation chart, and a Refresh button
#          that re-fetches all live prices.
#
# How to run:  streamlit run app.py
#              (from inside the streamlit_app/ folder)
# ============================================================

import sys
import os

# Make sure Python can find the src/ folder when importing
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from src.data_store   import load_holdings
from src.fetch_prices import fetch_all_prices
from src.portfolio    import calculate_portfolio

# ─────────────────────────────────────────────────────────────
# Page configuration — sets the browser tab title and layout
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Portfolio Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────
# Helper: format numbers as SGD currency strings
# e.g. 12345.6 → "S$12,345.60"
# ─────────────────────────────────────────────────────────────
def fmt_sgd(value):
    """Format a number as a SGD currency string."""
    if value is None:
        return "—"
    return f"S${value:,.2f}"


def fmt_pct(value):
    """Format a number as a percentage string with a + or - sign."""
    if value is None:
        return "—"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def pnl_color(value):
    """Return green or red depending on whether the value is a gain or loss."""
    if value is None:
        return "grey"
    return "green" if value >= 0 else "red"


# ─────────────────────────────────────────────────────────────
# Load and calculate data
# We use st.cache_data so prices are only re-fetched when you
# press Refresh — not on every minor page interaction.
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_dashboard_data():
    """
    Loads holdings, fetches live prices, and calculates the full portfolio.
    Cached so it doesn't re-run on every Streamlit interaction.
    Call st.cache_data.clear() to force a refresh.
    """
    holdings  = load_holdings()
    prices    = fetch_all_prices(holdings)
    portfolio = calculate_portfolio(holdings, prices)
    return portfolio


# ─────────────────────────────────────────────────────────────
# Header row: title + refresh button
# ─────────────────────────────────────────────────────────────
col_title, col_btn = st.columns([5, 1])

with col_title:
    st.title("📊 Portfolio Dashboard")

with col_btn:
    st.write("")  # small vertical spacer so the button aligns with the title
    if st.button("🔄 Refresh", use_container_width=True, type="primary"):
        # Clear cached data so everything re-fetches on next load
        st.cache_data.clear()
        st.rerun()

# ─────────────────────────────────────────────────────────────
# Load data (from cache or fresh if Refresh was pressed)
# ─────────────────────────────────────────────────────────────
try:
    portfolio = load_dashboard_data()
except Exception as error:
    import traceback
    st.error(f"Could not load portfolio data: {error}")
    st.code(traceback.format_exc())
    st.stop()

summary    = portfolio['summary']
fetched_at = portfolio['fetched_at']

st.caption(f"Prices last fetched: {fetched_at}  •  USD/SGD: {portfolio['usd_sgd']:.4f}  •  Gold 24k: {fmt_sgd(portfolio['gold_prices'].get('24k'))} /g  •  Gold 22k: {fmt_sgd(portfolio['gold_prices'].get('22k'))} /g")

st.divider()

# ─────────────────────────────────────────────────────────────
# SECTION 1: Top-level summary metrics
# ─────────────────────────────────────────────────────────────
st.subheader("Portfolio Summary")

col1, col2, col3, col4 = st.columns(4)

total_value    = summary['total_value']
total_invested = summary['total_invested']
total_pnl      = total_value - total_invested  # approximate, excludes SC and full property

with col1:
    st.metric(label="Total Portfolio Value", value=fmt_sgd(total_value))

with col2:
    st.metric(label="Total Invested (tracked)", value=fmt_sgd(total_invested))

with col3:
    pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    st.metric(
        label="Unrealised P&L",
        value=fmt_sgd(total_pnl),
        delta=fmt_pct(pnl_pct),
    )

with col4:
    prop = portfolio['property']
    st.metric(label="Property Equity", value=fmt_sgd(prop['equity']))

st.divider()

# ─────────────────────────────────────────────────────────────
# SECTION 2: Allocation pie chart
# ─────────────────────────────────────────────────────────────
st.subheader("Allocation by Asset Class")

col_chart, col_table = st.columns([1, 1])

with col_chart:
    allocation_df = pd.DataFrame([
        {'Asset Class': name, 'Value (SGD)': value, 'Allocation %': pct}
        for (name, value), pct in zip(
            summary['asset_values'].items(),
            summary['allocation'].values()
        )
    ])

    fig_pie = px.pie(
        allocation_df,
        values='Value (SGD)',
        names='Asset Class',
        hole=0.4,  # donut style
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
    fig_pie.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
    st.plotly_chart(fig_pie, use_container_width=True)

with col_table:
    display_df = allocation_df.copy()
    display_df['Value (SGD)']   = display_df['Value (SGD)'].apply(fmt_sgd)
    display_df['Allocation %']  = display_df['Allocation %'].apply(lambda x: f"{x:.1f}%")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

st.divider()

# ─────────────────────────────────────────────────────────────
# SECTION 3: Asset class detail panels
# Each one is inside an expander — click to open/close.
# ─────────────────────────────────────────────────────────────
st.subheader("Holdings Detail")

# ── Gold ────────────────────────────────────────────────────
gold = portfolio['gold']
with st.expander(
    f"🥇 Gold  —  {fmt_sgd(gold['total_value'])}  |  P&L: {fmt_sgd(gold['total_pnl'])} ({fmt_pct(gold['total_pnl_pct'])})",
    expanded=True
):
    g_col1, g_col2, g_col3, g_col4 = st.columns(4)
    g_col1.metric("Total Value",    fmt_sgd(gold['total_value']))
    g_col2.metric("Total Invested", fmt_sgd(gold['total_invested']))
    g_col3.metric("Total Grams",    f"{gold['total_grams']:.1f}g")
    g_col4.metric("DCA Cost",       fmt_sgd(gold['dca_cost']) + "/g")

    gold_df = pd.DataFrame(gold['rows'])
    if not gold_df.empty:
        gold_df_display = gold_df[[
            'date', 'grams', 'purity', 'cost_per_gram',
            'current_price_per_gram', 'total_cost', 'current_value', 'pnl', 'pnl_pct'
        ]].copy()
        gold_df_display.columns = [
            'Date', 'Grams', 'Purity', 'Cost/g (SGD)',
            'Live Price/g (SGD)', 'Total Cost', 'Current Value', 'P&L (SGD)', 'P&L %'
        ]
        for col in ['Cost/g (SGD)', 'Live Price/g (SGD)', 'Total Cost', 'Current Value', 'P&L (SGD)']:
            gold_df_display[col] = gold_df_display[col].apply(fmt_sgd)
        gold_df_display['P&L %'] = gold_df_display['P&L %'].apply(fmt_pct)
        st.dataframe(gold_df_display, use_container_width=True, hide_index=True)

    st.caption(f"Price source: {gold['price_source']}")

# ── Stocks ──────────────────────────────────────────────────
stocks = portfolio['stocks']
with st.expander(
    f"📈 Stocks  —  {fmt_sgd(stocks['total_value'])}  |  P&L: {fmt_sgd(stocks['total_pnl'])} ({fmt_pct(stocks['total_pnl_pct'])})"
):
    s_col1, s_col2, s_col3 = st.columns(3)
    s_col1.metric("Total Value",    fmt_sgd(stocks['total_value']))
    s_col2.metric("Total Invested", fmt_sgd(stocks['total_invested']))
    s_col3.metric("Total P&L",      fmt_sgd(stocks['total_pnl']), delta=fmt_pct(stocks['total_pnl_pct']))

    if stocks['rows']:
        stocks_df = pd.DataFrame(stocks['rows'])
        stocks_display = stocks_df[[
            'ticker', 'name', 'market', 'shares', 'currency',
            'purchase_price', 'current_price_local', 'purchase_cost_sgd',
            'current_value_sgd', 'pnl_sgd', 'pnl_pct', 'price_source'
        ]].copy()
        stocks_display.columns = [
            'Ticker', 'Name', 'Market', 'Shares', 'CCY',
            'Buy Price', 'Live Price', 'Cost (SGD)',
            'Value (SGD)', 'P&L (SGD)', 'P&L %', 'Source'
        ]
        for col in ['Cost (SGD)', 'Value (SGD)', 'P&L (SGD)']:
            stocks_display[col] = stocks_display[col].apply(fmt_sgd)
        stocks_display['P&L %'] = stocks_display['P&L %'].apply(fmt_pct)
        st.dataframe(stocks_display, use_container_width=True, hide_index=True)

# ── Endowus ─────────────────────────────────────────────────
endowus = portfolio['endowus']
with st.expander(
    f"💼 Endowus  —  {fmt_sgd(endowus['total_value'])}  |  P&L: {fmt_sgd(endowus['total_pnl'])} ({fmt_pct(endowus['total_pnl_pct'])})"
):
    e_col1, e_col2, e_col3, e_col4 = st.columns(4)
    e_col1.metric("Current Value",    fmt_sgd(endowus['total_value']))
    e_col2.metric("Total Invested",   fmt_sgd(endowus['total_invested']))
    e_col3.metric("Total Return",     fmt_sgd(endowus['total_pnl']))
    e_col4.metric("TWR",              fmt_pct(endowus['twr_pct']))
    st.caption("Values entered manually — update in Admin page.")

# ── HSBC RSP ────────────────────────────────────────────────
hsbc = portfolio['hsbc']
with st.expander(
    f"🏦 HSBC RSP  —  {fmt_sgd(hsbc['total_value'])}  |  P&L: {fmt_sgd(hsbc['total_pnl'])} ({fmt_pct(hsbc['total_pnl_pct'])})"
):
    h_col1, h_col2, h_col3 = st.columns(3)
    h_col1.metric("Current Value",  fmt_sgd(hsbc['total_value']))
    h_col2.metric("Total Invested", fmt_sgd(hsbc['total_invested']))
    h_col3.metric("Total P&L",      fmt_sgd(hsbc['total_pnl']), delta=fmt_pct(hsbc['total_pnl_pct']))
    st.caption("Values entered manually — update in Admin page.")

# ── SC Savings ──────────────────────────────────────────────
sc = portfolio['sc']
with st.expander(f"💰 SC Savings  —  {fmt_sgd(sc['total_value'])}"):
    if sc['rows']:
        sc_df = pd.DataFrame(sc['rows'])
        sc_df['balance'] = sc_df['balance'].apply(fmt_sgd)
        sc_df.columns    = ['Account', 'Balance (SGD)']
        st.dataframe(sc_df, use_container_width=True, hide_index=True)
    st.caption("Values entered manually — update in Admin page.")

# ── Property ────────────────────────────────────────────────
prop = portfolio['property']
with st.expander(f"🏠 Property  —  Equity: {fmt_sgd(prop['equity'])}  |  Market Value: {fmt_sgd(prop['current_value'])}"):
    p_col1, p_col2, p_col3, p_col4 = st.columns(4)
    p_col1.metric("Market Value",     fmt_sgd(prop['current_value']))
    p_col2.metric("Purchase Price",   fmt_sgd(prop['purchase_price']))
    p_col3.metric("Outstanding Loan", fmt_sgd(prop['outstanding_loan']))
    p_col4.metric("Your Equity",      fmt_sgd(prop['equity']))
    st.metric("Unrealised Gain", fmt_sgd(prop['unrealised_gain']), delta=fmt_pct(prop['gain_pct']))
    st.caption("Values entered manually — update in Admin page.")

# ── Jewellery ────────────────────────────────────────────────
jewellery = portfolio['jewellery']
with st.expander(f"💍 Jewellery  —  {fmt_sgd(jewellery['current_value'])}"):
    j_col1, j_col2, j_col3 = st.columns(3)
    j_col1.metric("Current Value", fmt_sgd(jewellery['current_value']))
    j_col2.metric("Weight",        f"{jewellery['grams']:.0f}g ({jewellery['purity']})")
    j_col3.metric("Live Price",    fmt_sgd(jewellery['live_price']) + "/g")

    if jewellery['pnl'] is not None:
        j2_col1, j2_col2 = st.columns(2)
        j2_col1.metric("Purchase Cost",  fmt_sgd(jewellery['total_cost']))
        j2_col2.metric("Unrealised P&L", fmt_sgd(jewellery['pnl']), delta=fmt_pct(jewellery['pnl_pct']))
    else:
        st.caption("Purchase cost not entered — P&L not shown. Update in Admin page.")
