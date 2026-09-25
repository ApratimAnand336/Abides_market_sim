"""
ABIDES Market Simulation Dashboard
───────────────────────────────────
Interactive Streamlit dashboard for visualizing ABIDES market simulations.

Usage:
    streamlit run dashboard.py
"""

import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import streamlit as st


# ═══════════════════════════════════════════════════════════════════════
# PAGE CONFIG & STYLING
# ═══════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="ABIDES Market Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%); }

    .metric-card {
        background: linear-gradient(135deg, rgba(26, 26, 46, 0.8), rgba(22, 33, 62, 0.6));
        border: 1px solid rgba(100, 120, 200, 0.2);
        border-radius: 12px; padding: 16px 20px; margin: 4px 0;
        backdrop-filter: blur(10px);
    }
    .metric-value { font-size: 28px; font-weight: 700; color: #e0e0ff; margin: 0; }
    .metric-label { font-size: 12px; font-weight: 500; color: #8888aa;
        text-transform: uppercase; letter-spacing: 1px; margin: 0; }

    .news-positive { background: linear-gradient(135deg, rgba(0,180,80,0.15), rgba(0,120,60,0.1));
        border-left: 3px solid #00b450; padding: 10px 15px; border-radius: 0 8px 8px 0; margin: 8px 0; }
    .news-negative { background: linear-gradient(135deg, rgba(220,50,50,0.15), rgba(150,30,30,0.1));
        border-left: 3px solid #dc3232; padding: 10px 15px; border-radius: 0 8px 8px 0; margin: 8px 0; }
    .news-neutral { background: linear-gradient(135deg, rgba(100,100,150,0.15), rgba(80,80,120,0.1));
        border-left: 3px solid #6464aa; padding: 10px 15px; border-radius: 0 8px 8px 0; margin: 8px 0; }

    div[data-testid="stTabs"] button { font-weight: 600; font-size: 14px; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

PICKLE_PATH = Path("sim_data.pkl")

PREDEFINED_NEWS = [
    ("Company announces record quarterly earnings", 0.90),
    ("CEO unexpectedly resigns amid internal disputes", -0.85),
    ("FDA approves company's flagship drug", 0.92),
    ("Company faces major data breach affecting millions", -0.88),
    ("Strategic merger announced with industry leader", 0.75),
    ("Revenue misses analyst expectations by 15%", -0.78),
    ("Company wins $2B government contract", 0.82),
    ("Product recall issued due to safety concerns", -0.70),
    ("Analysts upgrade stock to strong buy", 0.65),
    ("Regulatory investigation launched into company practices", -0.72),
]


def metric_card(label, value, delta=None, delta_color="normal"):
    delta_html = ""
    if delta is not None:
        color = "#00b450" if (delta_color == "normal" and delta >= 0) else "#dc3232"
        if delta_color == "inverse":
            color = "#dc3232" if delta >= 0 else "#00b450"
        arrow = "▲" if delta >= 0 else "▼"
        delta_html = f'<p style="color:{color}; font-size:14px; margin:2px 0 0 0;">{arrow} {abs(delta):.4f}</p>'
    st.markdown(f"""
    <div class="metric-card">
        <p class="metric-label">{label}</p>
        <p class="metric-value">{value}</p>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def load_sim_data():
    if not PICKLE_PATH.exists():
        return None
    with open(PICKLE_PATH, "rb") as f:
        return pickle.load(f)


def ns_to_display(ns_val, baseline_ns, time_unit):
    """Convert nanosecond timestamp to display value in the appropriate unit."""
    delta_sec = (ns_val - baseline_ns) / 1e9
    if time_unit == "seconds":
        return delta_sec
    elif time_unit == "minutes":
        return delta_sec / 60
    else:
        return delta_sec / 3600


# ═══════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 🎛️ Simulation Controls")
    seed = st.number_input("Random Seed", value=42, min_value=0, step=1)
    end_time = st.selectbox("Market Close Time", [
        "10:00:00", "10:30:00", "11:00:00", "12:00:00", "14:00:00", "16:00:00"
    ], index=5)
    num_ekf = st.slider("Number of EKF Agents", 1, 20, 5)

    st.markdown("---")
    st.markdown("## 📰 News Events")

    if "news_list" not in st.session_state:
        st.session_state.news_list = []

    news_time = st.text_input("Time offset (HH:MM:SS from open)", "00:05:00", key="news_time")
    news_mode = st.radio("News Input", ["Predefined", "Custom"], horizontal=True)

    if news_mode == "Predefined":
        selected_news = st.selectbox("Select headline", [n[0] for n in PREDEFINED_NEWS])
        sentiment_val = next(n[1] for n in PREDEFINED_NEWS if n[0] == selected_news)
        st.info(f"Sentiment: **{sentiment_val:+.2f}**")
        headline = selected_news
    else:
        headline = st.text_input("Headline", "Company announces new product line")
        use_finbert = st.checkbox("Score with FinBERT", value=True)
        if use_finbert:
            sentiment_val = None
        else:
            sentiment_val = st.slider("Manual Sentiment", -1.0, 1.0, 0.0, 0.05)

    if st.button("➕ Add News Event", use_container_width=True):
        if news_mode == "Custom" and use_finbert and sentiment_val is None:
            try:
                from abides_markets.models.finbert_sentiment import FinBERTSentiment
                with st.spinner("Scoring with FinBERT..."):
                    analyzer = FinBERTSentiment()
                    result = analyzer.score(headline)
                    sentiment_val = result["sentiment"]
                st.success(f"FinBERT: **{sentiment_val:+.4f}**")
            except Exception as e:
                st.error(f"FinBERT error: {e}")
                sentiment_val = 0.0
        if sentiment_val is not None:
            st.session_state.news_list.append((news_time, "ABM", sentiment_val, headline))

    if st.session_state.news_list:
        st.markdown("### Queued Events")
        for i, (t, sym, sent, hl) in enumerate(st.session_state.news_list):
            css = "news-positive" if sent > 0.1 else ("news-negative" if sent < -0.1 else "news-neutral")
            st.markdown(f'<div class="{css}"><b>{t}</b> | {sent:+.2f}<br><small>{hl}</small></div>', unsafe_allow_html=True)
        if st.button("🗑️ Clear All News", use_container_width=True):
            st.session_state.news_list = []
            st.rerun()

    st.markdown("---")
    if st.button("🚀 Run Simulation", type="primary", use_container_width=True):
        cmd = [sys.executable, "run_dashboard_sim.py",
               "--seed", str(seed), "--end-time", end_time, "--num-ekf", str(num_ekf)]
        for t, sym, sent, hl in st.session_state.news_list:
            cmd.extend(["--news", f"{t},{sym},{sent},{hl}"])
        with st.spinner("Running ABIDES simulation..."):
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).parent))
            if result.returncode == 0:
                st.success("Simulation complete!")
                st.code(result.stdout[-800:] if len(result.stdout) > 800 else result.stdout)
            else:
                st.error("Simulation failed!")
                st.code(result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr)
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ═══════════════════════════════════════════════════════════════════════

st.markdown("# 📊 ABIDES Market Simulation Dashboard")

data = load_sim_data()
if data is None:
    st.warning("No simulation data found. Click **🚀 Run Simulation** in the sidebar.")
    st.stop()

book = data["book"]
ohlcv = data["ohlcv"]
time_unit = data.get("time_unit", "seconds")
agents_data = data["agents"]
oracle_data = data["oracle"]
trades = data["trades"]
baseline_ns = data.get("baseline_ns", data.get("mkt_open_ns", 0))
ticker = data["ticker"]

# Compute display times
times_display = [ns_to_display(t, baseline_ns, time_unit) for t in book["times_ns"]]
oracle_times_display = [ns_to_display(t, baseline_ns, time_unit) for t in oracle_data["times_ns"]]
time_label = f"Time ({time_unit} from first activity)"


# ═══════════════════════════════════════════════════════════════════════
# TOP METRICS
# ═══════════════════════════════════════════════════════════════════════

if book["mids"]:
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Opening Price", f"${book['mids'][0]:.2f}")
    with c2:
        metric_card("Closing Price", f"${book['mids'][-1]:.2f}",
                     delta=book['mids'][-1] - book['mids'][0])
    with c3:
        metric_card("Price Points", f"{len(book['mids']):,}")
    with c4:
        metric_card("OHLCV Candles", f"{len(ohlcv)}")
    with c5:
        metric_card("EKF Agents", f"{len(agents_data)}")

st.markdown("")


# ═══════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Market Overview",
    "🤖 Agent Performance",
    "📰 News & Sentiment",
    "📊 Market Health",
])


# ─────────────────────────────────────────────────────────────────────
# TAB 1: MARKET OVERVIEW
# ─────────────────────────────────────────────────────────────────────

with tab1:
    if len(ohlcv) > 0:
        fig = make_subplots(
            rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03,
            row_heights=[0.6, 0.2, 0.2],
            subplot_titles=("Price Action", "Tick Volume", "Bid-Ask Spread"),
        )

        # Candlestick chart
        fig.add_trace(go.Candlestick(
            x=ohlcv["time_display"],
            open=ohlcv["open"], high=ohlcv["high"],
            low=ohlcv["low"], close=ohlcv["close"],
            name="Price",
            increasing_line_color="#00cc66", decreasing_line_color="#ff3366",
            increasing_fillcolor="rgba(0, 204, 102, 0.4)",
            decreasing_fillcolor="rgba(255, 51, 102, 0.4)",
        ), row=1, col=1)

        # Oracle fundamental overlay
        if oracle_data["values"]:
            fig.add_trace(go.Scatter(
                x=oracle_times_display, y=oracle_data["values"],
                mode="lines", name="Oracle Fundamental",
                line=dict(color="#ff9900", width=2, dash="dash"), opacity=0.7,
            ), row=1, col=1)

        # EKF agent estimates
        colors = px.colors.qualitative.Vivid
        for i, (aid, adata) in enumerate(agents_data.items()):
            ekf_df = adata["ekf_updates"]
            if len(ekf_df) > 0 and "time_ns" in ekf_df.columns and "x_hat" in ekf_df.columns:
                et = [ns_to_display(t, baseline_ns, time_unit) for t in ekf_df["time_ns"]]
                fig.add_trace(go.Scatter(
                    x=et, y=[v / 100 for v in ekf_df["x_hat"]],
                    mode="lines", name=f"{adata['name']} x̂",
                    line=dict(color=colors[i % len(colors)], width=1.5), opacity=0.6,
                ), row=1, col=1)

        # News markers
        news_markers = []
        for aid, adata in agents_data.items():
            ndf = adata["news_events"]
            if len(ndf) > 0 and "time_ns" in ndf.columns:
                for _, row in ndf.iterrows():
                    news_markers.append(row.to_dict())
                break

        for ev in news_markers:
            t_d = ns_to_display(ev.get("time_ns", 0), baseline_ns, time_unit)
            s = ev.get("sentiment", 0)
            color = "#00cc66" if s > 0 else "#ff3366"
            fig.add_vline(x=t_d, line_color=color, line_width=2, line_dash="dot", row=1, col=1)

        # Volume bars
        fig.add_trace(go.Bar(
            x=ohlcv["time_display"], y=ohlcv["volume"],
            name="Volume", marker_color="rgba(100, 140, 255, 0.4)",
        ), row=2, col=1)

        # Spread — downsample for performance
        ds = max(1, len(times_display) // 2000)
        fig.add_trace(go.Scatter(
            x=times_display[::ds],
            y=[book["spreads"][i] for i in range(0, len(book["spreads"]), ds)],
            mode="lines", name="Spread",
            line=dict(color="#bb66ff", width=1),
            fill="tozeroy", fillcolor="rgba(187, 102, 255, 0.1)",
        ), row=3, col=1)

        fig.update_layout(
            template="plotly_dark", height=800, showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis3_title=time_label,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,26,0.8)",
            xaxis_rangeslider_visible=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    elif book["mids"]:
        # Fallback: line chart when we can't build candles
        st.markdown("### Price Timeline (Line Chart)")
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=times_display, y=book["mids"],
            mode="lines", name="Mid Price",
            line=dict(color="#00ccff", width=2),
        ))
        if oracle_data["values"]:
            fig_line.add_trace(go.Scatter(
                x=oracle_times_display, y=oracle_data["values"],
                mode="lines", name="Oracle Fundamental",
                line=dict(color="#ff9900", width=2, dash="dash"),
            ))
        fig_line.update_layout(
            template="plotly_dark", height=500,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,26,0.8)",
            xaxis_title=time_label, yaxis_title="Price ($)",
        )
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.warning("No price data available. Try a different seed or longer simulation.")

    # Bid-Ask Band
    if book["best_bids"] and len(book["best_bids"]) > 1:
        st.markdown("### Bid-Ask Spread Band")
        ds = max(1, len(times_display) // 3000)
        fig_band = go.Figure()
        td = times_display[::ds]
        fig_band.add_trace(go.Scatter(
            x=td, y=[book["best_asks"][i] for i in range(0, len(book["best_asks"]), ds)],
            mode="lines", name="Best Ask", line=dict(color="#ff5555", width=1),
        ))
        fig_band.add_trace(go.Scatter(
            x=td, y=[book["best_bids"][i] for i in range(0, len(book["best_bids"]), ds)],
            mode="lines", name="Best Bid", line=dict(color="#55ff55", width=1),
            fill="tonexty", fillcolor="rgba(100, 200, 255, 0.1)",
        ))
        fig_band.update_layout(
            template="plotly_dark", height=300,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,26,0.8)",
            xaxis_title=time_label, yaxis_title="Price ($)", margin=dict(t=20),
        )
        st.plotly_chart(fig_band, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────
# TAB 2: AGENT PERFORMANCE
# ─────────────────────────────────────────────────────────────────────

with tab2:
    if not agents_data:
        st.warning("No EKF agent data available.")
    else:
        agent_names = {aid: adata["name"] for aid, adata in agents_data.items()}
        selected_agent_id = st.selectbox("Select Agent", list(agent_names.keys()),
                                          format_func=lambda x: agent_names[x])
        adata = agents_data[selected_agent_id]
        ekf_df = adata["ekf_updates"]
        caution_df = adata["caution_updates"]

        ca, cb = st.columns(2)

        with ca:
            st.markdown("### EKF State: x̂ vs Market Price")
            if len(ekf_df) > 0 and "time_ns" in ekf_df.columns:
                et = [ns_to_display(t, baseline_ns, time_unit) for t in ekf_df["time_ns"]]
                fig_ekf = go.Figure()
                if "mid" in ekf_df.columns:
                    fig_ekf.add_trace(go.Scatter(
                        x=et, y=[v / 100 for v in ekf_df["mid"]],
                        mode="lines", name="Market Mid", line=dict(color="#6688cc", width=1),
                    ))
                fig_ekf.add_trace(go.Scatter(
                    x=et, y=[v / 100 for v in ekf_df["x_hat"]],
                    mode="lines", name="EKF Estimate (x̂)", line=dict(color="#ff9900", width=2),
                ))
                fig_ekf.update_layout(
                    template="plotly_dark", height=350,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,26,0.8)",
                    xaxis_title=time_label, yaxis_title="Price ($)", margin=dict(t=20),
                )
                st.plotly_chart(fig_ekf, use_container_width=True)
            else:
                st.info("No EKF updates recorded for this agent.")

        with cb:
            st.markdown("### Kalman Gain & Efficiency Ratio")
            if len(ekf_df) > 0 and "K" in ekf_df.columns:
                et = [ns_to_display(t, baseline_ns, time_unit) for t in ekf_df["time_ns"]]
                fig_k = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                                       subplot_titles=("Kalman Gain (K)", "Efficiency Ratio (ER)"))
                fig_k.add_trace(go.Scatter(
                    x=et, y=ekf_df["K"].tolist(), mode="lines", name="K",
                    line=dict(color="#00ccff", width=1.5),
                ), row=1, col=1)
                if "ER" in ekf_df.columns:
                    fig_k.add_trace(go.Scatter(
                        x=et, y=ekf_df["ER"].tolist(), mode="lines", name="ER",
                        line=dict(color="#ffcc00", width=1.5),
                    ), row=2, col=1)
                fig_k.update_layout(
                    template="plotly_dark", height=350,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,26,0.8)",
                    margin=dict(t=30), showlegend=False,
                )
                st.plotly_chart(fig_k, use_container_width=True)

        # Caution Modulator
        st.markdown("### Caution Modulator (Confidence C_t)")
        if len(caution_df) > 0 and "time_ns" in caution_df.columns:
            ct = [ns_to_display(t, baseline_ns, time_unit) for t in caution_df["time_ns"]]
            fig_c = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                                   subplot_titles=("Confidence (C_t)", "Emotional Memory (E_t)"))
            fig_c.add_trace(go.Scatter(
                x=ct, y=caution_df["C_t"].tolist(), mode="lines", name="C_t",
                line=dict(color="#00ff88", width=2),
                fill="tozeroy", fillcolor="rgba(0, 255, 136, 0.1)",
            ), row=1, col=1)
            if "E_t" in caution_df.columns:
                fig_c.add_trace(go.Scatter(
                    x=ct, y=caution_df["E_t"].tolist(), mode="lines", name="E_t",
                    line=dict(color="#ff6688", width=1.5),
                ), row=2, col=1)
            fig_c.update_layout(
                template="plotly_dark", height=400,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,26,0.8)",
                xaxis2_title=time_label, margin=dict(t=30), showlegend=False,
            )
            fig_c.update_yaxes(range=[0, 1.05], row=1, col=1)
            st.plotly_chart(fig_c, use_container_width=True)
        else:
            st.info("No caution modulator data recorded.")

        # Holdings
        st.markdown("### Agent Holdings")
        holdings = adata.get("holdings", {})
        if holdings:
            hc1, hc2 = st.columns(2)
            with hc1:
                metric_card("Cash", f"${holdings.get('CASH', 0) / 100:,.2f}")
            with hc2:
                metric_card(f"Shares ({ticker})", f"{holdings.get(ticker, 0):,}")


# ─────────────────────────────────────────────────────────────────────
# TAB 3: NEWS & SENTIMENT
# ─────────────────────────────────────────────────────────────────────

with tab3:
    st.markdown("### 📰 News Impact Analysis")

    st.markdown("#### Test FinBERT Sentiment")
    test_headline = st.text_input("Type a headline to score:", "Company reports strong quarterly growth")
    if st.button("🔍 Score with FinBERT"):
        try:
            from abides_markets.models.finbert_sentiment import FinBERTSentiment
            with st.spinner("Loading FinBERT and scoring..."):
                analyzer = FinBERTSentiment()
                result = analyzer.score(test_headline)
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1: metric_card("Positive", f"{result['positive']:.4f}")
            with sc2: metric_card("Negative", f"{result['negative']:.4f}")
            with sc3: metric_card("Neutral", f"{result['neutral']:.4f}")
            with sc4:
                s = result["sentiment"]
                icon = "🟢" if s > 0.1 else ("🔴" if s < -0.1 else "⚪")
                metric_card("Sentiment", f"{icon} {s:+.4f}")
        except Exception as e:
            st.error(f"FinBERT error: {e}")

    st.markdown("---")
    st.markdown("#### News Events in This Simulation")

    all_news = []
    for aid, adata in agents_data.items():
        ndf = adata["news_events"]
        if len(ndf) > 0:
            for _, row in ndf.iterrows():
                all_news.append(row.to_dict())
            break

    if all_news:
        for event in all_news:
            t_d = ns_to_display(event.get("time_ns", 0), baseline_ns, time_unit)
            sent = event.get("sentiment", 0)
            hl = event.get("headline", "Unknown")
            css = "news-positive" if sent > 0.1 else ("news-negative" if sent < -0.1 else "news-neutral")
            emoji = "📈" if sent > 0.1 else ("📉" if sent < -0.1 else "➖")
            st.markdown(f"""
            <div class="{css}">
                <b>{emoji} t={t_d:.2f} {time_unit}</b> | Sentiment: {sent:+.2f}<br>
                <small>{hl}</small>
            </div>
            """, unsafe_allow_html=True)

        # Impact chart
        if book["mids"]:
            st.markdown("#### Price Impact Timeline")
            fig_impact = go.Figure()
            ds = max(1, len(times_display) // 2000)
            fig_impact.add_trace(go.Scatter(
                x=times_display[::ds],
                y=[book["mids"][i] for i in range(0, len(book["mids"]), ds)],
                mode="lines", name="Mid Price", line=dict(color="#6688cc", width=1.5),
            ))
            for event in all_news:
                t_d = ns_to_display(event.get("time_ns", 0), baseline_ns, time_unit)
                s = event.get("sentiment", 0)
                fig_impact.add_vline(x=t_d, line_color="#00cc66" if s > 0 else "#ff3366",
                                      line_width=2, line_dash="dot")
            fig_impact.update_layout(
                template="plotly_dark", height=400,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,26,0.8)",
                xaxis_title=time_label, yaxis_title="Price ($)", margin=dict(t=20),
            )
            st.plotly_chart(fig_impact, use_container_width=True)
    else:
        st.info("No news events were injected. Add news in the sidebar and re-run.")


# ─────────────────────────────────────────────────────────────────────
# TAB 4: MARKET HEALTH
# ─────────────────────────────────────────────────────────────────────

with tab4:
    st.markdown("### Market Health Metrics")

    if book["mids"] and len(book["mids"]) > 1:
        log_returns = np.diff(np.log(np.array(book["mids"])))
        log_returns = log_returns[np.isfinite(log_returns)]

        hc1, hc2, hc3, hc4 = st.columns(4)
        with hc1: metric_card("Return Kurtosis", f"{pd.Series(log_returns).kurtosis():.2f}")
        with hc2: metric_card("Return Skewness", f"{pd.Series(log_returns).skew():.4f}")
        with hc3: metric_card("Return Std", f"{np.std(log_returns):.6f}")
        with hc4:
            if oracle_data["values"] and oracle_times_display:
                fund_interp = np.interp(times_display, oracle_times_display, oracle_data["values"])
                te = np.sqrt(np.mean((np.array(book["mids"]) - fund_interp) ** 2))
                metric_card("RMS Tracking Error", f"${te:.4f}")
            else:
                metric_card("RMS Tracking Error", "N/A")

        rc1, rc2 = st.columns(2)
        with rc1:
            st.markdown("#### Return Distribution")
            fig_ret = go.Figure()
            fig_ret.add_trace(go.Histogram(
                x=log_returns, nbinsx=150,
                marker_color="rgba(0, 200, 255, 0.5)",
                marker_line=dict(color="rgba(0, 200, 255, 0.8)", width=0.5),
            ))
            fig_ret.add_vline(x=0, line_color="red", line_dash="dash", line_width=1)
            fig_ret.update_layout(
                template="plotly_dark", height=400,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,26,0.8)",
                xaxis_title="Log Return", yaxis_title="Count", margin=dict(t=20),
            )
            st.plotly_chart(fig_ret, use_container_width=True)

        with rc2:
            st.markdown("#### Spread Distribution")
            fig_sp = go.Figure()
            fig_sp.add_trace(go.Histogram(
                x=book["spreads"], nbinsx=100,
                marker_color="rgba(187, 102, 255, 0.5)",
                marker_line=dict(color="rgba(187, 102, 255, 0.8)", width=0.5),
            ))
            fig_sp.update_layout(
                template="plotly_dark", height=400,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,15,26,0.8)",
                xaxis_title="Spread ($)", yaxis_title="Count", margin=dict(t=20),
            )
            st.plotly_chart(fig_sp, use_container_width=True)

        # Summary table
        st.markdown("#### Summary Statistics")
        summary = pd.DataFrame({
            "Metric": [
                "Price Range", "Opening Price", "Closing Price", "Price Change",
                "Mean Spread", "Median Spread", "Max Spread",
                "Total Price Points", "OHLCV Candles", "Trades",
                "Return Mean", "Return Std", "Kurtosis", "Skewness",
            ],
            "Value": [
                f"${min(book['mids']):.2f} — ${max(book['mids']):.2f}",
                f"${book['mids'][0]:.2f}", f"${book['mids'][-1]:.2f}",
                f"${book['mids'][-1] - book['mids'][0]:+.2f}",
                f"${np.mean(book['spreads']):.4f}", f"${np.median(book['spreads']):.4f}",
                f"${max(book['spreads']):.4f}",
                f"{len(book['mids']):,}", f"{len(ohlcv)}", f"{len(trades):,}",
                f"{np.mean(log_returns):.8f}", f"{np.std(log_returns):.8f}",
                f"{pd.Series(log_returns).kurtosis():.2f}", f"{pd.Series(log_returns).skew():.4f}",
            ],
        })
        st.dataframe(summary, hide_index=True, use_container_width=True)
    else:
        st.warning("Not enough data for market health metrics.")

st.markdown("---")
st.caption(f"Simulation: seed={data.get('seed', '?')} | end_time={data.get('end_time', '?')} | "
           f"EKF agents: {len(agents_data)} | Time unit: {time_unit}")
