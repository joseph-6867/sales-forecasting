# ================================================================
# backend/auth.py — Authentication via Supabase
# ================================================================

import os
import streamlit as st
from supabase import create_client, Client


def _get_supabase() -> Client:
    try:
        url = st.secrets.get("SUPABASE_URL", "") or os.environ.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_ANON_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")
    except Exception:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("Supabase credentials missing.")
    return create_client(url, key)


def init_session():
    defaults = {
        "authenticated": False,
        "user_id":       None,
        "email":         None,
        "full_name":     None,
        "role":          "analyst",
        "jwt_token":     None,
        "demo_mode":     False,
        "current_page":  "home",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def is_auth() -> bool:
    return bool(st.session_state.get("authenticated"))


def is_admin() -> bool:
    return bool(st.session_state.get("authenticated")) and st.session_state.get("role") == "admin"


def get_current_user() -> dict:
    return {
        "user_id":   st.session_state.get("user_id"),
        "email":     st.session_state.get("email"),
        "full_name": st.session_state.get("full_name"),
        "role":      st.session_state.get("role", "analyst"),
        "jwt_token": st.session_state.get("jwt_token"),
        "demo_mode": st.session_state.get("demo_mode", False),
    }


def _set_session_from_supabase(user, session):
    meta = user.user_metadata if hasattr(user, "user_metadata") else {}
    st.session_state.authenticated  = True
    st.session_state.user_id        = user.id
    st.session_state.email          = user.email
    st.session_state.full_name      = (
        meta.get("full_name") or meta.get("name") or
        (user.email.split("@")[0] if user.email else "User")
    )
    st.session_state.role           = meta.get("role", "analyst")
    st.session_state.jwt_token      = getattr(session, "access_token", None) or session
    st.session_state.demo_mode      = False
    st.session_state.current_page   = "home"
    st.session_state.active_project = None
    st.session_state.active_df      = None
    st.session_state.col_map        = {}


# ── Email / Password ─────────────────────────────────────────────

def auth_register(email, password, full_name, role="analyst"):
    try:
        res = _get_supabase().auth.sign_up({
            "email": email, "password": password,
            "options": {"data": {"full_name": full_name, "role": role}},
        })
        if res.user:
            if res.session:
                _set_session_from_supabase(res.user, res.session)
                return True, {"message": "Account created! Welcome 🎉", "auto_login": True}
            return True, {"message": "Account created! Check your email to confirm.", "auto_login": False}
        return False, {"message": "Registration failed.", "auto_login": False}
    except Exception as e:
        msg = str(e)
        if "already registered" in msg.lower() or "duplicate" in msg.lower():
            return False, {"message": "Email already registered.", "auto_login": False}
        if "rate" in msg.lower():
            import time; st.session_state["register_cooldown"] = time.time() + 60
            return False, {"message": "Too many requests. Wait 60 seconds.", "auto_login": False}
        return False, {"message": f"Registration error: {msg}", "auto_login": False}


def auth_login(email, password):
    try:
        res = _get_supabase().auth.sign_in_with_password({"email": email, "password": password})
        if res.user and res.session:
            meta = res.user.user_metadata or {}
            _set_session_from_supabase(res.user, res.session)
            return True, {"message": f"Welcome back, {meta.get('full_name', res.user.email)}!"}
        return False, {"message": "Login failed. Check your credentials."}
    except Exception as e:
        msg = str(e)
        if "email not confirmed" in msg.lower():
            return False, {"message": "Please confirm your email first."}
        if "invalid" in msg.lower() or "credentials" in msg.lower():
            return False, {"message": "Invalid email or password."}
        return False, {"message": f"Login error: {msg}"}


def auth_forgot_password(email):
    try:
        _get_supabase().auth.reset_password_email(
            email, options={"redirect_to": _get_site_url()}
        )
        return True, "Password reset email sent."
    except Exception as e:
        return False, f"Error: {e}"


def auth_logout():
    try: _get_supabase().auth.sign_out()
    except Exception: pass
    for key in ["authenticated", "user_id", "email", "full_name", "role", "jwt_token",
                "demo_mode", "current_page", "active_project", "active_df", "col_map",
                "trained_models", "forecast_results", "_kpis", "_seasonal", "_monthly",
                "_daily", "_daily_eng", "_feat_cols", "_best_model"]:
        st.session_state.pop(key, None)
    st.session_state.update({
        "authenticated": False, "demo_mode": False, "current_page": "home",
        "active_project": None, "active_df": None, "col_map": {},
    })


# ── Helpers ──────────────────────────────────────────────────────

def _get_site_url():
    try:
        url = st.secrets.get("SITE_URL", "") or os.environ.get("SITE_URL", "")
    except Exception:
        url = os.environ.get("SITE_URL", "")
    return (url or "https://deploy-financial66.streamlit.app/").rstrip("/") + "/"


def _get_supabase_url():
    try:
        return st.secrets.get("SUPABASE_URL", "") or os.environ.get("SUPABASE_URL", "")
    except Exception:
        return os.environ.get("SUPABASE_URL", "")


# ── Google OAuth ─────────────────────────────────────────────────
# Strategy: redirect_to points directly back to the Streamlit app.
# Supabase appends #access_token=... to the URL (implicit flow).
# A small JS snippet in the page converts the fragment to ?st_access_token=
# so Streamlit can read it as a query param.

def auth_google_login_url():
    """
    Build the Supabase OAuth URL.
    redirect_to = your Streamlit app URL (Supabase will append the token fragment there).
    """
    import urllib.parse
    redirect_to = _get_site_url().rstrip("/") + "/"
    params = urllib.parse.urlencode({
        "provider":    "google",
        "redirect_to": redirect_to,
        "scopes":      "email profile",
    })
    return f"{_get_supabase_url().rstrip('/')}/auth/v1/authorize?{params}"


def inject_oauth_fragment_handler():
    """
    Inject a JS snippet once per page load.
    If the URL contains #access_token=..., convert it to ?st_access_token=
    so Streamlit picks it up as a query param on the next render.
    This is needed because Streamlit cannot read URL fragments server-side.
    """
    st.components.v1.html(
        """
        <script>
        (function() {
            var hash = window.location.hash;
            if (!hash) return;

            var params = {};
            hash.substring(1).split('&').forEach(function(part) {
                var kv = part.split('=');
                if (kv.length === 2) params[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1]);
            });

            var accessToken = params['access_token'];
            if (!accessToken) return;

            // Already converted — avoid infinite loop
            if (window.location.search.indexOf('st_access_token') !== -1) return;

            // Build new URL with token as query param so Streamlit can read it
            var newUrl = window.location.origin + window.location.pathname
                + '?st_access_token=' + encodeURIComponent(accessToken)
                + '&token_type=' + encodeURIComponent(params['token_type'] || 'bearer');
            window.location.replace(newUrl);
        })();
        </script>
        """,
        height=0,
    )


def auth_handle_google_callback() -> bool:
    """
    1. Always inject the JS fragment handler so tokens in the URL hash get
       converted to query params on first load.
    2. Then check for ?st_access_token= and log the user in.
    3. Also handles ?code= (PKCE) as a fallback.
    Returns True if login succeeded (caller should st.rerun()).
    """
    # Step 1: always inject fragment→query-param converter
    inject_oauth_fragment_handler()

    params = st.query_params

    # ── Explicit error ────────────────────────────────────────────
    if params.get("error"):
        st.error(f"Google sign-in failed: {params.get('error_description', params.get('error'))}")
        st.query_params.clear()
        return False

    # ── Path 1: implicit — token in query param (set by JS above) ─
    access_token = params.get("st_access_token")
    if access_token:
        return _login_with_token(access_token)

    # ── Path 2: PKCE code exchange (fallback) ─────────────────────
    code = params.get("code")
    if code:
        return _exchange_code(code)

    return False


def _login_with_token(access_token: str) -> bool:
    try:
        supabase  = _get_supabase()
        user_res  = supabase.auth.get_user(access_token)
        if not user_res or not user_res.user:
            st.error("Google sign-in: token invalid or expired. Please try again.")
            st.query_params.clear()
            return False

        class _Sess:
            def __init__(self, t): self.access_token = t

        _set_session_from_supabase(user_res.user, _Sess(access_token))
        st.query_params.clear()
        return True
    except Exception as e:
        st.error(f"Google sign-in error: {e}")
        st.query_params.clear()
        return False


def _exchange_code(code: str) -> bool:
    """Exchange PKCE auth code for a session using Supabase's token endpoint."""
    try:
        supabase_url = _get_supabase_url().rstrip("/")
        try:
            key = st.secrets.get("SUPABASE_ANON_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")
        except Exception:
            key = os.environ.get("SUPABASE_ANON_KEY", "")

        import httpx
        resp = httpx.post(
            f"{supabase_url}/auth/v1/token?grant_type=authorization_code",
            headers={"apikey": key, "Content-Type": "application/json"},
            json={"code": code},
            timeout=15,
        )

        if resp.status_code == 200:
            data = resp.json()
            access_token = data.get("access_token")
            if access_token:
                return _login_with_token(access_token)

        st.error(
            f"Code exchange failed (HTTP {resp.status_code}). "
            "In Supabase Dashboard → Authentication → URL Configuration, "
            "ensure Auth Flow is set to **Implicit** (not PKCE)."
        )
        st.query_params.clear()
        return False
    except Exception as e:
        st.error(f"Code exchange error: {e}")
        st.query_params.clear()
        return False


def auth_verify_token(token):
    try:
        res = _get_supabase().auth.get_user(token)
        if res.user:
            meta = res.user.user_metadata or {}
            return True, {"user": {"id": res.user.id, "email": res.user.email,
                                   "full_name": meta.get("full_name", ""),
                                   "role": meta.get("role", "analyst")}}
        return False, "Invalid token"
    except Exception as e:
        return False, str(e)
