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
                _set_session_from_supabase(res.user, res.session)
                return True, {"message": "Account created successfully! Welcome 🎉", "auto_login": True}
            else:
                return True, {
                    "message": "✅ Account created! Check your email to confirm, then log in.",
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
        "_oauth_code_verifier",
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
    Generates Google OAuth URL using PKCE flow.

    supabase-py always uses PKCE. When sign_in_with_oauth() is called,
    the Python client generates a code_verifier internally and embeds
    the matching code_challenge in the OAuth URL.

    The verifier is stored in st.session_state["_oauth_code_verifier"]
    so auth_handle_google_callback() can use it to exchange the ?code=
    for a real session via exchange_code_for_session().

    Required Supabase setup:
      1. Auth → Providers → Google → Enable, add Client ID + Secret
      2. Auth → URL Configuration:
           Site URL:      https://deploy-financial66.streamlit.app
           Redirect URLs: https://deploy-financial66.streamlit.app/**
      3. Google Cloud Console → OAuth Client → Authorised redirect URIs:
           https://<project-ref>.supabase.co/auth/v1/callback
    """
    supabase = _get_supabase()
    site_url = _get_site_url()

    res = supabase.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {
            "redirect_to": site_url,
            "scopes":      "email profile",
        },
    })

    if not res.url:
        raise RuntimeError(
            "Supabase returned an empty OAuth URL. "
            "Check that Google provider is enabled in Supabase → Auth → Providers."
        )

    # Save the PKCE code verifier that supabase-py generated internally.
    # We must pass it back when exchanging the ?code= for a session.
    # It lives on the supabase.auth._storage or in the response object.
    _save_pkce_verifier(supabase)

    return res.url


def _save_pkce_verifier(supabase):
    """
    Extracts the PKCE code verifier from the supabase-py auth client
    and stores it in session_state for use during callback.

    supabase-py stores the verifier in its internal async/sync storage.
    We reach into it here so Python can complete the code exchange.
    """
    try:
        # supabase-py stores PKCE state in auth._storage (SyncMemoryStorage)
        storage = supabase.auth._storage
        # The key used internally by gotrue-py
        for key in ["supabase.auth.code_verifier", "code_verifier", "pkce_code_verifier"]:
            try:
                verifier = storage.get_item(key)
                if verifier:
                    st.session_state["_oauth_code_verifier"] = verifier
                    return
            except Exception:
                continue

        # Fallback: iterate all storage keys
        try:
            items = storage._storage if hasattr(storage, "_storage") else {}
            for k, v in items.items():
                if "verifier" in k.lower() or "pkce" in k.lower():
                    st.session_state["_oauth_code_verifier"] = v
                    return
        except Exception:
            pass

    except Exception:
        pass


def auth_handle_google_callback() -> bool:
    """
    Handles the ?code= callback from Supabase after Google OAuth.

    PKCE flow:
      1. User clicks Google button → auth_google_login_url() generates URL
         + stores code_verifier in session_state
      2. Google auth → Supabase → redirects to app with ?code=xxx
      3. This function reads ?code= and the saved verifier, calls
         exchange_code_for_session() to get a real session
      4. Sets authenticated state, clears query params, returns True
    """
    params = st.query_params

    # Supabase error
    error = params.get("error")
    if error:
        desc = params.get("error_description", error)
        st.error(f"Google sign-in failed: {desc}")
        st.query_params.clear()
        return False

    # PKCE code arrived
    code = params.get("code")
    if code:
        try:
            supabase = _get_supabase()

            # Restore the code verifier into the supabase-py storage
            # so exchange_code_for_session can find it
            verifier = st.session_state.get("_oauth_code_verifier")
            if verifier:
                try:
                    storage = supabase.auth._storage
                    for key in ["supabase.auth.code_verifier", "code_verifier", "pkce_code_verifier"]:
                        try:
                            storage.set_item(key, verifier)
                        except Exception:
                            pass
                    # Also try _storage dict directly
                    if hasattr(storage, "_storage"):
                        storage._storage["supabase.auth.code_verifier"] = verifier
                        storage._storage["code_verifier"] = verifier
                except Exception:
                    pass

            res = supabase.auth.exchange_code_for_session({"auth_code": code})

            if res.user and res.session:
                _set_session_from_supabase(res.user, res.session)
                st.session_state.pop("_oauth_code_verifier", None)
                st.query_params.clear()
                return True
            else:
                st.error("Google sign-in: could not complete sign-in. Please try again.")
                st.query_params.clear()
                return False

        except Exception as e:
            err = str(e)
            # If verifier still missing, show a clear message
            if "verifier" in err.lower() or "code" in err.lower():
                st.error(
                    "Google sign-in failed: session expired during redirect. "
                    "Please try signing in again."
                )
            else:
                st.error(f"Google sign-in error: {e}")
            st.query_params.clear()
            st.session_state.pop("_oauth_code_verifier", None)
            return False

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
