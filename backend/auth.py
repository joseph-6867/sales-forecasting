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
            "Add SUPABASE_URL and SUPABASE_ANON_KEY to Streamlit Cloud secrets "
            "(App settings → Secrets) in TOML format:\n"
            'SUPABASE_URL = "https://..."\n'
            'SUPABASE_ANON_KEY = "eyJ..."'
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


# ── Helpers ──────────────────────────────────────────────────────

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
    st.session_state.jwt_token      = session.access_token if session else None
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
                # ✅ Email confirmation OFF — session is immediately available
                _set_session_from_supabase(res.user, res.session)
                return True, {"message": "Account created successfully! Welcome 🎉", "auto_login": True}
            else:
                # Email confirmation ON — session is None, do NOT set authenticated
                # (With confirm OFF this branch should not be reached)
                return True, {
                    "message": (
                        "✅ Account created! Check your email to confirm your address, "
                        "then log in here."
                    ),
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
                "message": f"Welcome back, {meta.get('full_name', res.user.email)}! ✅"
            }
        return False, {"message": "Login failed. Check your credentials."}
    except Exception as e:
        msg = str(e)
        # ✅ BUG 2 FIX: catch "email not confirmed" before generic handler
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


# ── Google OAuth via Supabase ────────────────────────────────────

def _get_site_url() -> str:
    try:
        url = st.secrets.get("SITE_URL", "") or os.environ.get("SITE_URL", "")
    except Exception:
        url = os.environ.get("SITE_URL", "")
    return url or "https://deploy-financial66.streamlit.app/"


def auth_google_login_url() -> str:
    """
    Returns the Supabase Google OAuth redirect URL.

    IMPORTANT — Flow type must be set to IMPLICIT in Supabase dashboard:
      Authentication → Sign In / Providers → Scroll to bottom → Auth Flow Type → Implicit

    Why Implicit and not PKCE:
      PKCE requires a browser-generated code verifier that only Supabase JS can create.
      Python has no access to it, so exchange_code_for_session always fails with
      "both auth code and code verifier should be non-empty".
      Implicit flow returns the token directly in the URL — Python can read it.

    Required setup:
      1. Supabase → Auth → Sign In / Providers → Auth Flow Type → "Implicit"  ← CRITICAL
      2. Supabase → Auth → Providers → Google → Enable, paste Client ID + Secret
      3. Supabase → Auth → URL Configuration
           Site URL:      https://deploy-financial66.streamlit.app
           Redirect URLs: https://deploy-financial66.streamlit.app/**
      4. Google Cloud Console → Credentials → OAuth 2.0 Client
           Authorised redirect URIs:
             https://<your-project-ref>.supabase.co/auth/v1/callback
    """
    supabase = _get_supabase()
    site_url = _get_site_url()

    res = supabase.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {
            "redirect_to": site_url,
            "scopes":      "email profile",
            # No query_params — they forced PKCE behaviour Python can't satisfy
        },
    })

    if not res.url:
        raise RuntimeError(
            "Supabase returned an empty OAuth URL. "
            "Check that Google provider is enabled in Supabase → Auth → Providers."
        )

    return res.url


def auth_handle_google_callback() -> bool:
    """
    Handles Google OAuth callback after redirect.

    Supabase Implicit flow puts the token in the URL FRAGMENT (#access_token=...).
    URL fragments are NEVER sent to the server — Streamlit's st.query_params cannot
    see them. So we inject a tiny JS snippet that reads window.location.hash, extracts
    the access_token, and re-writes it as a real ?query_param so Streamlit can read it
    on the next render cycle.

    Flow:
      1. Google redirects to app with #access_token=xxx in the fragment
      2. JS reads the fragment and does location.replace("?access_token=xxx")
      3. Streamlit re-renders, st.query_params now has access_token
      4. Python reads it, calls get_user(), sets session, clears params
    """
    params = st.query_params

    # ── Step 1: Check for Supabase error in query params ────────
    error = params.get("error")
    if error:
        desc = params.get("error_description", error)
        st.error(f"Google sign-in failed: {desc}")
        st.query_params.clear()
        return False

    # ── Step 2: Implicit flow token arrived as ?access_token= ───
    # (Set by our JS fragment-to-query bridge below on previous render)
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
            else:
                st.error("Google sign-in: could not verify token. Please try again.")
                st.query_params.clear()
                return False
        except Exception as e:
            st.error(f"Google sign-in error: {e}")
            st.query_params.clear()
            return False

    # ── Step 3: No token yet — inject JS to read URL fragment ───
    # Supabase Implicit flow lands with #access_token=... in the hash.
    # This JS reads it and converts it to a ?query_param so Streamlit sees it.
    # Uses st.iframe with a data URI (st.components.v1.html removed after 2026-06-01)
    js_code = """
        <script>
        (function() {
            var hash = window.parent.location.hash;
            if (!hash || hash.indexOf('access_token') === -1) return;

            var fragmentParams = {};
            hash.substring(1).split('&').forEach(function(pair) {
                var parts = pair.split('=');
                if (parts.length === 2) {
                    fragmentParams[decodeURIComponent(parts[0])] = decodeURIComponent(parts[1]);
                }
            });

            var token = fragmentParams['access_token'];
            if (token) {
                var newUrl = window.parent.location.pathname + '?access_token=' + encodeURIComponent(token);
                window.parent.location.replace(newUrl);
            }
        })();
        </script>
    """
    import base64
    encoded = base64.b64encode(js_code.encode()).decode()
    st.iframe(f"data:text/html;base64,{encoded}", height=1)

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
