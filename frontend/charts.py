# ================================================================
# frontend/charts.py  —  Plotly Chart Library
# ================================================================

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from config.settings import PALETTE, COLOR


# ── Shared Theme ─────────────────────────────────────────────

_L = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor ="rgba(0,0,0,0)",
    font=dict(family="Inter,sans-serif", color=COLOR["text"], size=12),
    margin=dict(t=48, b=36, l=16, r=16),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
    xaxis=dict(showgrid=False, color=COLOR["muted"],
               linecolor="rgba(255,255,255,0.08)"),
    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)",
               color=COLOR["muted"]),
)

def _fig(title="", height=380):
    f = go.Figure()
    f.update_layout(
        title=dict(text=title, x=0.03, font=dict(size=14, color=COLOR["text"])),
        height=height, **_L
    )
    return f

def _empty(msg="No data"):
    f = go.Figure()
    f.add_annotation(text=msg, xref="paper", yref="paper", x=.5, y=.5,
                     showarrow=False, font=dict(size=15, color=COLOR["muted"]))
    f.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(visible=False), yaxis=dict(visible=False))
    return f

def _rgb(hex_c):
    h = hex_c.lstrip("#")
    return tuple(int(h[i:i+2],16) for i in (0,2,4))


# ── Line Chart ────────────────────────────────────────────────

def line_chart(df, x, y, title="", color=None, show_rolling=False):
    if df.empty or x not in df.columns or y not in df.columns:
        return _empty()
    c = color or PALETTE[0]
    f = _fig(title)
    r,g,b = _rgb(c)
    f.add_trace(go.Scatter(
        x=df[x], y=df[y], mode="lines",
        line=dict(color=c, width=2.5),
        fill="tozeroy", fillcolor=f"rgba({r},{g},{b},0.12)",
        name=y, hovertemplate=f"<b>%{{x}}</b><br>{y}: %{{y:,.2f}}<extra></extra>"
    ))
    if show_rolling and "rolling_7" in df.columns:
        f.add_trace(go.Scatter(
            x=df[x], y=df["rolling_7"], mode="lines",
            line=dict(color=PALETTE[1], width=1.5, dash="dot"),
            name="7-day avg"
        ))
    if show_rolling and "rolling_30" in df.columns:
        f.add_trace(go.Scatter(
            x=df[x], y=df["rolling_30"], mode="lines",
            line=dict(color=PALETTE[2], width=1.5, dash="dash"),
            name="30-day avg"
        ))
    return f


# ── Bar Chart ─────────────────────────────────────────────────

def bar_chart(df, x, y, title="", color=None, horizontal=False):
    if df.empty: return _empty()
    c = color or PALETTE[0]
    f = _fig(title)
    if horizontal:
        f.add_trace(go.Bar(
            y=df[x], x=df[y], orientation="h",
            marker=dict(color=c), text=df[y].round(0),
            texttemplate="%{text:,.0f}", textposition="outside",
            hovertemplate=f"<b>%{{y}}</b><br>{y}: %{{x:,.2f}}<extra></extra>"
        ))
    else:
        f.add_trace(go.Bar(
            x=df[x], y=df[y],
            marker=dict(color=PALETTE[:len(df)] if len(df) <= 10 else c),
            hovertemplate=f"<b>%{{x}}</b><br>{y}: %{{y:,.2f}}<extra></extra>"
        ))
    return f


# ── Multi-Line Chart ──────────────────────────────────────────

def multi_line(df, x, y_cols, title=""):
    if df.empty: return _empty()
    f = _fig(title)
    for i, col in enumerate(y_cols):
        if col in df.columns:
            c = PALETTE[i % len(PALETTE)]
            f.add_trace(go.Scatter(
                x=df[x], y=df[col], name=col, mode="lines",
                line=dict(color=c, width=2),
                hovertemplate=f"<b>%{{x}}</b><br>{col}: %{{y:,.2f}}<extra></extra>"
            ))
    return f


# ── Grouped Bar ───────────────────────────────────────────────

def grouped_bar_pivot(df, x, color_col, y, title=""):
    """Pivot df so each unique color_col becomes a bar series."""
    if df.empty: return _empty()
    try:
        pivot = df.pivot_table(index=x, columns=color_col, values=y, aggfunc="sum").reset_index()
    except Exception: return _empty("Cannot pivot data")
    f = _fig(title)
    cats = [c for c in pivot.columns if c != x]
    for i, cat in enumerate(cats):
        f.add_trace(go.Bar(
            x=pivot[x], y=pivot[cat], name=str(cat),
            marker_color=PALETTE[i % len(PALETTE)]
        ))
    f.update_layout(barmode="group")
    return f


# ── Pie / Donut ───────────────────────────────────────────────

def pie_chart(labels, values, title="", donut=True):
    if not labels: return _empty()
    f = _fig(title, height=360)
    f.add_trace(go.Pie(
        labels=labels, values=values,
        hole=0.42 if donut else 0,
        marker=dict(colors=PALETTE[:len(labels)],
                    line=dict(color=COLOR["card"], width=2)),
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>%{value:,.2f} (%{percent})<extra></extra>"
    ))
    return f


# ── Area Chart ────────────────────────────────────────────────

def area_chart(df, x, y, title="", color=None):
    if df.empty: return _empty()
    c = color or PALETTE[2]
    r,g,b = _rgb(c)
    f = _fig(title)
    f.add_trace(go.Scatter(
        x=df[x], y=df[y], mode="lines",
        line=dict(color=c, width=2),
        fill="tozeroy", fillcolor=f"rgba({r},{g},{b},0.25)",
        hovertemplate=f"<b>%{{x}}</b><br>{y}: %{{y:,.2f}}<extra></extra>"
    ))
    return f


# ── Scatter Plot ──────────────────────────────────────────────

def scatter_plot(df, x, y, color_col=None, title=""):
    if df.empty: return _empty()
    if color_col and color_col in df.columns:
        f2 = px.scatter(df, x=x, y=y, color=color_col,
                        color_discrete_sequence=PALETTE, title=title)
        f2.update_layout(**_L, height=380,
                         title=dict(text=title, x=0.03))
        return f2
    f = _fig(title)
    f.add_trace(go.Scatter(
        x=df[x], y=df[y], mode="markers",
        marker=dict(color=PALETTE[0], size=7, opacity=0.7),
        hovertemplate=f"<b>{x}</b>: %{{x}}<br><b>{y}</b>: %{{y:,.2f}}<extra></extra>"
    ))
    return f


# ── Heatmap ───────────────────────────────────────────────────

def heatmap(matrix, title=""):
    if matrix.empty: return _empty()
    f = _fig(title, height=420)
    f.add_trace(go.Heatmap(
        z=matrix.values.tolist(),
        x=list(matrix.columns),
        y=list(matrix.index),
        colorscale="Viridis",
        text=[[f"{v:.2f}" for v in row] for row in matrix.values],
        texttemplate="%{text}",
        showscale=True,
        hovertemplate="%{y} vs %{x}: %{z:.3f}<extra></extra>"
    ))
    f.update_layout(margin=dict(t=60, b=80, l=80, r=20))
    return f


# ── Forecast Chart ────────────────────────────────────────────

def forecast_chart(hist_df, forecast_df, title="Sales Forecast"):
    """
    Combines historical actuals + ML forecast on one chart.
    hist_df   : columns [date, sales]
    forecast_df: columns [date, forecast]
    """
    f = _fig(title, height=420)

    if not hist_df.empty:
        f.add_trace(go.Scatter(
            x=hist_df["date"], y=hist_df["sales"],
            mode="lines", name="Historical",
            line=dict(color=PALETTE[0], width=2.5),
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Actual: $%{y:,.2f}<extra></extra>"
        ))

    if not forecast_df.empty:
        # Bridge from last actual to first forecast
        if not hist_df.empty:
            bridge_x = [hist_df["date"].iloc[-1]] + list(forecast_df["date"])
            bridge_y = [float(hist_df["sales"].iloc[-1])] + list(forecast_df["forecast"])
        else:
            bridge_x = list(forecast_df["date"])
            bridge_y = list(forecast_df["forecast"])

        f.add_trace(go.Scatter(
            x=bridge_x, y=bridge_y,
            mode="lines+markers", name="Forecast",
            line=dict(color=PALETTE[3], width=2, dash="dash"),
            marker=dict(size=6, symbol="diamond"),
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>Forecast: $%{y:,.2f}<extra></extra>"
        ))

        # Confidence band (±15%)
        upper = [v * 1.15 for v in bridge_y]
        lower = [max(0, v * 0.85) for v in bridge_y]
        r,g,b = _rgb(PALETTE[3])
        f.add_trace(go.Scatter(
            x=bridge_x + bridge_x[::-1],
            y=upper + lower[::-1],
            fill="toself", fillcolor=f"rgba({r},{g},{b},0.1)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Confidence Band", showlegend=True
        ))

    if not hist_df.empty:
        f.add_vline(
            x=str(hist_df["date"].iloc[-1]),
            line=dict(color="rgba(255,255,255,0.25)", dash="dot", width=1)
        )
    f.update_layout(legend=dict(x=0.01, y=0.99, orientation="h"))
    return f


# ── Model Comparison Bar ──────────────────────────────────────

def model_comparison_chart(metrics_list, metric="rmse"):
    """
    metrics_list: list of {model_name, mae, rmse, r2, mape}
    """
    if not metrics_list: return _empty()
    df = pd.DataFrame(metrics_list)
    f  = _fig(f"Model Comparison — {metric.upper()}", height=320)
    best_idx = df[metric].idxmin() if metric != "r2" else df[metric].idxmax()
    colors   = [COLOR["success"] if i == best_idx else PALETTE[0]
                for i in range(len(df))]
    f.add_trace(go.Bar(
        x=df["model_name"], y=df[metric],
        marker=dict(color=colors),
        text=df[metric].round(3),
        texttemplate="%{text}", textposition="outside",
        hovertemplate="<b>%{x}</b><br>" + metric.upper() + ": %{y:.4f}<extra></extra>"
    ))
    return f


# ── Gauge ─────────────────────────────────────────────────────

def gauge_chart(value, max_val, title="", unit=""):
    pct = min(value / max_val * 100, 150) if max_val > 0 else 0
    bar_c = (COLOR["success"] if pct < 70 else
             COLOR["warning"] if pct < 90 else COLOR["danger"])
    f = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number=dict(suffix=unit, font=dict(size=26, color=COLOR["text"])),
        title=dict(text=title, font=dict(size=12, color=COLOR["muted"])),
        gauge=dict(
            axis=dict(range=[0, max_val]),
            bar=dict(color=bar_c, thickness=0.7),
            bgcolor="rgba(255,255,255,0.04)",
            borderwidth=1, bordercolor="rgba(255,255,255,0.1)",
        )
    ))
    f.update_layout(height=240, paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color=COLOR["text"]),
                    margin=dict(t=36, b=16, l=24, r=24))
    return f
