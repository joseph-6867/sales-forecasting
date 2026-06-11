# ================================================================
# app.py — Main Entry Point
# ================================================================

import time
import streamlit as st

# ── MUST be first Streamlit call ─────────────────────────────────
st.set_page_config(
    page_title="Sales Forecasting Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "# Sales Forecasting Platform v1.0"},
)

# ── Initialize ALL session state keys BEFORE any imports ─────────
_DEFAULTS = {
    "authenticated":     False,
    "user_id":           None,
    "email":             None,
    "full_name":         None,
    "role":              "analyst",
    "jwt_token":         None,
    "demo_mode":         False,
    "current_page":      "home",
    # Dashboard keys
    "active_project":    None,
    "active_df":         None,
    "col_map":           {},
    # Misc
    "register_cooldown": 0,
    "trained_models":    None,
    "forecast_results":  {},
    "_kpis":             None,
    "_seasonal":         None,
    "_monthly":          None,
    "_daily":            None,
    "_daily_eng":        None,
    "_feat_cols":        None,
    "_best_model":       None,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

from backend.auth import (
    init_session,
    is_auth,
    auth_register,
    auth_login,
    auth_forgot_password,
    auth_google_login_url,
    auth_handle_google_callback,
)
from frontend.dashboard import render_dashboard

init_session()

# ================================================================
# GOOGLE BUTTON HELPER
# ================================================================

def _google_button(label: str):
    """
    Renders the Google OAuth button using st.link_button.
    """
    try:
        google_url = auth_google_login_url()
    except Exception as exc:
        st.error(
            f"**Google OAuth unavailable** — `{exc}`\n\n"
            "Check that `SUPABASE_URL` and `SUPABASE_ANON_KEY` are set in "
            "Streamlit Cloud → App settings → Secrets."
        )
        return

    try:
        st.link_button(f"🔵  {label}", url=google_url, use_container_width=True)
    except AttributeError:
        import html as _html
        safe_url = _html.escape(google_url, quote=True)
        st.markdown(
            f'<a href="{safe_url}" target="_self" style="text-decoration:none;display:block">'
            f'<div style="display:flex;align-items:center;justify-content:center;gap:10px;'
            f'background:#fff;border:1px solid #dadce0;border-radius:6px;padding:10px 16px;'
            f'font-family:sans-serif;font-size:15px;font-weight:500;color:#3c4043;'
            f'box-shadow:0 1px 2px rgba(0,0,0,.08)">'
            f'<svg width="18" height="18" viewBox="0 0 48 48">'
            f'<path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>'
            f'<path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>'
            f'<path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>'
            f'<path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.35-8.16 2.35-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>'
            f'</svg>{label}</div></a>',
            unsafe_allow_html=True,
        )

# ================================================================
# AUTH PAGE
# ================================================================

def _auth_page():
    # Handle Google OAuth callback BEFORE any UI renders
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
            ("📤", "Upload CSV/Excel",    "Auto-detects sales, date, product, region columns"),
            ("📈", "Trend Analytics",     "Daily, weekly, monthly, yearly breakdowns"),
            ("🔮", "ML Forecasting",      "Linear Regression, Random Forest, XGBoost"),
            ("🌟", "Seasonal Insights",   "Best/worst months, quarterly & day-of-week patterns"),
            ("📦", "Product Analysis",    "Top products, revenue share, trend comparison"),
            ("🗺️", "Region Analysis",     "Regional breakdown and performance comparison"),
            ("🧠", "AI Recommendations",  "Inventory, demand, and revenue suggestions"),
            ("🎮", "Scenario Simulator",  "Test growth, demand & discount scenarios"),
            ("📋", "Reports",             "Download PDF, Excel, and CSV reports"),
            ("👑", "Role-Based Access",   "Admin and Business Analyst roles"),
        ]
        for i, (icon, title, desc) in enumerate(features):
            cols[i % 2].info(f"**{icon} {title}**\n\n{desc}")

    with right:
        tab_login, tab_register, tab_forgot = st.tabs(
            ["🔑 Log In", "📝 Register", "🔒 Forgot Password"]
        )

        # ── LOGIN ─────────────────────────────────────────────────
        with tab_login:
            _google_button("Sign in with Google")
            st.divider()

            with st.form("login_form"):
                st.subheader("Sign in with Email")
                email     = st.text_input("Email",    placeholder="you@example.com")
                password  = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log In", use_container_width=True, type="primary")

            if submitted:
                if not email or not password:
                    st.error("Please fill in both fields.")
                else:
                    with st.spinner("Signing in…"):
                        ok, result = auth_login(email, password)
                    msg = result["message"] if isinstance(result, dict) else result
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

            st.divider()
            st.caption("No account? Switch to the Register tab.")
            if st.button("🎮 Try Demo (no login)", use_container_width=True):
                st.session_state.authenticated = True
                st.session_state.user_id       = "demo-user"
                st.session_state.email         = "demo@platform.local"
                st.session_state.full_name     = "Demo User"
                st.session_state.role          = "analyst"
                st.session_state.jwt_token     = "demo-token"
                st.session_state.demo_mode     = True
                st.session_state.current_page  = "home"
                st.rerun()

        # ── REGISTER ──────────────────────────────────────────────
        with tab_register:
            _google_button("Sign up with Google")
            st.divider()

            cooldown     = st.session_state.get("register_cooldown", 0)
            secs_left    = max(0, int(cooldown - time.time()))
            reg_disabled = secs_left > 0

            if reg_disabled:
                st.warning(f"Please wait {secs_left} seconds before trying again.")

            with st.form("register_form"):
                st.subheader("Create account with Email")
                reg_name  = st.text_input("Full Name",              placeholder="Jane Smith")
                reg_email = st.text_input("Email",                  placeholder="you@example.com")
                reg_role  = st.selectbox("Role",                    ["analyst", "admin"])
                reg_pass  = st.text_input("Password (min 6 chars)", type="password")
                reg_pass2 = st.text_input("Confirm Password",       type="password")
                reg_sub   = st.form_submit_button(
                    "Create Account",
                    use_container_width=True,
                    type="primary",
                    disabled=reg_disabled,
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
                        if result.get("auto_login", False):
                            st.rerun()
                    else:
                        st.error(msg)

        # ── FORGOT PASSWORD ────────────────────────────────────────
        with tab_forgot:
            with st.form("forgot_form"):
                st.subheader("Reset Password")
                fp_email = st.text_input("Email", placeholder="you@example.com")
                fp_sub   = st.form_submit_button("Send Reset Email", use_container_width=True)

            if fp_sub:
                if not fp_email:
                    st.error("Please enter your email address.")
                else:
                    with st.spinner("Processing..."):
                        ok, msg = auth_forgot_password(fp_email)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

# ================================================================
# ROUTER
# ================================================================

def main():
    if is_auth():
        render_dashboard()
    else:
        _auth_page()

if __name__ == "__main__":
    main()
