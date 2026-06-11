# ================================================================
# backend/auth.py
# ================================================================

import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def init_supabase() -> Client:
    """Initialize and cache the Supabase client."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
        return create_client(url, key)
    except KeyError:
        st.error("🚨 Supabase credentials not found in st.secrets. Please configure SUPABASE_URL and SUPABASE_ANON_KEY.")
        st.stop()

def init_session():
    """Fallback initialization if needed outside app.py DEFAULTS."""
    pass

def is_auth() -> bool:
    """Check if the user is currently authenticated."""
    return st.session_state.get("authenticated", False)

def auth_login(email: str, password: str) -> tuple[bool, dict]:
    """Authenticates a user with email and password."""
    supabase = init_supabase()
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        
        # Populate session state
        st.session_state.authenticated = True
        st.session_state.user_id = response.user.id
        st.session_state.email = response.user.email
        
        # Extract metadata
        metadata = response.user.user_metadata or {}
        st.session_state.full_name = metadata.get("full_name", email.split("@")[0])
        st.session_state.role = metadata.get("role", "analyst")
        st.session_state.jwt_token = response.session.access_token
        
        return True, {"message": "Login successful"}
    except Exception as e:
        return False, {"message": str(e).split(":")[-1].strip()}

def auth_register(email: str, password: str, name: str, role: str) -> tuple[bool, dict]:
    """Registers a new user and appends custom metadata (name, role)."""
    supabase = init_supabase()
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "full_name": name,
                    "role": role
                }
            }
        })
        
        # If email confirmation is disabled in Supabase, a session is immediately returned.
        if response.session:
            st.session_state.authenticated = True
            st.session_state.user_id = response.user.id
            st.session_state.email = response.user.email
            st.session_state.full_name = name
            st.session_state.role = role
            st.session_state.jwt_token = response.session.access_token
            return True, {
                "message": "Registration successful! Logging you in...", 
                "auto_login": True
            }
        else:
            # Email confirmation is required
            return True, {
                "message": "Registration successful! Please check your email to confirm your account.", 
                "auto_login": False
            }
    except Exception as e:
        return False, {"message": str(e).split(":")[-1].strip()}

def auth_forgot_password(email: str) -> tuple[bool, str]:
    """Triggers a password reset email via Supabase."""
    supabase = init_supabase()
    try:
        supabase.auth.reset_password_email(email)
        return True, "If that email exists, a password reset link has been sent."
    except Exception as e:
        return False, str(e).split(":")[-1].strip()

def auth_google_login_url() -> str:
    """Generates the Google OAuth URL."""
    supabase = init_supabase()
    # Replace the redirect_to URL with your production Streamlit URL when deploying
    response = supabase.auth.get_authorization_url({
        "provider": "google",
        "options": {
            "redirect_to": "http://localhost:8501" 
        }
    })
    return response

def auth_handle_google_callback() -> bool:
    """
    Parses the URL query parameters for an OAuth code.
    Streamlit reloads the app with query params when Supabase redirects back.
    """
    if "code" in st.query_params:
        code = st.query_params["code"]
        supabase = init_supabase()
        try:
            # Exchange the OAuth code for a session
            response = supabase.auth.exchange_code_for_session({"auth_code": code})
            
            # Setup session state
            st.session_state.authenticated = True
            st.session_state.user_id = response.user.id
            st.session_state.email = response.user.email
            
            metadata = response.user.user_metadata or {}
            st.session_state.full_name = metadata.get("full_name", response.user.email)
            st.session_state.role = metadata.get("role", "analyst")
            st.session_state.jwt_token = response.session.access_token
            
            # Clean up the URL to prevent re-triggering on subsequent reloads
            st.query_params.clear()
            return True
        except Exception:
            return False
    return False
