# ================================================================
# backend/auth.py — Authentication via Supabase
# ================================================================

import os
import hashlib
import base64
import secrets
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


# ── PKCE helpers ─────────────────────────────────────────────────

def _generate_pkce_pair() -> tuple[str, str]:
    """
    Generate a PKCE code_verifier and code_challenge pair.
    - code_verifier : 32 random bytes → base64url (no padding)
    - code_challenge: SHA-256(verifier) → base64url (no padding)
    """
    code_verifier  = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest         = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


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


def _get_supabase_url() -> str:
    try:
        return st.secrets.get("SUPABASE_URL", "") or os.environ.get("SUPABASE_URL", "")
    except Exception:
        return os.environ.get("SUPABASE_URL", "")


def auth_google_login_url() -> str:
    """
    Builds the Google OAuth URL with PKCE, encoding the verifier inside
    the `state` query parameter so it survives the cross-tab redirect.

    WHY STATE PARAM:
      Streamlit creates a brand-new session for every browser tab, so
      st.session_state is empty when the OAuth callback lands.
      By embedding the verifier in the `state` param we round-trip it
      through Google → Supabase → back to our app inside the URL itself,
      with no reliance on session storage across tabs.

    STATE FORMAT:  base64url( verifier + "." + random_nonce )
      - verifier  : the PKCE code_verifier
      - nonce     : 8 random bytes for CSRF protection
    """
    import urllib.parse

    supabase_url = _get_supabase_url().rstrip("/")
    site_url     = _get_site_url()

    code_verifier, code_challenge = _generate_pkce_pair()

    # Embed verifier in state so it survives the redirect to a new Streamlit session
    nonce      = base64.urlsafe_b64encode(secrets.token_bytes(8)).rstrip(b"=").decode()
    state_data = f"{code_verifier}.{nonce}"
    state      = base64.urlsafe_b64encode(state_data.encode()).rstrip(b"=").decode()

    params = urllib.parse.urlencode({
        "provider":              "google",
        "redirect_to":           site_url,
        "scopes":                "email profile",
        "code_challenge":        code_challenge,
        "code_challenge_method": "S256",
        "state":                 state,
    })

    return f"{supabase_url}/auth/v1/authorize?{params}"


def auth_handle_google_callback() -> bool:
    """
    Exchanges the ?code= from Supabase using the PKCE verifier that was
    encoded in the ?state= parameter — no session state required.
    """
    params = st.query_params

    error = params.get("error")
    if error:
        desc = params.get("error_description", error)
        st.error(f"Google sign-in failed: {desc}")
        st.query_params.clear()
        return False

    code = params.get("code")
    if not code:
        return False

    # ── Recover verifier from the state param ────────────────────
    state_raw = params.get("state", "")
    verifier  = None

    if state_raw:
        try:
            # Add padding back before decoding
            padded    = state_raw + "=" * (-len(state_raw) % 4)
            decoded   = base64.urlsafe_b64decode(padded).decode()
            # Format: "<verifier>.<nonce>"
            verifier  = decoded.rsplit(".", 1)[0]
        except Exception:
            verifier = None

    # ── Fallback: check session state (same-tab flow) ────────────
    if not verifier:
        verifier = st.session_state.get("_oauth_code_verifier")

    if not verifier:
        st.error(
            "Sign-in session expired — could not recover the PKCE verifier. "
            "Please try signing in again."
        )
        st.query_params.clear()
        return False

    # ── Load credentials ─────────────────────────────────────────
    try:
        supabase_url = st.secrets.get("SUPABASE_URL", "") or os.environ.get("SUPABASE_URL", "")
        key          = st.secrets.get("SUPABASE_ANON_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")
    except Exception:
        supabase_url = os.environ.get("SUPABASE_URL", "")
        key          = os.environ.get("SUPABASE_ANON_KEY", "")

    supabase_url = supabase_url.rstrip("/")

    # ── Exchange code + verifier at Supabase token endpoint ──────
    import httpx
    try:
        resp = httpx.post(
            f"{supabase_url}/auth/v1/token?grant_type=pkce",
            headers={
                "apikey":       key,
                "Content-Type": "application/json",
            },
            json={
                "auth_code":     code,
                "code_verifier": verifier,
            },
            timeout=15,
        )

        if resp.status_code != 200:
            st.error(f"Google sign-in failed (HTTP {resp.status_code}): {resp.text}")
            st.query_params.clear()
            st.session_state.pop("_oauth_code_verifier", None)
            return False

        data          = resp.json()
        access_token  = data.get("access_token")

        if not access_token:
            st.error(f"Google sign-in: no access token in response. Response: {data}")
            st.query_params.clear()
            st.session_state.pop("_oauth_code_verifier", None)
            return False

        # ── Fetch user info via the token ────────────────────────
        supabase = _get_supabase()
        user_res = supabase.auth.get_user(access_token)

        if not user_res.user:
            st.error("Google sign-in: could not retrieve user from token.")
            st.query_params.clear()
            st.session_state.pop("_oauth_code_verifier", None)
            return False

        class _Session:
            def __init__(self, token):
                self.access_token = token

        _set_session_from_supabase(user_res.user, _Session(access_token))
        st.session_state.pop("_oauth_code_verifier", None)
        st.query_params.clear()
        return True

    except Exception as e:
        import traceback
        st.error(f"Google sign-in error: {e}")
        st.code(traceback.format_exc(), language="python")
        st.query_params.clear()
        st.session_state.pop("_oauth_code_verifier", None)
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
