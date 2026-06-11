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

    # ✅ KEY FIX: flow_type="implicit" tells supabase-py NOT to generate a
    # PKCE code verifier. Without this, the Python client defaults to PKCE,
    # which needs a browser-side verifier Python can never provide — causing
    # "both auth code and code verifier should be non-empty" error.
    # There is NO dashboard toggle; this must be set in the client options.
    try:
        from supabase.lib.client_options import ClientOptions
        return create_client(url, key, options=ClientOptions(flow_type="implicit"))
    except Exception:
        # Fallback for older supabase-py versions that don't support flow_type
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

    With flow_type="implicit" set on the client (in _get_supabase),
    Supabase returns #access_token=... in the URL fragment after Google
    auth — no code exchange needed, no PKCE verifier needed.

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

    return res.url


def auth_handle_google_callback() -> bool:
    """
    Handles the Google OAuth callback.

    With implicit flow, Supabase redirects back with the token in the
    URL *fragment* (#access_token=...). Browsers never send fragments to
    the server, so Streamlit's st.query_params can't see them directly.

    We use a small JS snippet (via st.markdown with an auto-executing
    script tag) to read the fragment and push it into the URL as a real
    query param (?access_token=...). On the next Streamlit rerender,
    Python picks it up from st.query_params and completes the login.
    """
    params = st.query_params

    # Step 1: Supabase error came back as query param
    error = params.get("error")
    if error:
        desc = params.get("error_description", error)
        st.error(f"Google sign-in failed: {desc}")
        st.query_params.clear()
        return False

    # Step 2: JS bridge already ran on a previous render — token is now a query param
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

    # Step 3: No token yet — inject JS to read #fragment and convert to ?query_param.
    # st.markdown executes script tags synchronously in the page context,
    # so window.location refers directly to the parent page (not an iframe).
    # This avoids st.components/st.iframe entirely.
    st.markdown(
        """
        <script>
        (function() {
            var hash = window.location.hash;
            if (!hash || hash.indexOf('access_token') === -1) return;
            var params = {};
            hash.substring(1).split('&').forEach(function(pair) {
                var kv = pair.split('=');
                if (kv.length === 2) {
                    params[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1]);
                }
            });
            var token = params['access_token'];
            if (token) {
                window.location.replace(
                    window.location.pathname + '?access_token=' + encodeURIComponent(token)
                );
            }
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )

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
