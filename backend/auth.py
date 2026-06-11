# ================================================================
# backend/auth.py — Authentication via Supabase
# ================================================================

import os
import streamlit as st
from supabase import create_client, Client


# ── Supabase client ──────────────────────────────────────────────
def _get_supabase() -> Client:
    try:
        url = st.secrets.get("SUPABASE_URL", "") or os.environ.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_ANON_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")
    except Exception:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")

    if not url or not key:
        raise RuntimeError(
            "Supabase credentials missing. "
            "Add SUPABASE_URL and SUPABASE_ANON_KEY to Streamlit Cloud secrets."
        )
    return create_client(url, key)


# ── Session initialisation ───────────────────────────────────────

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
    return (
        bool(st.session_state.get("authenticated")) and
        st.session_state.get("role") == "admin"
    )


def get_current_user() -> dict:
    return {
        "user_id":   st.session_state.get("user_id"),
        "email":     st.session_state.get("email"),
        "full_name": st.session_state.get("full_name"),
        "role":      st.session_state.get("role", "analyst"),
        "jwt_token": st.session_state.get("jwt_token"),
        "demo_mode": st.session_state.get("demo_mode", False),
    }


# ── Session setter ───────────────────────────────────────────────

def _set_session_from_supabase(user, session):
    meta = user.user_metadata if hasattr(user, "user_metadata") else {}
    st.session_state.authenticated  = True
    st.session_state.user_id        = user.id
    st.session_state.email          = user.email
    st.session_state.full_name      = (
        meta.get("full_name") or
        meta.get("name") or
        (user.email.split("@")[0] if user.email else "User")
    )
    st.session_state.role           = meta.get("role", "analyst")
    st.session_state.jwt_token      = getattr(session, "access_token", None) or session
    st.session_state.demo_mode      = False
    st.session_state.current_page   = "home"
    st.session_state.active_project = None
    st.session_state.active_df      = None
    st.session_state.col_map        = {}


# ── Email / Password auth ────────────────────────────────────────

def auth_register(email: str, password: str, full_name: str, role: str = "analyst"):
    try:
        supabase = _get_supabase()
        res = supabase.auth.sign_up({
            "email":    email,
            "password": password,
            "options":  {"data": {"full_name": full_name, "role": role}},
        })
        if res.user:
            if res.session:
                _set_session_from_supabase(res.user, res.session)
                return True, {"message": "Account created successfully! Welcome 🎉", "auto_login": True}
            else:
                return True, {
                    "message": "Account created! Check your email to confirm, then log in.",
                    "auto_login": False,
                }
        return False, {"message": "Registration failed. Please try again.", "auto_login": False}
    except Exception as e:
        msg = str(e)
        if "already registered" in msg.lower() or "duplicate" in msg.lower():
            return False, {"message": "Email already registered. Please log in instead.", "auto_login": False}
        if "rate" in msg.lower():
            import time
            st.session_state["register_cooldown"] = time.time() + 60
            return False, {"message": "Too many requests. Please wait 60 seconds.", "auto_login": False}
        return False, {"message": f"Registration error: {msg}", "auto_login": False}


def auth_login(email: str, password: str):
    try:
        supabase = _get_supabase()
        res = supabase.auth.sign_in_with_password({
            "email":    email,
            "password": password,
        })
        if res.user and res.session:
            meta = res.user.user_metadata or {}
            _set_session_from_supabase(res.user, res.session)
            return True, {
                "message": f"Welcome back, {meta.get('full_name', res.user.email)}!"
            }
        return False, {"message": "Login failed. Check your credentials."}
    except Exception as e:
        msg = str(e)
        if "email not confirmed" in msg.lower() or "not confirmed" in msg.lower():
            return False, {"message": "Please confirm your email address first (check your inbox)."}
        if "invalid" in msg.lower() or "credentials" in msg.lower() or "wrong" in msg.lower():
            return False, {"message": "Invalid email or password."}
        return False, {"message": f"Login error: {msg}"}


def auth_forgot_password(email: str):
    try:
        supabase = _get_supabase()
        site_url = _get_site_url()
        supabase.auth.reset_password_email(email, options={"redirect_to": site_url})
        return True, "Password reset email sent. Check your inbox."
    except Exception as e:
        return False, f"Error: {e}"


def auth_logout():
    try:
        supabase = _get_supabase()
        supabase.auth.sign_out()
    except Exception:
        pass

    keys_to_clear = [
        "authenticated", "user_id", "email", "full_name",
        "role", "jwt_token", "demo_mode", "current_page",
        "active_project", "active_df", "col_map",
        "trained_models", "forecast_results",
        "_kpis", "_seasonal", "_monthly", "_daily",
        "_daily_eng", "_feat_cols", "_best_model",
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)

    st.session_state.authenticated  = False
    st.session_state.demo_mode      = False
    st.session_state.current_page   = "home"
    st.session_state.active_project = None
    st.session_state.active_df      = None
    st.session_state.col_map        = {}


# ── Helpers ──────────────────────────────────────────────────────

def _get_site_url() -> str:
    try:
        url = st.secrets.get("SITE_URL", "") or os.environ.get("SITE_URL", "")
    except Exception:
        url = os.environ.get("SITE_URL", "")
    return (url or "https://deploy-financial66.streamlit.app/").rstrip("/") + "/"


def _get_supabase_url() -> str:
    try:
        return st.secrets.get("SUPABASE_URL", "") or os.environ.get("SUPABASE_URL", "")
    except Exception:
        return os.environ.get("SUPABASE_URL", "")


def _get_callback_url() -> str:
    """
    Returns the URL of oauth_callback.html — the intermediate page that
    extracts the token from the URL fragment and forwards it to Streamlit.

    For Streamlit Cloud, static files in /static/ are served at:
      https://<app>.streamlit.app/app/static/<filename>

    We serve oauth_callback.html from the /static/ folder.
    """
    try:
        cb = st.secrets.get("OAUTH_CALLBACK_URL", "") or os.environ.get("OAUTH_CALLBACK_URL", "")
    except Exception:
        cb = os.environ.get("OAUTH_CALLBACK_URL", "")

    if cb:
        return cb

    # Default: Streamlit Cloud serves files in /static/ at this path
    base = _get_site_url().rstrip("/")
    return f"{base}/app/static/oauth_callback.html"


# ── Google OAuth ─────────────────────────────────────────────────

def auth_google_login_url() -> str:
    """
    Builds the Supabase Google OAuth URL.

    REDIRECT STRATEGY
    -----------------
    We redirect to oauth_callback.html (a static file in /static/).
    That page runs in a real browser context (not an iframe), reads the
    #access_token fragment, and redirects to the Streamlit app with
    ?st_access_token=... as a query param that Python can read.

    Why not redirect straight to the Streamlit app?
      Streamlit renders inside an iframe on Streamlit Cloud.
      st.components.v1.html() also renders in a nested iframe.
      Neither can access or modify the top-level window.location.
      A standalone HTML page has no such restriction.
    """
    import urllib.parse

    supabase_url  = _get_supabase_url().rstrip("/")
    callback_url  = _get_callback_url()

    params = urllib.parse.urlencode({
        "provider":    "google",
        "redirect_to": callback_url,   # → oauth_callback.html, not Streamlit directly
        "scopes":      "email profile",
    })

    return f"{supabase_url}/auth/v1/authorize?{params}"


def auth_handle_google_callback() -> bool:
    """
    Reads ?st_access_token= forwarded by oauth_callback.html,
    validates with Supabase, sets session state.
    Returns True if a new session was established.
    """
    params = st.query_params

    # Explicit OAuth error forwarded by the callback page
    error = params.get("error")
    if error:
        desc = params.get("error_description", error)
        st.error(f"Google sign-in failed: {desc}")
        st.query_params.clear()
        return False

    # Token forwarded from oauth_callback.html
    access_token = params.get("st_access_token")
    if not access_token:
        return False

    try:
        supabase = _get_supabase()
        user_res = supabase.auth.get_user(access_token)

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
        import traceback
        st.error(f"Google sign-in error: {e}")
        st.code(traceback.format_exc(), language="python")
        st.query_params.clear()
        return False


# ── Token verification ───────────────────────────────────────────

def auth_verify_token(token: str):
    try:
        supabase = _get_supabase()
        res = supabase.auth.get_user(token)
        if res.user:
            meta = res.user.user_metadata or {}
            return True, {
                "user": {
                    "id":        res.user.id,
                    "email":     res.user.email,
                    "full_name": meta.get("full_name", ""),
                    "role":      meta.get("role", "analyst"),
                }
            }
        return False, "Invalid token"
    except Exception as e:
        return False, str(e)
