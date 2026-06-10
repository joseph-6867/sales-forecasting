# ================================================================
# app.py  —  Main Entry Point
# ================================================================
# Run with:  streamlit run app.py
#
# Routes:
#   Not logged in → Auth page  (login / register / forgot pw)
#   Logged in     → Dashboard
# ================================================================

import time
import streamlit as st

st.set_page_config(
    page_title="Sales Forecasting Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "# Sales Forecasting Platform v1.0"}
)

from backend.auth       import init_session, is_auth, auth_register, auth_login, auth_forgot_password, auth_verify_token
from frontend.dashboard import render_dashboard

init_session()


def _handle_google_callback():
    params = st.query_params
    token_param = params.get("token")
    if isinstance(token_param, list):
        token = token_param[0] if token_param else None
    else:
        token = token_param
    if not token:
        return

    ok, result = auth_verify_token(token)
    if ok and isinstance(result, dict) and result.get("user"):
        user = result["user"]
        st.session_state.authenticated = True
        st.session_state.user_id = user.get("id")
        st.session_state.email = user.get("email")
        st.session_state.full_name = user.get("full_name")
        st.session_state.role = user.get("role")
        st.session_state.jwt_token = token
        st.session_state.current_page = "dashboard"
        st.query_params = {}
        st.experimental_rerun()
    else:
        error_message = result if isinstance(result, str) else result.get("message", "Google sign-in failed")
        st.error(f"Google sign-in failed: {error_message}")
        st.query_params = {}


# ================================================================
# AUTH PAGES
# ================================================================

def _auth_page():
    """Login / Register / Forgot Password."""

    if "_handle_google_callback" in globals():
        _handle_google_callback()
    else:
        st.warning("Google callback handler is unavailable. Check app.py for missing definitions.")

    # ── Hero ──────────────────────────────────────────────────
    st.markdown(
        """
        <div style="text-align:center;padding:36px 0 20px">
          <h1 style="font-size:2.6rem;margin:0">📊 Sales Forecasting Platform</h1>
          <p style="color:#94A3B8;font-size:1.1rem;margin-top:8px">
            Intelligent Business Analytics & ML-Powered Sales Prediction
          </p>
        </div>
        """, unsafe_allow_html=True
    )
    st.divider()

    left, right = st.columns([3, 2], gap="large")

    # ── LEFT: Feature highlights ───────────────────────────
    with left:
        st.subheader("🚀 What you get")
        cols = st.columns(2)
        features = [
            ("📤", "Upload CSV/Excel", "Auto-detects sales, date, product, region columns"),
            ("📈", "Trend Analytics",  "Daily, weekly, monthly, yearly breakdowns"),
            ("🔮", "ML Forecasting",   "Linear Regression, Random Forest, Gradient Boosting"),
            ("🌟", "Seasonal Insights","Best/worst months, quarterly & day-of-week patterns"),
            ("📦", "Product Analysis", "Top products, revenue share, trend comparison"),
            ("🗺️", "Region Analysis",  "Regional breakdown and performance comparison"),
            ("🧠", "AI Recommendations","Inventory, demand, and revenue suggestions"),
            ("🎮", "Scenario Simulator","Test growth, demand & discount scenarios"),
            ("📋", "Reports",          "Download PDF, Excel, and CSV reports"),
            ("👑", "Role-Based Access","Admin and Business Analyst roles"),
        ]
        for i, (icon, title, desc) in enumerate(features):
            cols[i % 2].info(f"**{icon} {title}**\n\n{desc}")

    # ── RIGHT: Auth forms ──────────────────────────────────
    with right:
        tab_login, tab_register, tab_forgot = st.tabs(
            ["🔑 Log In", "📝 Register", "🔒 Forgot Password"]
        )

        # ── LOGIN ─────────────────────────────────────────
        with tab_login:
            with st.form("login_form"):
                st.subheader("Welcome back")
                account  = st.text_input("Account or Email", placeholder="site account name or alias email")
                password = st.text_input("Password", type="password")
                st.caption("Use your account name or shared alias email plus password. Login is now handled by the app.")
                submitted= st.form_submit_button("Log In", use_container_width=True, type="primary")

            if submitted:
                if not account or not password:
                    st.error("Please fill in both fields.")
                else:
                    with st.spinner("Signing in…"):
                        ok, auth_result = auth_login(account, password)
                    result_msg = auth_result["message"] if isinstance(auth_result, dict) else auth_result
                    if ok:
                        st.success(result_msg)
                        if isinstance(auth_result, dict) and auth_result.get("user"):
                            user = auth_result["user"]
                            token = auth_result.get("session", {}).get("access_token")
                            if token and user:
                                st.session_state.authenticated = True
                                st.session_state.user_id = user.get("id")
                                st.session_state.email = user.get("email")
                                st.session_state.full_name = user.get("full_name")
                                st.session_state.role = user.get("role")
                                st.session_state.jwt_token = token
                                st.session_state.current_page = "dashboard"
                        st.rerun()
                    else:
                        st.error(result_msg)

            # Demo shortcut
            st.divider()
            st.caption("Want to try without an account?")
            if st.button("🎮 Try Demo (no login)", use_container_width=True):
                # Create a guest session
                st.session_state.authenticated = True
                st.session_state.user_id       = "demo-user"
                st.session_state.email         = "demo@platform.local"
                st.session_state.full_name     = "Demo User"
                st.session_state.role          = "analyst"
                st.session_state.jwt_token     = "demo-token"  # Dummy token for demo mode
                st.session_state.demo_mode     = True
                st.session_state.current_page  = "home"
                st.rerun()

            st.caption("Or sign in with Google instead of a password.")
            st.markdown(
                "<a href='http://localhost:8000/auth/google/login' target='_self'>"
                "<button style='width:100%;padding:10px;border-radius:6px;border:none;background:#4285F4;color:white;font-weight:600;'>"
                "Sign in with Google"
                "</button></a>",
                unsafe_allow_html=True,
            )

        # ── REGISTER ──────────────────────────────────────
        with tab_register:
            register_cooldown = st.session_state.get("register_cooldown", 0)
            seconds_left = max(0, int(register_cooldown - time.time()))
            register_disabled = seconds_left > 0

            if register_disabled:
                st.warning(
                    f"Please wait {seconds_left} seconds before trying again."
                )
                st.caption("Use the Demo login while you wait.")

            with st.form("register_form"):
                st.subheader("Create account")
                reg_name    = st.text_input("Full Name",  placeholder="Jane Smith")
                reg_account = st.text_input("Account or Email",    placeholder="site account name or email")
                reg_role    = st.selectbox("Role", ["analyst", "admin"])
                reg_pass    = st.text_input("Password (min 6 chars)", type="password")
                reg_pass2   = st.text_input("Confirm Password", type="password")
                st.caption("Enter a website account name or email. The app stores your login in Supabase.")
                reg_sub     = st.form_submit_button(
                    "Create Account",
                    use_container_width=True,
                    type="primary",
                    disabled=register_disabled,
                )

            if reg_sub:
                if not all([reg_name, reg_account, reg_pass, reg_pass2]):
                    st.error("All fields are required.")
                elif reg_pass != reg_pass2:
                    st.error("Passwords do not match.")
                else:
                    with st.spinner("Creating account…"):
                        ok, auth_result = auth_register(reg_account, reg_pass, reg_name, reg_role)
                    result_msg = auth_result["message"] if isinstance(auth_result, dict) else auth_result
                    if ok:
                        st.success(result_msg)
                        if isinstance(auth_result, dict) and auth_result.get("user"):
                            user = auth_result["user"]
                            token = auth_result.get("session", {}).get("access_token")
                            if token and user:
                                st.session_state.authenticated = True
                                st.session_state.user_id = user.get("id")
                                st.session_state.email = user.get("email")
                                st.session_state.full_name = user.get("full_name")
                                st.session_state.role = user.get("role")
                                st.session_state.jwt_token = token
                                st.session_state.current_page = "dashboard"
                                st.rerun()
                    else:
                        st.error(result_msg)

        # ── FORGOT PASSWORD ───────────────────────────────
        with tab_forgot:
            with st.form("forgot_form"):
                st.subheader("Reset Password")
                fp_account = st.text_input("Account or Email", placeholder="site account name or alias email")
                fp_sub   = st.form_submit_button("Send Reset Email", use_container_width=True)

            if fp_sub:
                if not fp_account:
                    st.error("Please enter your account name or email.")
                else:
                    ok, msg = auth_forgot_password(fp_account)
                    if ok: st.success(msg)
                    else:  st.error(msg)


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
else:
    main()
