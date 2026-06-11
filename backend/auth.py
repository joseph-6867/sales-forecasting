# ================================================================
# backend/auth.py — Authentication via Supabase
# ================================================================
# Uses ONLY Supabase built-in Google OAuth (sign_in_with_oauth).
# No manual OAuth flow, no Google Client ID/Secret needed here.
#
# Supabase dashboard setup required:
#   Authentication → Providers → Google → Enable
#   Set your Google Client ID + Secret there.
#   Authentication → URL Configuration:
#     Site URL:      https://deploy-financial66.streamlit.app
#     Redirect URLs: https://deploy-financial66.streamlit.app/**
#
# Google Cloud Console → OAuth Client → Authorised redirect URIs:
#   https://<your-supabase-project>.supabase.co/auth/v1/callback
#   (NOT the Streamlit URL — Supabase acts as the middleman)
# ================================================================

import os
import streamlit as st
from supabase import create_client, Client


# ── Supabase client (cached per session) ────────────────────────

@st.cache_resource
def _get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL",      os.environ.get("SUPABASE_URL", ""))
    key = st.secrets.get("SUPABASE_ANON_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))
    if not url or not key:
        raise RuntimeError(
            "Supabase credentials missing. "
            "Add SUPABASE_URL and SUPABASE_ANON_KEY to Streamlit secrets or .env"
        )
    return create_client(url, key)


# ── Session initialisation ───────────────────────────────────────

def init_session():
    """
    Ensure all auth-related session state keys exist.
    Called once at startup from app.py AFTER st.set_page_config.
    Dashboard keys (active_project, active_df, col_map, etc.) are
    initialised in app.py's _DEFAULTS block, not here.
    """
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


# ── Helpers ──────────────────────────────────────────────────────

def _set_session_from_supabase(user, session):
    """Populate st.session_state from a Supabase user + session object."""
    meta = user.user_metadata if hasattr(user, "user_metadata") else {}
    st.session_state.authenticated = True
    st.session_state.user_id       = user.id
    st.session_state.email         = user.email
    st.session_state.full_name     = (
        meta.get("full_name") or
        meta.get("name") or
        (user.email.split("@")[0] if user.email else "User")
    )
    st.session_state.role          = meta.get("role", "analyst")
    st.session_state.jwt_token     = session.access_token if session else None
    st.session_state.demo_mode     = False
    st.session_state.current_page  = "home"
    # Reset any stale dashboard state on fresh login
    st.session_state.active_project = None
    st.session_state.active_df      = None
    st.session_state.col_map        = {}


# ── Email / Password auth ────────────────────────────────────────

def auth_register(email: str, password: str, full_name: str, role: str = "analyst"):
    """Register a new user with email + password."""
    try:
        supabase = _get_supabase()
        res = supabase.auth.sign_up({
            "email":    email,
            "password": password,
            "options":  {"data": {"full_name": full_name, "role": role}},
        })
        if res.user:
            # Supabase may require email confirmation — session may be None
            if res.session:
                _set_session_from_supabase(res.user, res.session)
                return True, {
                    "message": "Account created successfully! Welcome 🎉",
                    "user": {
                        "id":        res.user.id,
                        "email":     res.user.email,
                        "full_name": full_name,
                        "role":      role,
                    },
                    "session": {"access_token": res.session.access_token},
                }
            else:
                # Email confirmation is ON — user exists but no session yet
                return True, {
                    "message": (
                        "Account created! Please check your email to confirm "
                        "your address, then log in."
                    )
                }
        return False, {"message": "Registration failed. Please try again."}
    except Exception as e:
        msg = str(e)
        if "already registered" in msg.lower() or "duplicate" in msg.lower():
            return False, {"message": "Email already registered. Please log in."}
        if "rate" in msg.lower():
            import time
            st.session_state["register_cooldown"] = time.time() + 60
            return False, {"message": "Too many requests. Please wait 60 seconds."}
        return False, {"message": f"Registration error: {msg}"}


def auth_login(email: str, password: str):
    """Sign in with email + password."""
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
                "message": f"Welcome back, {meta.get('full_name', res.user.email)}! ✅",
                "user": {
                    "id":        res.user.id,
                    "email":     res.user.email,
                    "full_name": meta.get("full_name", ""),
                    "role":      meta.get("role", "analyst"),
                },
                "session": {"access_token": res.session.access_token},
            }
        return False, {"message": "Login failed. Check your credentials."}
    except Exception as e:
        msg = str(e)
        if "invalid" in msg.lower() or "credentials" in msg.lower() or "email not confirmed" in msg.lower():
            return False, {"message": "Invalid email or password. (If new, check your confirmation email.)"}
        return False, {"message": f"Login error: {msg}"}


def auth_forgot_password(email: str):
    """Send a password reset email."""
    try:
        supabase  = _get_supabase()
        site_url  = st.secrets.get(
            "SITE_URL",
            os.environ.get("SITE_URL", "https://deploy-financial66.streamlit.app/")
        )
        supabase.auth.reset_password_email(
            email,
            options={"redirect_to": site_url}
        )
        return True, "Password reset email sent. Check your inbox."
    except Exception as e:
        return False, f"Error: {e}"


def auth_logout():
    """Sign out and clear ALL session state."""
    try:
        supabase = _get_supabase()
        supabase.auth.sign_out()
    except Exception:
        pass

    # Clear every key we set — including dashboard state
    keys_to_clear = [
        "authenticated", "user_id", "email", "full_name",
        "role", "jwt_token", "demo_mode", "current_page",
        # Dashboard state
        "active_project", "active_df", "col_map",
        "trained_models", "forecast_results",
        "_kpis", "_seasonal", "_monthly", "_daily",
        "_daily_eng", "_feat_cols", "_best_model",
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)

    # Re-apply safe defaults so the auth page doesn't KeyError
    st.session_state.authenticated  = False
    st.session_state.demo_mode      = False
    st.session_state.current_page   = "home"
    st.session_state.active_project = None
    st.session_state.active_df      = None
    st.session_state.col_map        = {}


# ── Google OAuth via Supabase ────────────────────────────────────

def auth_google_login_url() -> str:
    """
    Return the Supabase-generated Google OAuth URL.
    Supabase handles the entire OAuth handshake.

    IMPORTANT — what to configure:
      1. Supabase → Auth → Providers → Google:
           Client ID and Client Secret from Google Cloud Console
      2. Supabase → Auth → URL Configuration:
           Site URL:      https://deploy-financial66.streamlit.app
           Redirect URLs: https://deploy-financial66.streamlit.app/**
      3. Google Cloud Console → Credentials → OAuth 2.0 Client:
           Authorised redirect URIs:
             https://<your-project-ref>.supabase.co/auth/v1/callback
           (This is the Supabase callback, NOT the Streamlit app URL)
      4. Google Cloud Console → OAuth consent screen:
           If still in "Testing" mode, add your Gmail as a Test User,
           OR publish the app (click "Publish App").
           403 errors almost always mean this step was missed.
    """
    try:
        supabase = _get_supabase()
        site_url = st.secrets.get(
            "SITE_URL",
            os.environ.get("SITE_URL", "https://deploy-financial66.streamlit.app/")
        )
        res = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": site_url,
                "scopes":      "email profile",
                # queryParams forces PKCE flow which works with Streamlit
                "query_params": {
                    "access_type": "offline",
                    "prompt":      "consent",
                },
            },
        })
        return res.url
    except Exception as e:
        return f"?google_error={e}"


def auth_handle_google_callback() -> bool:
    """
    Called on every page load from _auth_page().
    Handles the ?code= query param that Supabase sends back after
    Google sign-in. Exchanges the code for a Supabase session.

    Returns True if a new session was created (caller should st.rerun()).
    """
    params = st.query_params

    # ── Supabase returned an error ────────────────────────────────
    error = params.get("error")
    if error:
        desc = params.get("error_description", error)
        st.error(f"Google sign-in failed: {desc}")
        st.query_params.clear()
        return False

    # ── PKCE flow: ?code= ─────────────────────────────────────────
    # Supabase redirects back with ?code= (not a fragment) when using
    # PKCE. This is the standard modern flow.
    code = params.get("code")
    if code:
        try:
            supabase = _get_supabase()
            res = supabase.auth.exchange_code_for_session({"auth_code": code})
            if res.user and res.session:
                _set_session_from_supabase(res.user, res.session)
                st.query_params.clear()
                return True
            else:
                st.error("Google sign-in: could not exchange code for session. Try again.")
                st.query_params.clear()
                return False
        except Exception as e:
            st.error(f"Google sign-in error: {e}")
            st.query_params.clear()
            return False

    # ── Legacy implicit flow: ?access_token= ─────────────────────
    token = params.get("access_token")
    if token:
        try:
            supabase = _get_supabase()
            res = supabase.auth.get_user(token)
            if res.user:
                class _FakeSession:
                    access_token = token
                _set_session_from_supabase(res.user, _FakeSession())
                st.query_params.clear()
                return True
        except Exception as e:
            st.error(f"Google sign-in error (token): {e}")
            st.query_params.clear()
            return False

    return False


# ── Token verification ───────────────────────────────────────────

def auth_verify_token(token: str):
    """Verify an existing JWT and return user info."""
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
