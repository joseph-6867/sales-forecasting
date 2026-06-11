# ================================================================
# app.py — Main Entry Point
# ================================================================

import time
import streamlit as st

st.set_page_config(
    page_title="Sales Forecasting Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "# Sales Forecasting Platform v1.0"},
)

_DEFAULTS = {
    "authenticated": False, "user_id": None, "email": None, "full_name": None,
    "role": "analyst", "jwt_token": None, "demo_mode": False, "current_page": "home",
    "active_project": None, "active_df": None, "col_map": {}, "register_cooldown": 0,
    "trained_models": None, "forecast_results": {}, "_kpis": None, "_seasonal": None,
    "_monthly": None, "_daily": None, "_daily_eng": None, "_feat_cols": None, "_best_model": None,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

from backend.auth import (
    init_session, is_auth, auth_register, auth_login,
    auth_forgot_password, auth_google_login_url, auth_handle_google_callback,
)
from frontend.dashboard import render_dashboard

init_session()


def _google_button(label: str):
    try:
        google_url = auth_google_login_url()
    except Exception as exc:
        st.error(f"**Google OAuth unavailable** — `{exc}`")
        return
    try:
        st.link_button(f"🔵  {label}", url=google_url, use_container_width=True)
    except AttributeError:
        import html as _html
        safe_url = _html.escape(google_url, quote=True)
        st.markdown(
            f'<a href="{safe_url}" target="_self" style="text-decoration:none;display:block">'
            f'<div style="padding:10px;background:#fff;border:1px solid #dadce0;border-radius:6px;'
            f'text-align:center;font-family:sans-serif;color:#3c4043;">🔵 {label}</div></a>',
            unsafe_allow_html=True,
        )


def _auth_page():
    # ── Handle Google OAuth callback ──────────────────────────────
    # auth_handle_google_callback() uses streamlit-url-fragment to read
    # the #access_token= hash from the URL — the ONLY reliable way to
    # do this in Streamlit. Must run before any other UI is rendered.
    if auth_handle_google_callback():
        st.rerun()

    st.markdown(
        """
        <div style="text-align:center;padding:36px 0 20px">
            <h1 style="font-size:2.6rem;margin:0">📊 Sales Forecasting Platform</h1>
            <p style="color:#94A3B8;font-size:1.1rem;margin-top:8px">
                Intelligent Business Analytics & ML-Powered Sales Prediction
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    left, right = st.columns([3, 2], gap="large")

    with left:
        st.subheader("🚀 What you get")
        cols = st.columns(2)
        features = [
            ("📤", "Upload CSV/Excel",   "Auto-detects sales, date, product, region columns"),
            ("📈", "Trend Analytics",    "Daily, weekly, monthly, yearly breakdowns"),
            ("🔮", "ML Forecasting",     "Linear Regression, Random Forest, XGBoost"),
            ("🌟", "Seasonal Insights",  "Best/worst months, quarterly & day-of-week patterns"),
            ("📦", "Product Analysis",   "Top products, revenue share, trend comparison"),
            ("🗺️", "Region Analysis",    "Regional breakdown and performance comparison"),
            ("🧠", "AI Recommendations", "Inventory, demand, and revenue suggestions"),
            ("🎮", "Scenario Simulator", "Test growth, demand & discount scenarios"),
            ("📋", "Reports",            "Download PDF, Excel, and CSV reports"),
            ("👑", "Role-Based Access",  "Admin and Business Analyst roles"),
        ]
        for i, (icon, title, desc) in enumerate(features):
            cols[i % 2].info(f"**{icon} {title}**\n\n{desc}")

    with right:
        tab_login, tab_register, tab_forgot = st.tabs(["🔑 Log In", "📝 Register", "🔒 Forgot Password"])

        with tab_login:
            _google_button("Sign in with Google")
            st.divider()
            with st.form("login_form"):
                st.subheader("Sign in with Email")
                email    = st.text_input("Email",    placeholder="you@example.com")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log In", use_container_width=True, type="primary")
            if submitted:
                if not email or not password:
                    st.error("Please fill in both fields.")
                else:
                    with st.spinner("Signing in…"):
                        ok, result = auth_login(email, password)
                    msg = result["message"] if isinstance(result, dict) else result
                    if ok: st.success(msg); st.rerun()
                    else:  st.error(msg)
            st.divider()
            if st.button("🎮 Try Demo (no login)", use_container_width=True):
                st.session_state.update({
                    "authenticated": True, "user_id": "demo-user",
                    "email": "demo@platform.local", "full_name": "Demo User",
                    "role": "analyst", "jwt_token": "demo-token",
                    "demo_mode": True, "current_page": "home",
                })
                st.rerun()

        with tab_register:
            _google_button("Sign up with Google")
            st.divider()
            cooldown  = st.session_state.get("register_cooldown", 0)
            secs_left = max(0, int(cooldown - time.time()))
            if secs_left > 0:
                st.warning(f"Please wait {secs_left} seconds before trying again.")
            with st.form("register_form"):
                st.subheader("Create account with Email")
                reg_name  = st.text_input("Full Name",              placeholder="Jane Smith")
                reg_email = st.text_input("Email",                  placeholder="you@example.com")
                reg_role  = st.selectbox("Role",                    ["analyst", "admin"])
                reg_pass  = st.text_input("Password (min 6 chars)", type="password")
                reg_pass2 = st.text_input("Confirm Password",       type="password")
                reg_sub   = st.form_submit_button(
                    "Create Account", use_container_width=True,
                    type="primary", disabled=(secs_left > 0),
                )
            if reg_sub:
                if not all([reg_name, reg_email, reg_pass, reg_pass2]):
                    st.error("All fields are required.")
                elif reg_pass != reg_pass2:
                    st.error("Passwords do not match.")
                elif len(reg_pass) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    with st.spinner("Creating account…"):
                        ok, result = auth_register(reg_email, reg_pass, reg_name, reg_role)
                    msg = result["message"] if isinstance(result, dict) else result
                    if ok:
                        st.success(msg)
                        if result.get("auto_login"): st.rerun()
                    else:
                        st.error(msg)

        with tab_forgot:
            with st.form("forgot_form"):
                st.subheader("Reset Password")
                fp_email = st.text_input("Email", placeholder="you@example.com")
                fp_sub   = st.form_submit_button("Send Reset Email", use_container_width=True)
            if fp_sub:
                if not fp_email: st.error("Please enter your email.")
                else:
                    ok, msg = auth_forgot_password(fp_email)
                    if ok: st.success(msg)
                    else:  st.error(msg)


def main():
    if is_auth():
        render_dashboard()
    else:
        _auth_page()


if __name__ == "__main__":
    main()
else:
    main()
