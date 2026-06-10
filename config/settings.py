# ================================================================
# config/settings.py  —  Global App Configuration
# ================================================================

import os
from dotenv import load_dotenv

load_dotenv()

try:
    import streamlit as st
except Exception:
    st = None


def _env(key: str, default: str = "") -> str:
    try:
        if st is not None and hasattr(st, "secrets"):
            if key in st.secrets:
                return st.secrets[key]
    except (FileNotFoundError, Exception):
        pass
    return os.getenv(key, default)


# ── Supabase ──────────────────────────────────────────────────
SUPABASE_URL              = _env("SUPABASE_URL", "")
SUPABASE_ANON_KEY         = _env("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = _env("SUPABASE_SERVICE_ROLE_KEY", "")

# ── App ───────────────────────────────────────────────────────
APP_NAME              = os.getenv("APP_NAME", "Sales Forecasting Platform")
APP_VERSION           = os.getenv("APP_VERSION", "1.0.0")
DEBUG                 = os.getenv("DEBUG", "false").lower() == "true"
JWT_SECRET            = _env("JWT_SECRET", "dev-secret-key-change-in-production")
SHARED_EMAIL_BASE     = _env("SHARED_EMAIL_BASE", "")
GOOGLE_CLIENT_ID      = _env("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET  = _env("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI   = _env("GOOGLE_REDIRECT_URI", "https://deploy-financial66.streamlit.app/1")

# ── ML ────────────────────────────────────────────────────────
FORECAST_HORIZONS = {
    "Next 7 Days":   7,
    "Next 30 Days":  30,
    "Next 90 Days":  90,
    "Next 6 Months": 180,
}

MODEL_NAMES = ["Linear Regression", "Random Forest", "Gradient Boosting"]

# ── UI Palette ────────────────────────────────────────────────
PALETTE = [
    "#6366F1", "#8B5CF6", "#10B981", "#F59E0B",
    "#EF4444", "#3B82F6", "#EC4899", "#14B8A6",
    "#F97316", "#84CC16",
]

COLOR = {
    "primary":  "#6366F1",
    "success":  "#10B981",
    "warning":  "#F59E0B",
    "danger":   "#EF4444",
    "info":     "#3B82F6",
    "bg":       "#0F172A",
    "card":     "#1E293B",
    "border":   "#334155",
    "text":     "#F1F5F9",
    "muted":    "#94A3B8",
}

# ── Demo dataset column defaults ─────────────────────────────
DEMO_DATE_COL    = "date"
DEMO_SALES_COL   = "sales"
DEMO_PRODUCT_COL = "product"
DEMO_REGION_COL  = "region"
