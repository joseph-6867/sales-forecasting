# ================================================================
# services/analytics.py  —  Business Analytics Engine
# ================================================================
# Provides: trend analysis, seasonal, product, region,
#           KPI summaries, insights, recommendations
# ================================================================

import numpy as np
import pandas as pd
from utils.helpers import safe_div, fmt_currency, fmt_pct, fmt_num


# ── KPI Summary ───────────────────────────────────────────────

def compute_kpis(df, date_col, sales_col):
    """
    Compute top-level KPI cards.
    Returns dict of metric_name -> value.
    """
    df = df.copy()
    df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce").fillna(0)
    df[date_col]  = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    total    = float(df[sales_col].sum())
    avg      = float(df[sales_col].mean())
    mx       = float(df[sales_col].max())
    mn       = float(df[sales_col].min())
    tx_count = len(df)

    # Growth: compare last 30 days vs prior 30 days
    latest  = df[date_col].max()
    cut30   = latest - pd.Timedelta(days=30)
    cut60   = latest - pd.Timedelta(days=60)
    last30  = float(df[df[date_col] >= cut30][sales_col].sum())
    prev30  = float(df[(df[date_col] >= cut60) & (df[date_col] < cut30)][sales_col].sum())
    growth  = safe_div(last30 - prev30, prev30) * 100

    # Daily aggregation for stats
    daily = df.groupby(date_col)[sales_col].sum()
    date_range = f"{df[date_col].min().strftime('%Y-%m-%d')} → {df[date_col].max().strftime('%Y-%m-%d')}"

    return {
        "total_sales":      total,
        "avg_sales":        avg,
        "max_sales":        mx,
        "min_sales":        mn,
        "transactions":     tx_count,
        "growth_pct":       round(growth, 2),
        "last_30_sales":    last30,
        "prev_30_sales":    prev30,
        "date_range":       date_range,
        "total_days":       int((df[date_col].max() - df[date_col].min()).days) + 1,
    }


# ── Trend Analysis ────────────────────────────────────────────

def daily_trend(df, date_col, sales_col):
    df = df.copy()
    df[date_col]  = pd.to_datetime(df[date_col])
    df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce").fillna(0)
    daily = df.groupby(date_col)[sales_col].sum().reset_index()
    daily.columns = ["date", "sales"]
    daily["rolling_7"]  = daily["sales"].rolling(7,  min_periods=1).mean()
    daily["rolling_30"] = daily["sales"].rolling(30, min_periods=1).mean()
    return daily.sort_values("date")

def weekly_trend(df, date_col, sales_col):
    df = df.copy()
    df[date_col]  = pd.to_datetime(df[date_col])
    df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce").fillna(0)
    df["week"] = df[date_col].dt.to_period("W").astype(str)
    weekly = df.groupby("week")[sales_col].sum().reset_index()
    weekly.columns = ["week", "sales"]
    return weekly

def monthly_trend(df, date_col, sales_col):
    df = df.copy()
    df[date_col]  = pd.to_datetime(df[date_col])
    df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce").fillna(0)
    df["month"] = df[date_col].dt.to_period("M").astype(str)
    monthly = df.groupby("month")[sales_col].sum().reset_index()
    monthly.columns = ["month", "sales"]
    return monthly

def yearly_trend(df, date_col, sales_col):
    df = df.copy()
    df[date_col]  = pd.to_datetime(df[date_col])
    df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce").fillna(0)
    df["year"] = df[date_col].dt.year
    yearly = df.groupby("year")[sales_col].sum().reset_index()
    yearly.columns = ["year", "sales"]
    return yearly


# ── Seasonal Analysis ─────────────────────────────────────────

def seasonal_analysis(df, date_col, sales_col):
    df = df.copy()
    df[date_col]  = pd.to_datetime(df[date_col])
    df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce").fillna(0)

    df["month_name"] = df[date_col].dt.strftime("%b")
    df["month_num"]  = df[date_col].dt.month
    df["quarter"]    = df[date_col].dt.quarter
    df["year"]       = df[date_col].dt.year

    # Monthly average
    by_month = (df.groupby(["month_num","month_name"])[sales_col]
                  .mean().reset_index()
                  .sort_values("month_num"))
    by_month.columns = ["month_num","month","avg_sales"]

    best_month  = by_month.loc[by_month["avg_sales"].idxmax(), "month"]
    worst_month = by_month.loc[by_month["avg_sales"].idxmin(), "month"]

    # Quarterly
    by_quarter = df.groupby("quarter")[sales_col].sum().reset_index()
    by_quarter.columns = ["quarter","sales"]
    by_quarter["quarter_label"] = by_quarter["quarter"].map(
        {1:"Q1 (Jan-Mar)", 2:"Q2 (Apr-Jun)",
         3:"Q3 (Jul-Sep)", 4:"Q4 (Oct-Dec)"}
    )

    # Day of week
    df["dow"]      = df[date_col].dt.dayofweek
    df["dow_name"] = df[date_col].dt.strftime("%a")
    by_dow = (df.groupby(["dow","dow_name"])[sales_col]
                .mean().reset_index().sort_values("dow"))
    by_dow.columns = ["dow","day","avg_sales"]

    return {
        "by_month":   by_month,
        "best_month": best_month,
        "worst_month":worst_month,
        "by_quarter": by_quarter,
        "by_dow":     by_dow,
    }


# ── Product Analysis ──────────────────────────────────────────

def product_analysis(df, date_col, sales_col, product_col):
    df = df.copy()
    df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce").fillna(0)
    df[date_col]  = pd.to_datetime(df[date_col])

    # Top products by total sales
    by_product = (df.groupby(product_col)[sales_col]
                    .agg(["sum","mean","count"])
                    .reset_index()
                    .rename(columns={"sum":"total","mean":"avg","count":"transactions"}))
    by_product = by_product.sort_values("total", ascending=False)
    total_rev = by_product["total"].sum()
    by_product["share_pct"] = (by_product["total"] / total_rev * 100).round(2)

    # Monthly trend per product (top 5)
    top5 = list(by_product[product_col].head(5))
    df["month"] = df[date_col].dt.to_period("M").astype(str)
    prod_trend = (df[df[product_col].isin(top5)]
                    .groupby(["month", product_col])[sales_col]
                    .sum().reset_index())
    prod_trend.columns = ["month","product","sales"]

    return {
        "by_product":  by_product,
        "top5":        top5,
        "prod_trend":  prod_trend,
        "total_rev":   total_rev,
    }


# ── Region Analysis ───────────────────────────────────────────

def region_analysis(df, date_col, sales_col, region_col):
    df = df.copy()
    df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce").fillna(0)
    df[date_col]  = pd.to_datetime(df[date_col])

    by_region = (df.groupby(region_col)[sales_col]
                   .agg(["sum","mean","count"])
                   .reset_index()
                   .rename(columns={"sum":"total","mean":"avg","count":"transactions"}))
    by_region = by_region.sort_values("total", ascending=False)
    total_rev = by_region["total"].sum()
    by_region["share_pct"] = (by_region["total"] / total_rev * 100).round(2)

    # Monthly trend per region
    df["month"] = df[date_col].dt.to_period("M").astype(str)
    reg_trend = (df.groupby(["month", region_col])[sales_col]
                   .sum().reset_index())
    reg_trend.columns = ["month","region","sales"]

    return {
        "by_region": by_region,
        "reg_trend": reg_trend,
        "total_rev": total_rev,
    }


# ── Business Insights ─────────────────────────────────────────

def generate_insights(df, date_col, sales_col, kpis, seasonal):
    """Return a list of auto-generated insight strings."""
    insights = []
    growth = kpis.get("growth_pct", 0)

    # Growth trend
    if growth > 10:
        insights.append(f"📈 **Strong growth**: Sales increased by {growth:.1f}% over the last 30 days.")
    elif growth > 0:
        insights.append(f"📈 **Moderate growth**: Sales up {growth:.1f}% vs prior 30 days.")
    elif growth < -10:
        insights.append(f"📉 **Sales decline**: Revenue dropped {abs(growth):.1f}% — urgent attention needed.")
    else:
        insights.append(f"➡️ **Stable sales**: Minimal change ({growth:.1f}%) in the last 30 days.")

    # Seasonal
    bm = seasonal.get("best_month")
    wm = seasonal.get("worst_month")
    if bm: insights.append(f"🌟 **Peak month**: {bm} consistently shows the highest average sales.")
    if wm: insights.append(f"⚠️ **Low month**: {wm} is historically the weakest month — consider promotions.")

    # Volume
    total = kpis.get("total_sales", 0)
    tx    = kpis.get("transactions", 0)
    avg   = kpis.get("avg_sales", 0)
    insights.append(f"💰 **Total revenue**: {fmt_currency(total)} across {tx:,} transactions (avg {fmt_currency(avg)}).")

    # Day of week
    by_dow = seasonal.get("by_dow", pd.DataFrame())
    if not by_dow.empty:
        best_day  = by_dow.loc[by_dow["avg_sales"].idxmax(), "day"]
        worst_day = by_dow.loc[by_dow["avg_sales"].idxmin(), "day"]
        insights.append(f"📅 **Best day**: {best_day} drives the most sales; **{worst_day}** is the slowest.")

    return insights


# ── AI Recommendations ────────────────────────────────────────

def generate_recommendations(kpis, seasonal, product_res, region_res):
    """Return a list of actionable recommendation strings."""
    recs = []
    growth = kpis.get("growth_pct", 0)

    # Inventory
    by_month = seasonal.get("by_month", pd.DataFrame())
    if not by_month.empty:
        peak_month = by_month.loc[by_month["avg_sales"].idxmax(), "month"]
        recs.append(f"📦 **Inventory Planning**: Stock up at least 4 weeks before {peak_month} to meet peak demand.")

    # Demand alert
    if growth > 15:
        recs.append("🚨 **Demand Alert**: Rapid sales growth detected — review stock levels and supplier lead times immediately.")
    elif growth < -10:
        recs.append("💡 **Demand Drop**: Consider running promotional campaigns or discounts to stimulate demand.")

    # Revenue
    recs.append("💡 **Revenue Tip**: Bundle low-performing products with top sellers to increase average order value.")

    # Regional
    if region_res:
        by_region = region_res.get("by_region", pd.DataFrame())
        if not by_region.empty and len(by_region) > 1:
            top_reg  = by_region.iloc[0]["region"] if "region" in by_region.columns else by_region.iloc[0, 0]
            low_reg  = by_region.iloc[-1]["region"] if "region" in by_region.columns else by_region.iloc[-1, 0]
            recs.append(f"🗺️ **Regional**: Replicate {top_reg}'s strategy in {low_reg} to boost under-performing region.")

    # Product
    if product_res:
        by_prod = product_res.get("by_product", pd.DataFrame())
        if not by_prod.empty and "share_pct" in by_prod.columns:
            top_share = float(by_prod["share_pct"].iloc[0])
            if top_share > 40:
                prod_name = by_prod.iloc[0, 0]
                recs.append(f"⚡ **Concentration Risk**: '{prod_name}' drives {top_share:.0f}% of revenue — diversify product mix.")

    recs.append("📊 **Forecasting**: Use the ML Forecasting module to plan resources for the next quarter.")
    return recs


# ── Scenario Simulator ────────────────────────────────────────

def run_scenario(baseline_forecast, growth_pct=0, demand_change=0, discount_pct=0):
    """
    Adjust a forecast DataFrame by scenario parameters.
    Returns modified forecast with scenario_sales column.
    """
    df = baseline_forecast.copy()
    multiplier = (1 + growth_pct/100) * (1 + demand_change/100) * (1 - discount_pct/100)
    df["scenario_sales"] = (df["forecast"] * multiplier).round(2).clip(lower=0)
    df["difference"]     = (df["scenario_sales"] - df["forecast"]).round(2)
    df["diff_pct"]       = ((df["difference"] / df["forecast"].replace(0, np.nan)) * 100).round(2)
    return df
