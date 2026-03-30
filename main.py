import os
import yaml
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from data import fetcher, parser
from models import dcf, valuation, sensitivity, reverse_dcf, verdict
from llm import analyst, rate_limiter as rl, research

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@st.cache_resource
def load_config():
    config_path = os.path.join(BASE_DIR, "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

config = load_config()

def init_rate_limiter():
    if "rate_limiter" not in st.session_state:
        st.session_state.rate_limiter = rl.RateLimiter(config)
    return st.session_state.rate_limiter

rate_limiter = init_rate_limiter()

st.set_page_config(
    page_title="GRAHAM",
    page_icon="",
    layout="wide",
)

# CSS
st.markdown("""
<style>
    .stApp {
        background-color: #000000 !important;
        color: #ffffff !important;
    }
    section[data-testid="stSidebar"] {
        background-color: #0a0a0a !important;
    }
    div[data-testid="stMetric"] {
        background-color: transparent !important;
        border: none !important;
        padding: 1rem !important;
        text-align: center !important;
    }
    div[data-testid="stMetric"] label {
        color: #9ca3af !important;
        text-align: center !important;
        display: block !important;
        width: 100% !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #00c853 !important;
        text-align: center !important;
        display: block !important;
        width: 100% !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
        color: #9ca3af !important;
        text-align: center !important;
        display: block !important;
        width: 100% !important;
        justify-content: center !important;
    }
    div[data-testid="stMetricDelta"] {
        justify-content: center !important;
    }
    .stButton > button[kind="primary"] {
        background-color: #00c853 !important;
        color: #000000 !important;
        border: none !important;
        font-weight: 700 !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #00e676 !important;
    }
    div[data-testid="stExpander"] {
        background-color: #111111 !important;
        border: 1px solid #1a1a1a !important;
    }
    div[data-testid="stExpander"] summary {
        color: #00c853 !important;
    }
    hr {
        border-top: 1px solid #1a1a1a !important;
    }
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #000000; }
    ::-webkit-scrollbar-thumb { background: #333333; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("<h1 style='color: #00c853; font-size: 2.5rem;'>GRAHAM</h1>", unsafe_allow_html=True)
st.caption("Global Recursive Analyst for Market Assessment and Headlines")

# Sidebar
with st.sidebar:
    st.header("DCF Assumptions")

    with st.expander("Projection & Risk", expanded=True):
        projection_years = st.number_input("Projection Years", 1, 20, config["dcf"]["projection_years"])
        terminal_growth = st.number_input("Terminal Growth", 0.0, 0.1, config["dcf"]["terminal_growth_rate"], 0.001, format="%.3f")
        margin_of_safety = st.number_input("Margin of Safety", 0.0, 0.5, config["dcf"]["margin_of_safety"], 0.01)

    with st.expander("WACC Parameters", expanded=True):
        risk_free = st.number_input("Risk-Free Rate", 0.0, 0.1, config["dcf"]["risk_free_rate"], 0.001, format="%.3f")
        erp = st.number_input("Equity Risk Premium", 0.0, 0.15, config["dcf"]["equity_risk_premium"], 0.001, format="%.3f")
        beta_fb = st.number_input("Beta Fallback", 0.0, 3.0, config["dcf"]["beta_fallback"], 0.1)
        tax_rate = st.number_input("Tax Rate", 0.0, 0.5, config["dcf"]["tax_rate"], 0.01)

    with st.expander("FCF Growth", expanded=True):
        use_override = st.checkbox("Override Growth Rate")
        fcf_override = None
        if use_override:
            fcf_override = st.number_input("Growth Rate", -0.5, 1.0, 0.1, 0.01)
        fcf_cap = st.number_input("Growth Cap", 0.0, 1.0, config["dcf"]["fcf_growth_cap"], 0.01)
        fcf_floor = st.number_input("Growth Floor", -0.5, 0.0, config["dcf"]["fcf_growth_floor"], 0.01)

    if st.button("Reset to Defaults", width="stretch"):
        st.rerun()

    st.markdown("---")
    st.caption("Rate Limits")
    st.caption(f"RPM: {config['rate_limits']['gemini_rpm_limit']} | RPD: {config['rate_limits']['gemini_rpd_limit']}")

assumptions = {
    "projection_years": projection_years, "terminal_growth_rate": terminal_growth,
    "margin_of_safety": margin_of_safety, "risk_free_rate": risk_free,
    "equity_risk_premium": erp, "beta_fallback": beta_fb,
    "tax_rate": tax_rate, "credit_spread": config["dcf"].get("credit_spread", 0.015),
    "fcf_growth_rate_override": fcf_override, "fcf_growth_cap": fcf_cap,
    "fcf_growth_floor": fcf_floor,
}

# Search
st.markdown("---")
with st.form("search_form"):
    col1, col2 = st.columns([4, 1])
    with col1:
        ticker_input = st.text_input("Enter ticker or name", placeholder="AAPL, Apple, Palantir...", label_visibility="collapsed")
    with col2:
        submitted = st.form_submit_button("Analyze", type="primary", width="stretch")


def get_valuation_label(score):
    if score >= 4.5:
        return "Undervalued"
    elif score >= 3.5:
        return "Slightly Undervalued"
    elif score >= 2.5:
        return "Fairly Valued"
    elif score >= 1.5:
        return "Overvalued"
    else:
        return "Highly Overvalued"


def run_analysis(ticker):
    with st.spinner(f"Analyzing {ticker}..."):
        try:
            raw_data = fetcher.fetch_ticker_data(ticker, config)
            parsed = parser.parse(raw_data, ticker, config)

            if parsed["current_price"] is None:
                st.error(f"Financial data unavailable for {ticker}.")
                return

            spy_pe = fetcher.fetch_spy_pe()
            pe_val = valuation.evaluate_pe(parsed, spy_pe)
            dcf_result = dcf.calculate(parsed, assumptions)
            sens = sensitivity.compute_sensitivity(parsed, {**assumptions, "wacc": dcf_result["wacc"]})
            rev_dcf = reverse_dcf.compute_implied_growth(parsed, dcf_result, assumptions)

            news_report = None
            try:
                news_report = analyst.analyze_news(ticker, parsed["company_name"], parsed["news_headlines"], config, rate_limiter)
            except Exception:
                pass

            analyst_data = None
            try:
                analyst_data = research.fetch_analyst_targets(ticker, parsed["company_name"], config, rate_limiter)
            except Exception:
                pass

            sentiment_score = news_report.sentiment_score if news_report else 0
            analyst_avg = analyst_data.get("average_target") if analyst_data else None
            v = verdict.compute_verdict(dcf_result, pe_val, sentiment_score, analyst_avg)
            val_label = get_valuation_label(v["score"])

            # --- DISPLAY ---
            st.markdown(f"### {parsed['company_name']} ({ticker})")
            st.markdown("&nbsp;")

            # Gauge + Metrics side by side
            col_g1, col_g2 = st.columns([1, 1])
            with col_g1:
                fig_v = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=v["score"],
                    domain={"x": [0, 1], "y": [0, 1]},
                    title={"text": f"Verdict: {v['verdict']}"},
                    gauge={
                        "axis": {"range": [1, 5], "tickwidth": 1, "tickcolor": "gray"},
                        "bar": {"color": "#ffffff"},
                        "bgcolor": "#111111",
                        "borderwidth": 0,
                        "steps": [
                            {"range": [1, 2], "color": "#ff1744"},
                            {"range": [2, 3], "color": "#ff9100"},
                            {"range": [3, 4], "color": "#ffea00"},
                            {"range": [4, 5], "color": "#00c853"},
                        ],
                        "threshold": {
                            "line": {"color": "#ffffff", "width": 4},
                            "thickness": 0.8,
                            "value": v["score"],
                        },
                    },
                ))
                fig_v.update_layout(
                    height=250,
                    margin=dict(l=20, r=20, t=50, b=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    font={"color": "#ffffff"},
                )
                st.plotly_chart(fig_v, width="stretch")

                # Valuation label in bold
                label_color = "#00c853" if "Under" in val_label else ("#60a5fa" if "Fair" in val_label else "#ef4444")
                st.markdown(
                    f"<div style='text-align:center; font-size:1.2rem; margin-top:0.5rem;'>"
                    f"<b style='color:{label_color};'>{val_label}</b></div>",
                    unsafe_allow_html=True,
                )

            with col_g2:
                st.markdown("<h4 style='text-align:center;'>Key Valuation Metrics</h4>", unsafe_allow_html=True)
                m1, m2 = st.columns(2)
                with m1:
                    st.metric("Current Price", f"${parsed['current_price']:.2f}")
                with m2:
                    st.metric("Intrinsic Value", f"${dcf_result['intrinsic_value_per_share']:.2f}", f"{dcf_result['upside_pct']*100:.1f}%")

                m3, m4 = st.columns(2)
                with m3:
                    st.metric("MOS Price", f"${dcf_result['margin_of_safety_price']:.2f}")
                with m4:
                    if pe_val["company_pe"]:
                        st.metric(pe_val["pe_type"], f"{pe_val['company_pe']:.1f}x", f"{pe_val['relative_multiple']:.1f}x SPY")

            # Tabs
            t_val, t_news, t_hist, t_src = st.tabs(["Valuation Analysis", "Research & Sentiment", "Historical Data", "Sources"])

            with t_val:
                st.subheader("Free Cash Flow Trend")

                df_cf = raw_data.get("cashflow")
                if df_cf is not None and not df_cf.empty:
                    cf_cols = df_cf.columns[:3]
                    years_hist = [str(int(d.year)) for d in cf_cols]
                    years_hist = list(reversed(years_hist))
                    fcf_hist = parsed["fcf_history"][:3]

                    if len(fcf_hist) < len(years_hist):
                        years_hist = years_hist[:len(fcf_hist)]

                    last_year = int(cf_cols[0].year)
                    years_proj = [str(last_year + i) for i in range(1, assumptions["projection_years"] + 1)]
                    fcf_proj = dcf_result["fcf_projections"]

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=years_hist,
                        y=[v / 1e9 for v in fcf_hist],
                        name="Historical",
                        mode="lines+markers",
                        line=dict(color="#60a5fa", width=3),
                        marker=dict(size=8),
                    ))
                    fig.add_trace(go.Scatter(
                        x=years_proj,
                        y=[v / 1e9 for v in fcf_proj],
                        name="Projected",
                        mode="lines+markers",
                        line=dict(color="#00c853", width=3, dash="dash"),
                        marker=dict(size=8),
                    ))
                    fig.update_layout(
                        height=350,
                        margin=dict(l=40, r=20, t=20, b=40),
                        legend=dict(orientation="h", y=1.1),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font={"color": "#9ca3af"},
                        yaxis_title="$B",
                    )
                    st.plotly_chart(fig, width="stretch")

                st.markdown("---")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Sensitivity Matrix**")
                    st.caption(
                        "This 3x3 grid shows how Intrinsic Value/share changes if your WACC or Growth "
                        "assumptions are off. Rows = WACC variations (base +/- 1%), "
                        "columns = Growth variations (base +/- 2%). "
                        "A narrow range means the valuation is robust. A wide range means it is highly sensitive to assumptions."
                    )
                    mat_df = pd.DataFrame(
                        sens["matrix"],
                        index=sens["wacc_labels"],
                        columns=[f"Growth {g}" for g in sens["growth_labels"]],
                    )
                    st.dataframe(mat_df.style.format("${:.2f}"), width="stretch")
                with c2:
                    st.markdown("**Reverse DCF**")
                    st.caption(
                        "Instead of computing Intrinsic Value, this solves for the FCF growth rate "
                        "the market is pricing in at the current price. If the implied growth is "
                        "much higher than your base assumption, the stock may be overvalued."
                    )
                    if rev_dcf["implied_growth"] is not None:
                        st.metric("Implied FCF Growth", f"{rev_dcf['implied_growth_pct']:.1f}%")
                        st.write(rev_dcf["interpretation"])
                        st.caption(f"Your base growth assumption: {rev_dcf['base_growth_pct']:.1f}%")

            with t_news:
                c_n1, c_n2 = st.columns(2)
                with c_n1:
                    if analyst_data and analyst_data["analysts"]:
                        st.subheader("Analyst Price Targets")
                        for a in analyst_data["analysts"]:
                            if a["rating"] and a["rating"] != "N/A":
                                st.write(f"**{a['firm']}**: ${a['target_price']:.0f} ({a['rating']})")
                            else:
                                st.write(f"**{a['firm']}**: ${a['target_price']:.0f}")
                    else:
                        st.info("Analyst targets unavailable")
                with c_n2:
                    if news_report:
                        st.subheader("AI News Sentiment")
                        st.write(news_report.summary)
                        st.markdown("**Positives:**")
                        for p in news_report.positives:
                            st.markdown(f"- {p}")
                        st.markdown("**Negatives:**")
                        for n in news_report.negatives:
                            st.markdown(f"- {n}")
                    else:
                        st.info("News analysis unavailable")

            with t_hist:
                hist = parsed["historical"]
                if hist["years"]:
                    st.subheader("5-Year Financial Summary ($B)")
                    h_data = {}
                    for m, vals in hist["income"].items():
                        h_data[m] = [f"{x / 1e9:.2f}" for x in vals]
                    for m, vals in hist["cashflow"].items():
                        h_data[m] = [f"{x / 1e9:.2f}" for x in vals]
                    for m, vals in hist["balance"].items():
                        h_data[m] = [f"{x / 1e9:.2f}" for x in vals]
                    if h_data:
                        disp_df = pd.DataFrame(
                            h_data,
                            index=hist["years"][:len(next(iter(h_data.values())))],
                        ).T
                        st.table(disp_df)

                    st.markdown("---")
                    st.subheader("Ownership & Activity")

                    # Institutional Holders
                    if parsed["institutional_holders"]:
                        st.write("**Top Institutional Holders**")
                        for h in parsed["institutional_holders"][:5]:
                            st.write(f"- {h['name']}: {h['pct_held'] * 100:.1f}%")
                        st.markdown("---")

                    # Insider Activity - use insider_transactions for details
                    itx = parsed.get("insider_transactions", [])
                    if itx:
                        st.write("**Recent Insider Transactions**")
                        for d in itx[:5]:
                            name = d.get("insider", "")
                            shares = d.get("shares", 0)
                            date = d.get("date", "")
                            position = d.get("position", "")
                            txn_type = d.get("transaction_type", "")
                            text = d.get("text", "")

                            line = f"**{name}**"
                            if position:
                                line += f" ({position})"
                            line += f": {shares:+,.0f} shares"
                            if date:
                                line += f" on {date}"
                            if text:
                                line += f" — {text}"
                            elif txn_type:
                                line += f" — {txn_type}"
                            st.caption(line)
                    else:
                        pass  # No insider data, don't show anything

            with t_src:
                st.subheader("Data Sources")
                st.markdown("- [Yahoo Finance](https://finance.yahoo.com) — Financial data, balance sheets, cash flow, insider transactions")
                st.markdown("- [S&P 500 ETF (SPY)](https://finance.yahoo.com/quote/SPY) — Market P/E benchmark")
                st.markdown("- [Google AI Studio](https://aistudio.google.com) — LLM for news sentiment analysis")
                st.markdown("- [Yahoo Finance News](https://finance.yahoo.com/quote/{ticker}/news) — Headlines used for sentiment".format(ticker=ticker))
                st.markdown("---")
                st.caption("GRAHAM does not provide financial advice. All analysis is for educational and research purposes only.")

        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
            import traceback
            st.code(traceback.format_exc())


# Ticker Selection
if submitted and ticker_input:
    search_results = fetcher.search_ticker(ticker_input)
    if not search_results:
        st.error(f"Could not find any stocks matching '{ticker_input}'.")
    elif len(search_results) == 1:
        st.session_state.selected_ticker = search_results[0]["symbol"]
    else:
        st.session_state.search_options = {
            f"{r['symbol']} - {r['name']} ({r['exchange']})": r["symbol"]
            for r in search_results
        }
        if "selected_ticker" in st.session_state:
            del st.session_state.selected_ticker

if "selected_ticker" in st.session_state:
    run_analysis(st.session_state.selected_ticker)

if "search_options" in st.session_state:
    st.info("Multiple matches found. Please specify:")
    selected_label = st.selectbox("Select company", list(st.session_state.search_options.keys()), label_visibility="collapsed")
    if st.button("Confirm Selection", width="stretch"):
        ticker = st.session_state.search_options[selected_label]
        del st.session_state.search_options
        st.session_state.selected_ticker = ticker
        st.rerun()
