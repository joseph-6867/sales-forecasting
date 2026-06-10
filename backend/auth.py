# ================================================================
# backend/auth.py  —  Streamlit-native JWT Authentication
# ================================================================
# Uses Supabase for user storage and creates/verifies JWTs directly in the app.
# This removes the need for a separate FastAPI auth server.
# ================================================================

import hashlib
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import jwt
import requests
import streamlit as st

from backend.database import db_get_user_by_email, db_upsert_user
from config.settings import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    SHARED_EMAIL_BASE,
    JWT_SECRET,
)

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def _build_auth_payload(
    response: Any,
    message: str,
    success: bool = True,
    raw_error: Optional[str] = None,
    rate_limit: bool = False,
    retry_after: Optional[int] = None,
) -> Dict[str, Any]:
    payload = {
        "success": success,
        "message": message,
        "user": None,
        "session": None,
        "error": raw_error,
        "rate_limit": rate_limit,
        "retry_after": retry_after,
    }

    if response is None:
        return payload

    if isinstance(response, dict):
        payload["user"] = response.get("user")
        payload["session"] = {"access_token": response.get("token")} if response.get("token") else None

    return payload


def _build_shared_email(account: str) -> str:
    if not SHARED_EMAIL_BASE or "@" not in SHARED_EMAIL_BASE:
        raise ValueError("Shared email base is not configured. Set SHARED_EMAIL_BASE in .env or Streamlit secrets.")
    local, domain = SHARED_EMAIL_BASE.split("@", 1)
    key = account.strip().lower().replace(" ", "_")
    key = re.sub(r"[^a-z0-9._+-]", "", key)
    if not key:
        raise ValueError("Account name must include letters or numbers.")
    return f"{local}+{key}@{domain}"


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _create_jwt(user_id: str, email: str, full_name: str, role: str) -> str:
    expiry = datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    payload = {
        "user_id": user_id,
        "email": email,
        "full_name": full_name,
        "role": role,
        "exp": expiry,
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token.decode("utf-8") if isinstance(token, bytes) else token


def _decode_jwt(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def _google_auth_url() -> str:
    if not GOOGLE_CLIENT_ID or not GOOGLE_REDIRECT_URI:
        raise ValueError("Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_REDIRECT_URI.")
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def _google_user_info(code: str) -> Dict[str, Any]:
    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    token_resp.raise_for_status()
    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise ValueError("Google did not return an access token.")

    profile_resp = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    profile_resp.raise_for_status()
    return profile_resp.json()


def auth_google_login_url() -> str:
    return _google_auth_url()


def auth_google_callback(code: str):
    try:
        profile = _google_user_info(code)
        email = profile.get("email", "").lower()
        full_name = profile.get("name") or email.split("@")[0]
        if not email:
            return False, _build_auth_payload(None, "Google did not return an email.", success=False)

        user = db_get_user_by_email(email)
        if not user:
            user_id = str(uuid.uuid4())
            success, db_error = db_upsert_user(
                user_id,
                email,
                full_name,
                "analyst",
                password_hash=None,
            )
            if not success:
                return False, _build_auth_payload(None, f"User create failed: {db_error}", success=False)
            role = "analyst"
        else:
            user_id = user.get("id")
            role = user.get("role", "analyst")

        token = _create_jwt(user_id, email, full_name, role)
        return True, _build_auth_payload(
            {"user": {"id": user_id, "email": email, "full_name": full_name, "role": role}, "token": token},
            "Google sign-in successful.",
            success=True,
        )
    except Exception as e:
        return False, _build_auth_payload(None, f"Google sign-in failed: {e}", success=False, raw_error=str(e))


def init_session():
    defaults = {
        "authenticated": False,
        "user_id":       None,
        "email":         None,
        "full_name":     None,
        "role":          None,
        "jwt_token":     None,
        "current_page":  "home",
        "active_project":None,
        "active_df":     None,
        "demo_mode":     False,
        "col_map":       {},
        "trained_models":{},
        "forecast_results":{},
        "register_cooldown": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def set_session(user_id, email, full_name, role, jwt_token):
    st.session_state.authenticated = True
    st.session_state.user_id       = user_id
    st.session_state.email         = email
    st.session_state.full_name     = full_name
    st.session_state.role          = role
    st.session_state.jwt_token     = jwt_token
    st.session_state.current_page  = "dashboard"


def clear_session():
    st.session_state.authenticated   = False
    st.session_state.user_id         = None
    st.session_state.email           = None
    st.session_state.full_name       = None
    st.session_state.role            = None
    st.session_state.jwt_token       = None
    st.session_state.active_project  = None
    st.session_state.active_df       = None
    st.session_state.demo_mode       = False
    st.session_state.col_map         = {}
    st.session_state.trained_models  = {}
    st.session_state.forecast_results = {}
    st.session_state.current_page    = "home"


def auth_logout():
    """Logout helper for Streamlit UI."""
    clear_session()


def is_auth():
    return bool(st.session_state.get("authenticated") and
                st.session_state.get("user_id") and
                st.session_state.get("jwt_token"))


def require_auth():
    if not is_auth():
        st.warning("🔒 Please log in to continue.")
        st.stop()


def is_admin():
    return st.session_state.get("role") == "admin"


def get_auth_headers():
    token = st.session_state.get("jwt_token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def auth_register(account, password, username, role="analyst"):
    if len(password) < 6:
        return False, _build_auth_payload(None, "Password must be at least 6 characters.", success=False)
    try:
        account = account.strip()
        if not account:
            return False, _build_auth_payload(None, "Please enter an account name or email.", success=False)

        if "@" in account:
            email = account.lower()
        else:
            email = _build_shared_email(account)

        existing = db_get_user_by_email(email)
        if existing:
            return False, _build_auth_payload(None, "Account already registered. Please log in.", success=False)

        user_id = str(uuid.uuid4())
        password_hash = _hash_password(password)
        success, db_error = db_upsert_user(user_id, email, username, role, password_hash=password_hash)
        if not success:
            return False, _build_auth_payload(None, f"Registration failed: {db_error}", success=False)

        token = _create_jwt(user_id, email, username, role)
        return True, _build_auth_payload(
            {"user": {"id": user_id, "email": email, "full_name": username, "role": role}, "token": token},
            f"Account created! Token issued for {email}",
            success=True,
        )
    except Exception as e:
        return False, _build_auth_payload(None, f"Registration error: {e}", success=False, raw_error=str(e))


def auth_login(account, password):
    try:
        account = account.strip()
        if not account:
            return False, _build_auth_payload(None, "Please enter account or email.", success=False)

        if "@" in account:
            email = account.lower()
        else:
            email = _build_shared_email(account)

        user = db_get_user_by_email(email)
        if not user:
            return False, _build_auth_payload(None, "Incorrect account or password.", success=False)

        password_hash = _hash_password(password)
        if user.get("password_hash") != password_hash:
            return False, _build_auth_payload(None, "Incorrect account or password.", success=False)

        user_id = user.get("id")
        full_name = user.get("full_name") or email.split("@")[0]
        role = user.get("role", "analyst")
        token = _create_jwt(user_id, email, full_name, role)

        return True, _build_auth_payload(
            {"user": {"id": user_id, "email": email, "full_name": full_name, "role": role}, "token": token},
            f"Welcome back, {full_name}! 👋",
            success=True,
        )
    except Exception as e:
        return False, _build_auth_payload(None, f"Login error: {e}", success=False, raw_error=str(e))


def auth_forgot_password(account: str):
    if not account or not account.strip():
        return False, "Please enter an account name or email."

    return False, (
        "Password reset is not yet available. "
        "Please contact the administrator or register a new account."
    )


def auth_verify_token(token: str):
    payload = _decode_jwt(token)
    if not payload:
        return False, "Token invalid or expired"

    user = {
        "id": payload.get("user_id"),
        "email": payload.get("email"),
        "full_name": payload.get("full_name"),
        "role": payload.get("role"),
    }
    return True, _build_auth_payload({"user": user, "token": token}, "Token is valid", success=True)

...

