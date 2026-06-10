# ================================================================
# backend/server.py  —  JWT Auth Server (FastAPI)
# ================================================================
# Run with:  python -m uvicorn backend.server:app --reload --port 8000
#
# Endpoints:
#   POST /auth/register  →  Register user, return JWT
#   POST /auth/login     →  Login user, return JWT
#   GET  /auth/verify    →  Verify token validity
# ================================================================

import os
import uuid
import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import jwt
import requests
from backend.database import get_db, db_get_user_by_email, db_upsert_user
from config.settings import SHARED_EMAIL_BASE, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI

# ── Constants ─────────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

app = FastAPI(title="Sales Forecasting Auth Server", version="1.0.0")

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    account: str
    password: str
    full_name: str
    role: str = "analyst"


class LoginRequest(BaseModel):
    account: str
    password: str


class AuthResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ── JWT Helpers ───────────────────────────────────────────────

def _build_shared_email(account: str) -> str:
    """Build shared Gmail alias from account name."""
    if not SHARED_EMAIL_BASE or "@" not in SHARED_EMAIL_BASE:
        raise ValueError("Shared email base is not configured. Set SHARED_EMAIL_BASE in .env.")
    local, domain = SHARED_EMAIL_BASE.split("@", 1)
    key = account.strip().lower().replace(" ", "_")
    key = re.sub(r"[^a-z0-9._+-]", "", key)
    if not key:
        raise ValueError("Account name must include letters or numbers.")
    return f"{local}+{key}@{domain}"


def _hash_password(password: str) -> str:
    """Hash password using SHA256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _create_jwt(user_id: str, email: str, full_name: str, role: str) -> str:
    """Create JWT token."""
    expiry = datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    payload = {
        "user_id": user_id,
        "email": email,
        "full_name": full_name,
        "role": role,
        "exp": expiry,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_jwt(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _get_token_from_request(request: Request) -> str:
    """Extract token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return auth_header[7:]


def _google_auth_url() -> str:
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth is not configured.")
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
    try:
        token_resp.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Google token exchange failed: {e}")

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Google did not return an access token.")

    profile_resp = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    try:
        profile_resp.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Google profile fetch failed: {e}")

    return profile_resp.json()


# ── Routes ────────────────────────────────────────────────────

@app.post("/auth/register", response_model=AuthResponse)
def register(req: RegisterRequest):
    """Register a new user and return JWT token."""
    if len(req.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters."
        )

    try:
        account = req.account.strip()
        if not account:
            raise HTTPException(status_code=400, detail="Account name required.")

        # Build email
        if "@" in account:
            email = account.lower()
        else:
            email = _build_shared_email(account)

        # Check if already exists
        existing = db_get_user_by_email(email.lower())
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Account already registered. Please log in."
            )

        # Create user
        user_id = str(uuid.uuid4())
        password_hash = _hash_password(req.password)
        success, db_error = db_upsert_user(user_id, email.lower(), req.full_name, req.role, password_hash=password_hash)

        if not success:
            raise HTTPException(status_code=500, detail=f"Registration failed: {db_error}")

        # Generate token
        token = _create_jwt(user_id, email.lower(), req.full_name, req.role)

        return AuthResponse(
            success=True,
            message=f"Account created! Token issued for {email.lower()}",
            token=token,
            user={
                "id": user_id,
                "email": email.lower(),
                "full_name": req.full_name,
                "role": req.role,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration error: {str(e)}")


@app.post("/auth/login", response_model=AuthResponse)
def login(req: LoginRequest):
    """Login user and return JWT token."""
    try:
        email = req.account.strip().lower()
        if "@" not in email:
            email = _build_shared_email(req.account)

        # Look up user
        user = db_get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=401, detail="Incorrect account or password.")

        # Verify password
        password_hash = _hash_password(req.password)
        stored_hash = user.get("password_hash")
        if stored_hash != password_hash:
            raise HTTPException(status_code=401, detail="Incorrect account or password.")

        # Generate token
        user_id = user.get("id")
        full_name = user.get("full_name") or email.split("@")[0]
        role = user.get("role", "analyst")
        token = _create_jwt(user_id, email, full_name, role)

        return AuthResponse(
            success=True,
            message=f"Welcome back, {full_name}! 👋",
            token=token,
            user={
                "id": user_id,
                "email": email,
                "full_name": full_name,
                "role": role,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login error: {str(e)}")


@app.get("/auth/google/login")
def google_login():
    """Redirect the user to Google's OAuth consent screen."""
    return RedirectResponse(_google_auth_url())


@app.get("/auth/google/callback")
def google_callback(code: Optional[str] = None, error: Optional[str] = None):
    if error:
        raise HTTPException(status_code=400, detail=f"Google auth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    profile = _google_user_info(code)
    email = profile.get("email", "").lower()
    full_name = profile.get("name") or email.split("@")[0]
    if not email:
        raise HTTPException(status_code=400, detail="Google did not return an email.")

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
            raise HTTPException(status_code=500, detail=f"User create failed: {db_error}")
        role = "analyst"
    else:
        user_id = user.get("id")
        role = user.get("role", "analyst")

    token = _create_jwt(user_id, email, full_name, role)
    redirect_url = f"http://localhost:8501/?{urlencode({'token': token})}"
    return RedirectResponse(redirect_url)


@app.get("/auth/verify", response_model=AuthResponse)
def verify_token(request: Request):
    """Verify JWT token validity."""
    try:
        token = _get_token_from_request(request)
        payload = _decode_jwt(token)

        return AuthResponse(
            success=True,
            message="Token is valid",
            user={
                "id": payload.get("user_id"),
                "email": payload.get("email"),
                "full_name": payload.get("full_name"),
                "role": payload.get("role"),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "auth-server"}
