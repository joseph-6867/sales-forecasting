# ================================================================
# services/data_processor.py  —  Data Validation & Feature Engineering
# ================================================================

import numpy as np
import pandas as pd
from utils.helpers import detect_column, num_cols, cat_cols, coerce_date


# ── Data Validation ───────────────────────────────────────────

def validate_dataset(df, date_col=None, sales_col=None):
    """
    Run full data quality checks.
    Returns a validation_report dict with issues and a 0-100 quality score.
    """
    issues   = []
    warnings = []
    score    = 100.0
    n        = len(df)

    # 1. Missing values
    missing_total = int(df.isnull().sum().sum())
    missing_pct   = missing_total / max(df.size, 1) * 100
    if missing_pct > 20:
        issues.append(f"High missing data: {missing_pct:.1f}% of all values are null.")
        score -= 20
    elif missing_pct > 5:
        warnings.append(f"Moderate missing data: {missing_pct:.1f}%.")
        score -= 10

    # Per-column missing
    col_missing = df.isnull().sum()
    col_missing = col_missing[col_missing > 0].to_dict()

    # 2. Duplicates
    dup_count = int(df.duplicated().sum())
    dup_pct   = dup_count / max(n, 1) * 100
    if dup_pct > 10:
        issues.append(f"High duplicates: {dup_count} rows ({dup_pct:.1f}%).")
        score -= 15
    elif dup_pct > 2:
        warnings.append(f"{dup_count} duplicate rows ({dup_pct:.1f}%).")
        score -= 5

    # 3. Date column
    date_ok = False
    if date_col and date_col in df.columns:
        parsed = pd.to_datetime(df[date_col], errors="coerce")
        bad    = int(parsed.isnull().sum())
        if bad > 0:
            issues.append(f"Date column '{date_col}': {bad} unparseable values.")
            score -= 10
        else:
            date_ok = True
    else:
        issues.append("No date column identified — time-series analysis unavailable.")
        score -= 15

    # 4. Sales column
    sales_ok = False
    if sales_col and sales_col in df.columns:
        s = pd.to_numeric(df[sales_col], errors="coerce")
        neg = int((s < 0).sum())
        if neg > 0:
            warnings.append(f"Sales column has {neg} negative values.")
            score -= 5
        sales_ok = True
    else:
        issues.append("No sales/revenue column identified.")
        score -= 10

    # 5. Outliers (IQR on numeric columns)
    outlier_info = {}
    for c in num_cols(df)[:5]:
        col_data = pd.to_numeric(df[c], errors="coerce").dropna()
        if len(col_data) < 10:
            continue
        q1, q3   = col_data.quantile(0.25), col_data.quantile(0.75)
        iqr      = q3 - q1
        outliers = int(((col_data < q1 - 3*iqr) | (col_data > q3 + 3*iqr)).sum())
        if outliers > 0:
            outlier_info[c] = outliers

    if outlier_info:
        warnings.append(f"Outliers detected in: {', '.join(outlier_info.keys())}")
        score -= min(10, len(outlier_info) * 2)

    # 6. Minimum rows
    if n < 30:
        issues.append(f"Very small dataset ({n} rows) — forecasting may be unreliable.")
        score -= 20
    elif n < 100:
        warnings.append(f"Small dataset ({n} rows) — more data improves forecasts.")
        score -= 5

    score = max(0, min(100, score))

    return {
        "score":        round(score, 1),
        "issues":       issues,
        "warnings":     warnings,
        "missing_total":missing_total,
        "missing_pct":  round(missing_pct, 2),
        "col_missing":  col_missing,
        "duplicates":   dup_count,
        "outliers":     outlier_info,
        "date_ok":      date_ok,
        "sales_ok":     sales_ok,
        "n_rows":       n,
    }


def clean_dataset(df, date_col=None, sales_col=None):
    """
    Auto-clean dataset:
      - Drop full-duplicate rows
      - Fill numeric NaN with median
      - Fill string NaN with 'Unknown'
      - Coerce date column
    Returns cleaned DataFrame + change log.
    """
    changes = []
    df = df.copy()

    # Drop duplicates
    before = len(df)
    df = df.drop_duplicates()
    dropped = before - len(df)
    if dropped > 0:
        changes.append(f"Removed {dropped} duplicate rows.")

    # Fill numeric
    for c in num_cols(df):
        nulls = int(df[c].isnull().sum())
        if nulls > 0:
            df[c] = df[c].fillna(df[c].median())
            changes.append(f"Filled {nulls} NaN in '{c}' with median.")

    # Fill string
    for c in cat_cols(df):
        nulls = int(df[c].isnull().sum())
        if nulls > 0:
            df[c] = df[c].fillna("Unknown")
            changes.append(f"Filled {nulls} NaN in '{c}' with 'Unknown'.")

    # Coerce date
    if date_col and date_col in df.columns:
        before = len(df)
        df = coerce_date(df, date_col)
        dropped_d = before - len(df)
        if dropped_d > 0:
            changes.append(f"Dropped {dropped_d} rows with unparseable dates.")

    # Remove negative sales
    if sales_col and sales_col in df.columns:
        df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce").fillna(0)
        neg = int((df[sales_col] < 0).sum())
        if neg > 0:
            df[sales_col] = df[sales_col].clip(lower=0)
            changes.append(f"Clipped {neg} negative sales values to 0.")

    return df, changes


# ── Feature Engineering ───────────────────────────────────────

def engineer_features(df, date_col, sales_col, lag_periods=None, roll_windows=None):
    """
    Auto-generate time-based and lag features for ML.

    Generated features:
      year, month, quarter, week_num, day_of_week,
      lag_1 … lag_N, rolling_mean_W, rolling_std_W
    """
    if lag_periods  is None: lag_periods  = [1, 7, 14, 30]
    if roll_windows is None: roll_windows = [7, 14, 30]

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).reset_index(drop=True)

    # Aggregate to daily totals if not already
    daily = (df.groupby(date_col)[sales_col]
               .sum()
               .reset_index()
               .rename(columns={sales_col: "daily_sales"}))

    daily[date_col] = pd.to_datetime(daily[date_col])
    daily = daily.sort_values(date_col).reset_index(drop=True)

    # Calendar features
    daily["year"]        = daily[date_col].dt.year
    daily["month"]       = daily[date_col].dt.month
    daily["quarter"]     = daily[date_col].dt.quarter
    daily["week_num"]    = daily[date_col].dt.isocalendar().week.astype(int)
    daily["day_of_week"] = daily[date_col].dt.dayofweek   # 0=Mon
    daily["is_weekend"]  = (daily["day_of_week"] >= 5).astype(int)
    daily["day_of_year"] = daily[date_col].dt.dayofyear

    # Lag features
    for lag in lag_periods:
        daily[f"lag_{lag}"] = daily["daily_sales"].shift(lag)

    # Rolling features
    for w in roll_windows:
        daily[f"rolling_mean_{w}"] = (
            daily["daily_sales"].shift(1).rolling(w, min_periods=1).mean()
        )
        daily[f"rolling_std_{w}"]  = (
            daily["daily_sales"].shift(1).rolling(w, min_periods=1).std().fillna(0)
        )

    daily = daily.dropna().reset_index(drop=True)
    return daily


def get_feature_cols(daily_df, date_col):
    """Return list of feature column names (exclude date + target)."""
    exclude = {date_col, "daily_sales"}
    return [c for c in daily_df.columns if c not in exclude]
