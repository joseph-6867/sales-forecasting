
# ================================================================
# backend/auth.py — Authentication via Supabase
# ================================================================
# Uses ONLY Supabase built-in Google OAuth (sign_in_with_oauth).
# No manual OAuth flow, no Google Client ID/Secret needed here.
#
# Supabase dashboard setup required:
#   Authentication → Providers → Google → Enable
#   Set your Google Client ID + Secret there.
#   Add redirect URL: https://<your-app>.streamlit.app/
# ================================================================

import os
import streamlit as st
from supabase import create_client, Client

# ── Supabase client ──────────────────────────────────────────────

def _get_supabase() -> Client:
    url  = st.secrets.get("SUPABASE_URL",      os.environ.get("SUPABASE_URL", ""))
    key  = st.secrets.get("SUPABASE_ANON_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))
    if not url or not key:
        raise RuntimeError(
            "Supabase credentials missing. "
            "Add SUPABASE_URL and SUPABASE_ANON_KEY to Streamlit secrets or .env"
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
    """Return True if the logged-in user has the admin role."""
    return (
        bool(st.session_state.get("authenticated")) and
        st.session_state.get("role") == "admin"
    )


def get_current_user() -> dict:
    """Return a dict of the current user's session data (safe to pass around)."""
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
        user.email.split("@")[0]
    )
    st.session_state.role          = meta.get("role", "analyst")
    st.session_state.jwt_token     = session.access_token if session else None
    st.session_state.demo_mode     = False
    st.session_state.current_page  = "home"


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
            _set_session_from_supabase(res.user, res.session)
            return True, {
                "message": "Account created successfully! Welcome 🎉",
                "user":    {
                    "id":        res.user.id,
                    "email":     res.user.email,
                    "full_name": full_name,
                    "role":      role,
                },
                "session": {"access_token": res.session.access_token if res.session else None},
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
                "user":    {
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
        if "invalid" in msg.lower() or "credentials" in msg.lower():
            return False, {"message": "Invalid email or password."}
        return False, {"message": f"Login error: {msg}"}


def auth_forgot_password(email: str):
    """Send a password reset email."""
    try:
        supabase = _get_supabase()
        supabase.auth.reset_password_email(email)
        return True, "Password reset email sent. Check your inbox."
    except Exception as e:
        return False, f"Error: {e}"


def auth_logout():
    """Sign out and clear session."""
    try:
        supabase = _get_supabase()
        supabase.auth.sign_out()
    except Exception:
        pass
    for key in ["authenticated", "user_id", "email", "full_name",
                "role", "jwt_token", "demo_mode", "current_page"]:
        st.session_state[key] = None
    st.session_state.authenticated = False


# ── Google OAuth via Supabase ────────────────────────────────────

def auth_google_login_url() -> str:
    """
    Return the Supabase Google OAuth URL.
    Supabase handles the entire OAuth handshake — no manual Client ID needed.

    The redirect_to must match one of the URLs you have whitelisted in:
      Supabase → Authentication → URL Configuration → Redirect URLs
    and also in:
      Google Cloud Console → OAuth Client → Authorised redirect URIs
      (use the Supabase callback URL shown in Supabase dashboard, NOT the Streamlit URL)
    """
    try:
        supabase  = _get_supabase()
        site_url  = st.secrets.get(
            "SITE_URL",
            os.environ.get("SITE_URL", "https://deploy-financial66.streamlit.app/")
        )
        res = supabase.auth.sign_in_with_oauth({
            "provider":    "google",
            "options": {
                "redirect_to": site_url,
                "scopes":      "email profile",
            },
        })
        return res.url
    except Exception as e:
        # Fallback: return a safe error URL that shows a message
        return f"?google_error={e}"


def auth_handle_google_callback():
    """
    Called on every page load.
    Reads the ?code= or ?access_token= / ?refresh_token= params that
    Supabase injects after a successful Google sign-in redirect,
    then creates the local session.

    Returns True if a session was created, False otherwise.
    """
    params = st.query_params

    # ── Supabase can return an error ────────────────────────────
    error = params.get("error")
    if error:
        desc = params.get("error_description", error)
        st.error(f"Google sign-in failed: {desc}")
        st.query_params.clear()
        return False

    # ── Supabase PKCE / implicit flow: access_token in fragment ─
    # Streamlit can't read URL fragments (they never reach the server),
    # so Supabase is configured to use the "PKCE" flow which sends
    # ?code= as a query param.  Handle that here.
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
                st.error("Google sign-in: could not exchange code for session.")
                st.query_params.clear()
                return False
        except Exception as e:
            st.error(f"Google sign-in error: {e}")
            st.query_params.clear()
            return False

    # ── Legacy: token passed directly (older Supabase implicit flow) ─
    token = params.get("access_token")
    if token:
        try:
            supabase = _get_supabase()
            res = supabase.auth.get_user(token)
            if res.user:
                # Reconstruct a minimal session-like object
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


# ── Token verification (used by demo / other callers) ───────────

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
