# ================================================================
# backend/auth.py  —  HTTP-Based JWT Authentication
# ================================================================
# Communicates with backend/server.py (FastAPI) for auth operations.
# Token issued by server is stored in Streamlit session state.
# ================================================================

import hashlib
import re
import uuid
import streamlit as st
import requests
from typing import Any, Dict, Optional
from config.settings import SHARED_EMAIL_BASE

AUTH_SERVER_URL = "http://localhost:8000"


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

    # Extract from response dict
    if isinstance(response, dict):
        payload["user"] = response.get("user")
        payload["session"] = {"access_token": response.get("token")} if response.get("token") else None

    return payload


def _build_shared_email(account: str) -> str:
    if not SHARED_EMAIL_BASE or "@" not in SHARED_EMAIL_BASE:
        raise ValueError("Shared email base is not configured. Set SHARED_EMAIL_BASE in .env.")
    local, domain = SHARED_EMAIL_BASE.split("@", 1)
    key = account.strip().lower().replace(" ", "_")
    key = re.sub(r"[^a-z0-9._+-]", "", key)
    if not key:
        raise ValueError("Account name must include letters or numbers.")
    return f"{local}+{key}@{domain}"


# ── Session ───────────────────────────────────────────────────

def init_session():
    defaults = {
        "authenticated": False,
        "user_id":       None,
        "email":         None,
        "full_name":     None,
        "role":          None,
        "jwt_token":     None,   # JWT token from auth server
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
    """Get headers with JWT token for API requests."""
    token = st.session_state.get("jwt_token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


# ── Auth Actions ──────────────────────────────────────────────

def auth_register(account, password, username, role="analyst"):
    """Register new user via HTTP auth server."""
    if len(password) < 6:
        return False, _build_auth_payload(None, "Password must be at least 6 characters.", success=False)
    try:
        account = account.strip()
        if not account:
            return False, _build_auth_payload(None, "Please enter an account name or email.", success=False)

        # Call auth server
        response = requests.post(
            f"{AUTH_SERVER_URL}/auth/register",
            json={
                "account": account,
                "password": password,
                "full_name": username,
                "role": role,
            },
            timeout=10,
        )

        if response.status_code != 200:
            error_data = response.json()
            error_msg = error_data.get("detail", "Registration failed")
            return False, _build_auth_payload(None, error_msg, success=False, raw_error=error_msg)

        data = response.json()
        if data.get("success"):
            user = data.get("user")
            token = data.get("token")
            return True, _build_auth_payload(
                {"user": user, "token": token},
                data.get("message"),
                success=True,
            )
        else:
            return False, _build_auth_payload(None, data.get("message", "Registration failed"), success=False)

    except requests.exceptions.ConnectionError:
        return False, _build_auth_payload(None, "Auth server unavailable. Is it running on port 8000?", success=False, raw_error="Connection failed")
    except requests.exceptions.Timeout:
        return False, _build_auth_payload(None, "Auth server request timed out.", success=False, raw_error="Timeout")
    except Exception as e:
        return False, _build_auth_payload(None, f"Registration error: {e}", success=False, raw_error=str(e))


def auth_login(account, password):
    """Login user via HTTP auth server."""
    try:
        account = account.strip()
        if not account:
            return False, _build_auth_payload(None, "Please enter account or email.", success=False)

        # Call auth server
        response = requests.post(
            f"{AUTH_SERVER_URL}/auth/login",
            json={
                "account": account,
                "password": password,
            },
            timeout=10,
        )

        if response.status_code != 200:
            error_data = response.json()
            error_msg = error_data.get("detail", "Login failed")
            return False, _build_auth_payload(None, error_msg, success=False, raw_error=error_msg)

        data = response.json()
        if data.get("success"):
            user = data.get("user")
            token = data.get("token")
            return True, _build_auth_payload(
                {"user": user, "token": token},
                data.get("message"),
                success=True,
            )
        else:
            return False, _build_auth_payload(None, data.get("message", "Login failed"), success=False)

    except requests.exceptions.ConnectionError:
        return False, _build_auth_payload(None, "Auth server unavailable. Is it running on port 8000?", success=False, raw_error="Connection failed")
    except requests.exceptions.Timeout:
        return False, _build_auth_payload(None, "Auth server request timed out.", success=False, raw_error="Timeout")
    except Exception as e:
        return False, _build_auth_payload(None, f"Login error: {e}", success=False, raw_error=str(e))


def auth_forgot_password(account: str):
    """Placeholder for password reset support."""
    if not account or not account.strip():
        return False, "Please enter an account name or email."

    # TODO: implement password reset flow via auth server / email.
    return False, (
        "Password reset is not yet available. "
        "Please contact the administrator or register a new account."
    )


def auth_verify_token(token: str):
    """Verify a JWT token via auth server."""
    try:
        response = requests.get(
            f"{AUTH_SERVER_URL}/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if response.status_code != 200:
            error_data = response.json()
            return False, error_data.get("detail", "Token verification failed")

        data = response.json()
        if data.get("success"):
            return True, {"user": data.get("user"), "token": token}
        return False, data.get("message", "Token verification failed")

    except requests.exceptions.ConnectionError:
        return False, "Auth server unavailable. Is it running on port 8000?"
    except requests.exceptions.Timeout:
        return False, "Auth server request timed out."
    except Exception as e:
        return False, f"Token verification error: {e}"


