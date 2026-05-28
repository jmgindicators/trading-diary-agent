"""Streamlit dashboard for the trading diary agent.

Run with: streamlit run dashboard.py
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from trading_diary import database

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Trading Diary | JMG",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stMetric {
        background-color: #1a1f2e;
        padding: 16px 20px;
        border-radius: 10px;
        border: 1px solid #2a3140;
    }
    [data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: 700;
        color: #e8eaf0;
    }
    [data-testid="stMetricLabel"] {
        font-size: 12px;
        color: #8b9bb4;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    [data-testid="stMetricDelta"] {
        color: #cbd5e1;
    }
    h1 { color: #e8eaf0; padding-bottom: 0px; }
    h2 { color: #e8eaf0; border-bottom: 1px solid #2a3140; padding-bottom: 8px; margin-top: 32px; }
    h3 { color: #e8eaf0; margin-top: 24px; }
    .section-subtitle { color: #8b9bb4; margin-top: -10px; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# DATA LOADING
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_trades() -> pd.DataFrame:
    """Load trades and their analyses from SQLite."""
    database.init_db()
    trades = database.fetch_trades()

    rows = []
    for t in trades:
        analysis = database.fetch_analysis(t.id) if t.id else None
        rows.append({
            "id": t.id,
            "entry_time": t.entry_time,
            "instrument": t.instrument,
            "direction": t.direction.value,
            "quantity": t.quantity,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "pnl": t.pnl,
            "commission": t.commission,
            "net_pnl": t.pnl - t.commission,
            "duration_min": t.duration_minutes,
            "notes": t.notes,
            "setup_type": analysis.setup_type.value if analysis else None,
            "quality_score": analysis.quality_score if analysis else None,
            "entry_quality": analysis.entry_quality if analysis else "",
            "exit_quality": analysis.exit_quality if analysis else "",
            "lesson_learned": analysis.lesson_learned if analysis else "",
            "pattern_tags": ", ".join(analysis.pattern_tags) if analysis else "",
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["entry_time"] = pd.to_datetime(df["entry_time"])
        df["date"] = df["entry_time"].dt.date
    return df


@st.cache_data(ttl=30)
def load_summaries() -> pd.DataFrame:
    """Load saved daily/weekly/monthly summaries."""
    db_path = Path("data/trades.db")
    if not db_path.exists():
        return pd.DataFrame()
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            "SELECT period_type, period_value, content, created_at FROM summaries "
            "ORDER BY created_at DESC",
            conn,
        )


# ──────────────────────────────────────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────────────────────────────────────

st.title("📊 Trading Diary Dashboard")
st.markdown(
    "<p class='section-subtitle'>AI-powered futures trading journal · JMG Trading · MNQ Specialist</p>",
    unsafe_allow_html=True,
)

df = load_trades()

if df.empty:
    st.warning(
        "No hay trades en la base de datos.\n\n"
        "Ejecuta en terminal:\n"
        "```\ndiary import data/sample_trades.csv\ndiary analyze\n```"
    )
    st.stop()


# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR FILTERS
# ──────────────────────────────────────────────────────────────────────────────

st.sidebar.header("🔍 Filtros")

min_date = df["date"].min()
max_date = df["date"].max()
date_range = st.sidebar.date_input(
    "Rango de fechas",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

setup_options = ["Todos"] + sorted(df["setup_type"].dropna().unique().tolist())
selected_setup = st.sidebar.selectbox("Tipo de setup", setup_options)
direction_filter = st.sidebar.selectbox("Dirección", ["Todas", "long", "short"])

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Acerca de**\n\n"
    "Sistema de coaching de trading impulsado por Claude (Anthropic).\n\n"
    "Cada trade se clasifica con tool-use estructurado y los resúmenes diarios "
    "se generan en tono profesional."
)

# Apply filters
filtered = df.copy()
if isinstance(date_range, tuple) and len(date_range) == 2:
    filtered = filtered[
        (filtered["date"] >= date_range[0]) & (filtered["date"] <= date_range[1])
    ]
if selected_setup != "Todos":
    filtered = filtered[filtered["setup_type"] == selected_setup]
if direction_filter != "Todas":
    filtered = filtered[filtered["direction"] == direction_filter]


# ──────────────────────────────────────────────────────────────────────────────
# KPIs
# ──────────────────────────────────────────────────────────────────────────────

total_trades = len(filtered)
if total_trades == 0:
    st.warning("No hay trades con esos filtros. Cambia los filtros para ver datos.")
    st.stop()

wins = int((filtered["net_pnl"] > 0).sum())
losses = int((filtered["net_pnl"] < 0).sum())
win_rate = (wins / total_trades * 100) if total_trades else 0
total_pnl = filtered["net_pnl"].sum()
avg_quality = filtered["quality_score"].mean() if filtered["quality_score"].notna().any() else 0
best_trade = filtered["net_pnl"].max()
worst_trade = filtered["net_pnl"].min()

col1, col2, col3, col4 = st.columns(4)
col1.metric("P&L Neto", f"${total_pnl:+,.2f}", delta=f"{total_trades} trades", delta_color="off") 
col2.metric("Win Rate", f"{win_rate:.1f}%", delta=f"{wins}W / {losses}L", delta_color="off")
col3.metric("Calidad Media IA", f"{avg_quality:.1f}/5", delta="Análisis Claude", delta_color="off")
col4.metric(
    "Mejor / Peor Trade",
    f"${best_trade:+,.0f}",
    delta=f"Peor: ${worst_trade:+,.0f}",
    delta_color="off",
)


# ──────────────────────────────────────────────────────────────────────────────
# EQUITY CURVE
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("📈 Curva de Capital")

equity_df = filtered.sort_values("entry_time").copy()
equity_df["cumulative_pnl"] = equity_df["net_pnl"].cumsum()

fig_equity = go.Figure()
fig_equity.add_trace(go.Scatter(
    x=equity_df["entry_time"],
    y=equity_df["cumulative_pnl"],
    mode="lines+markers",
    line=dict(color="#4ade80", width=2.5),
    marker=dict(size=8, line=dict(color="#0e1117", width=2)),
    fill="tozeroy",
    fillcolor="rgba(74, 222, 128, 0.1)",
    hovertemplate="<b>%{x|%Y-%m-%d %H:%M}</b><br>P&L acumulado: $%{y:,.2f}<extra></extra>",
))
fig_equity.update_layout(
    height=340,
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=10, b=0),
    xaxis=dict(gridcolor="#1a1f2e"),
    yaxis=dict(gridcolor="#1a1f2e", title="P&L Acumulado ($)"),
    hoverlabel=dict(bgcolor="#1a1f2e", font_size=13),
)
st.plotly_chart(fig_equity, use_container_width=True)


# ──────────────────────────────────────────────────────────────────────────────
# TWO COLUMNS: P&L per trade + Setup breakdown
# ──────────────────────────────────────────────────────────────────────────────

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("💰 P&L por Trade")
    pnl_df = filtered.sort_values("entry_time").copy()
    colors = ["#4ade80" if v > 0 else "#f87171" for v in pnl_df["net_pnl"]]
    fig_pnl = go.Figure(go.Bar(
        x=[f"#{i}" for i in pnl_df["id"]],
        y=pnl_df["net_pnl"],
        marker_color=colors,
        text=[f"${v:+,.0f}" for v in pnl_df["net_pnl"]],
        textposition="outside",
        hovertemplate="<b>Trade #%{x}</b><br>P&L: $%{y:,.2f}<extra></extra>",
    ))
    fig_pnl.update_layout(
        height=320,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False,
        xaxis=dict(title="", gridcolor="#1a1f2e"),
        yaxis=dict(title="P&L ($)", gridcolor="#1a1f2e"),
    )
    st.plotly_chart(fig_pnl, use_container_width=True)

with col_right:
    st.subheader("🎯 Rendimiento por Setup")
    if filtered["setup_type"].notna().any():
        setup_stats = filtered.dropna(subset=["setup_type"]).groupby("setup_type").agg(
            count=("id", "count"),
            pnl=("net_pnl", "sum"),
            wins=("net_pnl", lambda x: (x > 0).sum()),
        ).reset_index()
        setup_stats["win_rate"] = (setup_stats["wins"] / setup_stats["count"] * 100).round(0)

        fig_setup = go.Figure(go.Bar(
            x=setup_stats["setup_type"],
            y=setup_stats["pnl"],
            marker_color=["#4ade80" if v > 0 else "#f87171" for v in setup_stats["pnl"]],
            text=[
                f"${row['pnl']:+,.0f}<br>{row['count']} trades · {row['win_rate']:.0f}% WR"
                for _, row in setup_stats.iterrows()
            ],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>P&L total: $%{y:,.2f}<extra></extra>",
        ))
        fig_setup.update_layout(
            height=320,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=20),
            showlegend=False,
            xaxis=dict(title="", gridcolor="#1a1f2e"),
            yaxis=dict(title="P&L ($)", gridcolor="#1a1f2e"),
        )
        st.plotly_chart(fig_setup, use_container_width=True)
    else:
        st.info("Sin análisis disponibles. Ejecuta `diary analyze`.")


# ──────────────────────────────────────────────────────────────────────────────
# QUALITY DISTRIBUTION
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("⭐ Calidad de Ejecución (puntuación IA)")

quality_counts = (
    filtered.dropna(subset=["quality_score"])
    .groupby("quality_score")
    .size()
    .reindex([1, 2, 3, 4, 5], fill_value=0)
    .reset_index()
)
quality_counts.columns = ["score", "count"]

color_map = ["#dc2626", "#ea580c", "#facc15", "#84cc16", "#4ade80"]
fig_quality = go.Figure(go.Bar(
    x=[f"{int(s)}/5" for s in quality_counts["score"]],
    y=quality_counts["count"],
    marker_color=color_map,
    text=quality_counts["count"],
    textposition="outside",
    hovertemplate="<b>Calidad %{x}</b><br>%{y} trades<extra></extra>",
))
fig_quality.update_layout(
    height=260,
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=10, b=0),
    showlegend=False,
    xaxis=dict(title="1 = impulsivo · 5 = manual", gridcolor="#1a1f2e"),
    yaxis=dict(title="Trades", gridcolor="#1a1f2e"),
)
st.plotly_chart(fig_quality, use_container_width=True)


# ──────────────────────────────────────────────────────────────────────────────
# TRADE TABLE
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("📋 Tabla de Trades")
table_df = filtered[
    ["id", "entry_time", "instrument", "direction", "quantity",
     "net_pnl", "setup_type", "quality_score"]
].copy()
table_df["entry_time"] = table_df["entry_time"].dt.strftime("%Y-%m-%d %H:%M")
table_df.columns = ["#", "Fecha/Hora", "Inst.", "Dir.", "Qty", "P&L ($)", "Setup", "Q"]
st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "P&L ($)": st.column_config.NumberColumn("P&L ($)", format="$%+,.2f"),
        "Q": st.column_config.NumberColumn("Q", format="%d/5"),
    },
)


# ──────────────────────────────────────────────────────────────────────────────
# TRADE DETAIL VIEWER
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("🔬 Análisis Detallado de Trade")

selected_id = st.selectbox(
    "Selecciona un trade para ver el análisis completo:",
    options=filtered["id"].tolist(),
    format_func=lambda x: (
        f"Trade #{x} · "
        f"{filtered[filtered['id']==x]['entry_time'].iloc[0].strftime('%Y-%m-%d %H:%M')} · "
        f"${filtered[filtered['id']==x]['net_pnl'].iloc[0]:+,.2f}"
    ),
)

if selected_id:
    trade = filtered[filtered["id"] == selected_id].iloc[0]
    col_a, col_b = st.columns([1, 2])

    with col_a:
        st.markdown("##### Datos del Trade")
        st.markdown(f"**Instrumento:** {trade['instrument']}")
        st.markdown(f"**Dirección:** {trade['direction'].upper()}")
        st.markdown(f"**Cantidad:** {trade['quantity']} contratos")
        st.markdown(f"**Entrada:** {trade['entry_price']}")
        st.markdown(f"**Salida:** {trade['exit_price']}")
        st.markdown(f"**Duración:** {trade['duration_min']:.1f} min")
        st.markdown(f"**P&L Neto:** ${trade['net_pnl']:+,.2f}")
        if trade["notes"]:
            st.markdown(f"**Notas:** _{trade['notes']}_")

    with col_b:
        st.markdown("##### 🤖 Análisis Claude")
        if trade["setup_type"]:
            st.markdown(
                f"**Setup:** `{trade['setup_type']}` · "
                f"**Calidad:** {int(trade['quality_score'])}/5"
            )
            st.markdown("**Entrada:**")
            st.info(trade["entry_quality"])
            st.markdown("**Salida:**")
            st.info(trade["exit_quality"])
            st.markdown("**Lección:**")
            st.success(trade["lesson_learned"])
            st.markdown(f"**Tags:** `{trade['pattern_tags']}`")
        else:
            st.warning("Este trade aún no está analizado. Ejecuta `diary analyze`.")


# ──────────────────────────────────────────────────────────────────────────────
# SAVED SUMMARIES
# ──────────────────────────────────────────────────────────────────────────────

st.subheader("📝 Resúmenes Guardados")
summaries = load_summaries()

if summaries.empty:
    st.info(
        "Aún no hay resúmenes generados. En terminal ejecuta:\n"
        "```\ndiary summary day 2026-04-16\ndiary summary month 2026-04\n```"
    )
else:
    summary_choice = st.selectbox(
        "Selecciona un resumen:",
        options=summaries.index.tolist(),
        format_func=lambda i: (
            f"{summaries.iloc[i]['period_type'].upper()} · "
            f"{summaries.iloc[i]['period_value']} · "
            f"{summaries.iloc[i]['created_at']}"
        ),
    )
    selected = summaries.iloc[summary_choice]
    st.markdown(
        f"<div style='background:#1a1f2e;padding:24px;border-radius:10px;"
        f"border:1px solid #2a3140;'>"
        f"<h4 style='margin-top:0;color:#e8eaf0;'>"
        f"{selected['period_type'].title()} {selected['period_value']}</h4>"
        f"<div style='color:#cbd5e1;line-height:1.7;'>{selected['content']}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    "<p style='text-align:center;color:#8b9bb4;font-size:12px;'>"
    "Built with Streamlit + Claude (Anthropic) · JMG Trading 2026"
    "</p>",
    unsafe_allow_html=True,
)
