# ================================================================
# utils/helpers.py  —  Shared Utility Functions
# ================================================================

import io
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from config.settings import PALETTE, COLOR


# ── Number Formatters ─────────────────────────────────────────

def fmt_num(n, decimals=0):
    """Format large number with K/M suffix."""
    try:
        n = float(n)
        if n >= 1_000_000: return f"{n/1_000_000:.2f}M"
        if n >= 1_000:      return f"{n/1_000:.1f}K"
        return f"{n:,.{decimals}f}"
    except: return str(n)

def fmt_currency(n, symbol="$"):
    try:
        n = float(n)
        if n >= 1_000_000: return f"{symbol}{n/1_000_000:.2f}M"
        if n >= 1_000:      return f"{symbol}{n/1_000:.1f}K"
        return f"{symbol}{n:,.2f}"
    except: return f"{symbol}{n}"

def fmt_pct(n, decimals=1):
    try:
        n = float(n)
        if 0 <= n <= 1: n *= 100
        return f"{n:.{decimals}f}%"
    except: return str(n)

def delta_str(curr, prev):
    """Return (delta_label, delta_color) for st.metric."""
    try:
        curr, prev = float(curr), float(prev)
        if prev == 0: return "N/A", "off"
        pct = (curr - prev) / abs(prev) * 100
        sign = "+" if pct >= 0 else ""
        col  = "normal" if pct >= 0 else "inverse"
        return f"{sign}{pct:.1f}%", col
    except: return "N/A", "off"

def safe_div(a, b, default=0.0):
    return a / b if b != 0 else default


# ── File I/O ──────────────────────────────────────────────────

def read_uploaded_file(uploaded):
    """
    Read Streamlit UploadedFile (CSV or Excel) → DataFrame.
    Returns (df, error_string).
    Normalises column names to lowercase with underscores.
    """
    if uploaded is None:
        return None, "No file provided."
    try:
        name = uploaded.name.lower()
        if name.endswith(".csv"):
            # Try common encodings (utf-8 first, then Windows-1252 / latin1)
            encodings = ["utf-8", "cp1252", "latin1"]
            last_exc = None
            for enc in encodings:
                try:
                    try:
                        uploaded.seek(0)
                    except Exception:
                        pass
                    df = pd.read_csv(uploaded, encoding=enc)
                    last_exc = None
                    break
                except Exception as e:
                    last_exc = e
                    continue
            if last_exc:
                # Final attempt without specifying encoding (let pandas choose),
                # but ensure file pointer reset first.
                try:
                    uploaded.seek(0)
                except Exception:
                    pass
                df = pd.read_csv(uploaded)
        elif name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(uploaded)
        else:
            return None, "Only CSV and Excel files are supported."
        if df.empty:
            return None, "File is empty."
        df.columns = [
            str(c).strip().lower().replace(" ", "_").replace("-", "_")
            for c in df.columns
        ]
        return df, ""
    except Exception as e:
        return None, f"Could not read file: {e}"

def to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")

def to_excel_bytes(df, sheet="Data"):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name=sheet)
    return buf.getvalue()


# ── Column Auto-Detection ─────────────────────────────────────

_COL_HINTS = {
    "date":    ["date","time","period","month","week","day","created"],
    "sales":   ["sales","revenue","amount","income","gmv","value","total"],
    "product": ["product","item","sku","category","name","goods"],
    "region":  ["region","state","city","country","area","location","zone"],
    "qty":     ["qty","quantity","units","count","volume"],
}

def detect_column(df, col_type):
    """Return first column whose name contains a keyword for col_type."""
    hints = _COL_HINTS.get(col_type, [])
    for c in df.columns:
        cl = c.lower()
        if any(h in cl for h in hints):
            return c
    return None

def num_cols(df):
    return df.select_dtypes(include=[np.number]).columns.tolist()

def cat_cols(df):
    return df.select_dtypes(include=["object","category"]).columns.tolist()


# ── DataFrame Helpers ─────────────────────────────────────────

def coerce_date(df, col):
    df = df.copy()
    df[col] = pd.to_datetime(df[col], errors="coerce")
    return df.dropna(subset=[col])

def df_summary(df):
    return {
        "rows":        len(df),
        "columns":     len(df.columns),
        "numeric":     len(num_cols(df)),
        "categorical": len(cat_cols(df)),
        "missing":     int(df.isnull().sum().sum()),
        "duplicates":  int(df.duplicated().sum()),
        "memory_kb":   round(df.memory_usage(deep=True).sum()/1024, 1),
    }

def now_str():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
