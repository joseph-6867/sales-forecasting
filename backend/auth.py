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
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)

    st.session_state.authenticated  = False
    st.session_state.demo_mode      = False
    st.session_state.current_page   = "home"
    st.session_state.active_project = None
    st.session_state.active_df      = None
    st.session_state.col_map        = {}


# ── Google OAuth ─────────────────────────────────────────────────

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


def auth_google_login_url() -> str:
    """
    Returns the Supabase Google OAuth URL using the IMPLICIT flow
    (no PKCE, no custom state).

    Why implicit / no-PKCE:
      PKCE requires the code_verifier to be present when the callback
      lands.  Supabase stores its own verifier in JS localStorage, but
      supabase-py stores it in an in-process MemoryStorage that is tied
      to the client instance.  When Google redirects back, Streamlit
      spins up a brand-new Python process (or at minimum a new session),
      the client is recreated, MemoryStorage is empty, and the exchange
      fails with `bad_oauth_state`.

    The server-side (no-PKCE) flow works because:
      - Supabase issues a short-lived auth code tied to its own server session
      - We exchange it directly at /auth/v1/token without needing a verifier
      - Security is maintained by the short code lifetime + HTTPS
    """
    import urllib.parse

    supabase_url = _get_supabase_url().rstrip("/")
    site_url     = _get_site_url()

    params = urllib.parse.urlencode({
        "provider":    "google",
        "redirect_to": site_url,
        "scopes":      "email profile",
    })

    return f"{supabase_url}/auth/v1/authorize?{params}"


def auth_handle_google_callback() -> bool:
    """
    Handles the OAuth callback.

    Supabase can redirect back in two ways depending on project settings:

    1. PKCE / server flow  → ?code=<auth_code>  in query params
    2. Implicit flow       → #access_token=...  in the URL fragment

    Fragments (#...) are never sent to the server, so Streamlit cannot
    see them via st.query_params.  We therefore use the code-exchange
    path (option 1) but WITHOUT a PKCE code_verifier — Supabase accepts
    this when the project's auth flow is set to "Implicit" or when no
    challenge was included in the original authorize request.
    """
    params = st.query_params

    # ── Handle explicit errors from Supabase / Google ────────────
    error = params.get("error")
    if error:
        desc = params.get("error_description", error)
        st.error(f"Google sign-in failed: {desc}")
        st.query_params.clear()
        return False

    # ── Code-exchange flow ───────────────────────────────────────
    code = params.get("code")
    if not code:
        return False   # No callback params — normal page load

    try:
        supabase_url = _get_supabase_url().rstrip("/")
        try:
            key = st.secrets.get("SUPABASE_ANON_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")
        except Exception:
            key = os.environ.get("SUPABASE_ANON_KEY", "")

        import httpx

        # Exchange the auth code for tokens — no code_verifier needed
        # because we did not send a code_challenge in the authorize request
        resp = httpx.post(
            f"{supabase_url}/auth/v1/token?grant_type=authorization_code",
            headers={
                "apikey":       key,
                "Content-Type": "application/json",
            },
            json={"code": code},
            timeout=15,
        )

        if resp.status_code != 200:
            # Supabase may require the pkce grant_type even without a verifier
            # on some project configurations — try the pkce endpoint with an
            # empty verifier as a fallback.
            resp2 = httpx.post(
                f"{supabase_url}/auth/v1/token?grant_type=pkce",
                headers={
                    "apikey":       key,
                    "Content-Type": "application/json",
                },
                json={
                    "auth_code":     code,
                    "code_verifier": "",
                },
                timeout=15,
            )
            if resp2.status_code == 200:
                resp = resp2
            else:
                st.error(
                    f"Google sign-in failed (HTTP {resp.status_code}).\n\n"
                    f"**Fix:** In your Supabase dashboard → Authentication → "
                    f"URL Configuration, set the Auth Flow to **Implicit** "
                    f"and add `{_get_site_url()}` to the Redirect URLs allow-list."
                )
                st.query_params.clear()
                return False

        data         = resp.json()
        access_token = data.get("access_token")

        if not access_token:
            st.error(
                f"Google sign-in: no access_token in response.\n\n"
                f"Response: `{data}`\n\n"
                f"**Fix:** In Supabase → Authentication → URL Configuration, "
                f"set Auth Flow to **Implicit** and whitelist `{_get_site_url()}`."
            )
            st.query_params.clear()
            return False

        # ── Get user info ────────────────────────────────────────
        supabase = _get_supabase()
        user_res = supabase.auth.get_user(access_token)

        if not user_res or not user_res.user:
            st.error("Google sign-in: could not retrieve user from access token.")
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
