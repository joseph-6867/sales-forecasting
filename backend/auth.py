# # ================================================================
# # backend/auth.py  —  Streamlit-native JWT Authentication
# # ================================================================
# # Uses Supabase for user storage and creates/verifies JWTs directly in the app.
# # This removes the need for a separate FastAPI auth server.
# # ================================================================

# import hashlib
# import re
# import uuid
# from datetime import datetime, timedelta
# from typing import Any, Dict, Optional
# from urllib.parse import urlencode

# import jwt
# import requests
# import streamlit as st

# from backend.database import db_get_user_by_email, db_upsert_user
# from config.settings import (
#     GOOGLE_CLIENT_ID,
#     GOOGLE_CLIENT_SECRET,
#     GOOGLE_REDIRECT_URI,
#     SHARED_EMAIL_BASE,
#     JWT_SECRET,
# )

# JWT_ALGORITHM = "HS256"
# JWT_EXPIRY_HOURS = 24


# def _build_auth_payload(
#     response: Any,
#     message: str,
#     success: bool = True,
#     raw_error: Optional[str] = None,
#     rate_limit: bool = False,
#     retry_after: Optional[int] = None,
# ) -> Dict[str, Any]:
#     payload = {
#         "success": success,
#         "message": message,
#         "user": None,
#         "session": None,
#         "error": raw_error,
#         "rate_limit": rate_limit,
#         "retry_after": retry_after,
#     }

#     if response is None:
#         return payload

#     if isinstance(response, dict):
#         payload["user"] = response.get("user")
#         payload["session"] = {"access_token": response.get("token")} if response.get("token") else None

#     return payload


# def _build_shared_email(account: str) -> str:
#     if not SHARED_EMAIL_BASE or "@" not in SHARED_EMAIL_BASE:
#         raise ValueError("Shared email base is not configured. Set SHARED_EMAIL_BASE in .env or Streamlit secrets.")
#     local, domain = SHARED_EMAIL_BASE.split("@", 1)
#     key = account.strip().lower().replace(" ", "_")
#     key = re.sub(r"[^a-z0-9._+-]", "", key)
#     if not key:
#         raise ValueError("Account name must include letters or numbers.")
#     return f"{local}+{key}@{domain}"


# def _hash_password(password: str) -> str:
#     return hashlib.sha256(password.encode("utf-8")).hexdigest()


# def _create_jwt(user_id: str, email: str, full_name: str, role: str) -> str:
#     expiry = datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
#     payload = {
#         "user_id": user_id,
#         "email": email,
#         "full_name": full_name,
#         "role": role,
#         "exp": expiry,
#         "iat": datetime.utcnow(),
#     }
#     token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
#     return token.decode("utf-8") if isinstance(token, bytes) else token


# def _decode_jwt(token: str) -> Optional[Dict[str, Any]]:
#     try:
#         return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
#     except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
#         return None


# def _google_auth_url() -> str:
#     if not GOOGLE_CLIENT_ID or not GOOGLE_REDIRECT_URI:
#         raise ValueError("Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_REDIRECT_URI.")
#     params = {
#         "client_id": GOOGLE_CLIENT_ID,
#         "redirect_uri": GOOGLE_REDIRECT_URI,
#         "response_type": "code",
#         "scope": "openid email profile",
#         "access_type": "offline",
#         "prompt": "select_account",
#     }
#     return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


# def _google_user_info(code: str) -> Dict[str, Any]:
#     try:
#         token_resp = requests.post(
#             "https://oauth2.googleapis.com/token",
#             data={
#                 "code": code,
#                 "client_id": GOOGLE_CLIENT_ID,
#                 "client_secret": GOOGLE_CLIENT_SECRET,
#                 "redirect_uri": GOOGLE_REDIRECT_URI,
#                 "grant_type": "authorization_code",
#             },
#             timeout=10,
#         )
#         token_resp.raise_for_status()
#         token_data = token_resp.json()
#     except requests.HTTPError as http_err:
#         # Include response body to aid debugging (common cause: redirect_uri mismatch)
#         resp_text = None
#         try:
#             resp_text = token_resp.text
#         except Exception:
#             resp_text = str(http_err)
#         raise ValueError(f"Google token exchange failed: {http_err} - {resp_text}")
#     access_token = token_data.get("access_token")
#     if not access_token:
#         raise ValueError("Google did not return an access token.")

#     profile_resp = requests.get(
#         "https://www.googleapis.com/oauth2/v3/userinfo",
#         headers={"Authorization": f"Bearer {access_token}"},
#         timeout=10,
#     )
#     profile_resp.raise_for_status()
#     return profile_resp.json()


# def auth_google_login_url() -> str:
#     return _google_auth_url()


# def auth_google_callback(code: str):
#     try:
#         profile = _google_user_info(code)
#         email = profile.get("email", "").lower()
#         full_name = profile.get("name") or email.split("@")[0]
#         if not email:
#             return False, _build_auth_payload(None, "Google did not return an email.", success=False)

#         user = db_get_user_by_email(email)
#         if not user:
#             user_id = str(uuid.uuid4())
#             success, db_error = db_upsert_user(
#                 user_id,
#                 email,
#                 full_name,
#                 "analyst",
#                 password_hash=None,
#             )
#             if not success:
#                 return False, _build_auth_payload(None, f"User create failed: {db_error}", success=False)
#             role = "analyst"
#         else:
#             user_id = user.get("id")
#             role = user.get("role", "analyst")

#         token = _create_jwt(user_id, email, full_name, role)
#         return True, _build_auth_payload(
#             {"user": {"id": user_id, "email": email, "full_name": full_name, "role": role}, "token": token},
#             "Google sign-in successful.",
#             success=True,
#         )
#     except Exception as e:
#         return False, _build_auth_payload(None, f"Google sign-in failed: {e}", success=False, raw_error=str(e))


# def init_session():
#     defaults = {
#         "authenticated": False,
#         "user_id":       None,
#         "email":         None,
#         "full_name":     None,
#         "role":          None,
#         "jwt_token":     None,
#         "current_page":  "home",
#         "active_project":None,
#         "active_df":     None,
#         "demo_mode":     False,
#         "col_map":       {},
#         "trained_models":{},
#         "forecast_results":{},
#         "register_cooldown": 0,
#     }
#     for k, v in defaults.items():
#         if k not in st.session_state:
#             st.session_state[k] = v


# def set_session(user_id, email, full_name, role, jwt_token):
#     st.session_state.authenticated = True
#     st.session_state.user_id       = user_id
#     st.session_state.email         = email
#     st.session_state.full_name     = full_name
#     st.session_state.role          = role
#     st.session_state.jwt_token     = jwt_token
#     st.session_state.current_page  = "dashboard"


# def clear_session():
#     st.session_state.authenticated   = False
#     st.session_state.user_id         = None
#     st.session_state.email           = None
#     st.session_state.full_name       = None
#     st.session_state.role            = None
#     st.session_state.jwt_token       = None
#     st.session_state.active_project  = None
#     st.session_state.active_df       = None
#     st.session_state.demo_mode       = False
#     st.session_state.col_map         = {}
#     st.session_state.trained_models  = {}
#     st.session_state.forecast_results = {}
#     st.session_state.current_page    = "home"


# def auth_logout():
#     """Logout helper for Streamlit UI."""
#     clear_session()


# def is_auth():
#     return bool(st.session_state.get("authenticated") and
#                 st.session_state.get("user_id") and
#                 st.session_state.get("jwt_token"))


# def require_auth():
#     if not is_auth():
#         st.warning("🔒 Please log in to continue.")
#         st.stop()


# def is_admin():
#     return st.session_state.get("role") == "admin"


# def get_auth_headers():
#     token = st.session_state.get("jwt_token")
#     if token:
#         return {"Authorization": f"Bearer {token}"}
#     return {}


# def auth_register(account, password, username, role="analyst"):
#     if len(password) < 6:
#         return False, _build_auth_payload(None, "Password must be at least 6 characters.", success=False)
#     try:
#         account = account.strip()
#         if not account:
#             return False, _build_auth_payload(None, "Please enter an account name or email.", success=False)

#         if "@" in account:
#             email = account.lower()
#         else:
#             email = _build_shared_email(account)

#         existing = db_get_user_by_email(email)
#         if existing:
#             return False, _build_auth_payload(None, "Account already registered. Please log in.", success=False)

#         user_id = str(uuid.uuid4())
#         password_hash = _hash_password(password)
#         success, db_error = db_upsert_user(user_id, email, username, role, password_hash=password_hash)
#         if not success:
#             return False, _build_auth_payload(None, f"Registration failed: {db_error}", success=False)

#         token = _create_jwt(user_id, email, username, role)
#         return True, _build_auth_payload(
#             {"user": {"id": user_id, "email": email, "full_name": username, "role": role}, "token": token},
#             f"Account created! Token issued for {email}",
#             success=True,
#         )
#     except Exception as e:
#         return False, _build_auth_payload(None, f"Registration error: {e}", success=False, raw_error=str(e))


# def auth_login(account, password):
#     try:
#         account = account.strip()
#         if not account:
#             return False, _build_auth_payload(None, "Please enter account or email.", success=False)

#         if "@" in account:
#             email = account.lower()
#         else:
#             email = _build_shared_email(account)

#         user = db_get_user_by_email(email)
#         if not user:
#             return False, _build_auth_payload(None, "Incorrect account or password.", success=False)

#         password_hash = _hash_password(password)
#         if user.get("password_hash") != password_hash:
#             return False, _build_auth_payload(None, "Incorrect account or password.", success=False)

#         user_id = user.get("id")
#         full_name = user.get("full_name") or email.split("@")[0]
#         role = user.get("role", "analyst")
#         token = _create_jwt(user_id, email, full_name, role)

#         return True, _build_auth_payload(
#             {"user": {"id": user_id, "email": email, "full_name": full_name, "role": role}, "token": token},
#             f"Welcome back, {full_name}! 👋",
#             success=True,
#         )
#     except Exception as e:
#         return False, _build_auth_payload(None, f"Login error: {e}", success=False, raw_error=str(e))


# def auth_forgot_password(account: str):
#     if not account or not account.strip():
#         return False, "Please enter an account name or email."

#     return False, (
#         "Password reset is not yet available. "
#         "Please contact the administrator or register a new account."
#     )


# def auth_verify_token(token: str):
#     payload = _decode_jwt(token)
#     if not payload:
#         return False, "Token invalid or expired"

#     user = {
#         "id": payload.get("user_id"),
#         "email": payload.get("email"),
#         "full_name": payload.get("full_name"),
#         "role": payload.get("role"),
#     }
#     return True, _build_auth_payload({"user": user, "token": token}, "Token is valid", success=True)

# ...



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
