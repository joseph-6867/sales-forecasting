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
        "_oauth_code_verifier", "_oauth_debug",
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


def _debug_storage(supabase, label: str) -> dict:
    """
    Introspects every attribute of supabase.auth looking for the PKCE
    code verifier. Returns a dict of findings for display in the UI.
    """
    findings = {"label": label, "keys_found": [], "verifier": None}
    try:
        auth = supabase.auth

        # 1. Direct _storage attribute
        if hasattr(auth, "_storage"):
            storage = auth._storage
            findings["storage_type"] = type(storage).__name__

            # Try known keys
            for key in [
                "supabase.auth.code_verifier",
                "code_verifier",
                "pkce_code_verifier",
                "code-verifier",
            ]:
                try:
                    val = storage.get_item(key)
                    findings["keys_found"].append(f"get_item({key!r}) = {val!r}")
                    if val:
                        findings["verifier"] = val
                except Exception as ex:
                    findings["keys_found"].append(f"get_item({key!r}) ERROR: {ex}")

            # Dump internal dict if possible
            for attr in ["_storage", "_data", "store", "data", "__dict__"]:
                if hasattr(storage, attr):
                    try:
                        d = getattr(storage, attr)
                        if isinstance(d, dict):
                            findings[f"storage.{attr}"] = dict(d)
                    except Exception as ex:
                        findings[f"storage.{attr}_err"] = str(ex)

        # 2. Check auth.__dict__ for anything verifier-ish
        for k, v in vars(auth).items():
            if any(word in k.lower() for word in ["verif", "pkce", "code", "challenge"]):
                findings[f"auth.{k}"] = repr(v)[:200]

        # 3. Check auth._flow_type or similar
        for attr in ["_flow_type", "flow_type", "_pkce", "pkce"]:
            if hasattr(auth, attr):
                findings[f"auth.{attr}"] = repr(getattr(auth, attr))

    except Exception as ex:
        findings["error"] = str(ex)

    return findings


def auth_google_login_url() -> str:
    supabase = _get_supabase()
    site_url = _get_site_url()

    # DEBUG: snapshot storage BEFORE OAuth call
    pre = _debug_storage(supabase, "BEFORE sign_in_with_oauth")

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

    # DEBUG: snapshot storage AFTER OAuth call
    post = _debug_storage(supabase, "AFTER sign_in_with_oauth")

    # Try every possible location for the verifier
    verifier = None

    # From post-call storage scan
    if post.get("verifier"):
        verifier = post["verifier"]

    # From res object itself
    if not verifier and hasattr(res, "code_verifier"):
        verifier = res.code_verifier

    # From auth object attributes
    if not verifier:
        auth = supabase.auth
        for attr in ["_code_verifier", "code_verifier", "_pkce_code_verifier"]:
            val = getattr(auth, attr, None)
            if val:
                verifier = val
                break

    st.session_state["_oauth_code_verifier"] = verifier
    st.session_state["_oauth_debug"] = {"pre": pre, "post": post, "verifier_found": verifier is not None}

    return res.url


def auth_handle_google_callback() -> bool:
    params = st.query_params

    # Supabase error
    error = params.get("error")
    if error:
        desc = params.get("error_description", error)
        st.error(f"Google sign-in failed: {desc}")
        st.query_params.clear()
        return False

    code = params.get("code")
    if not code:
        return False

    # ── Show debug panel ─────────────────────────────────────────
    debug = st.session_state.get("_oauth_debug", {})
    verifier = st.session_state.get("_oauth_code_verifier")

    with st.expander("🔍 OAuth Debug Info (share this with developer)", expanded=True):
        st.write(f"**?code present:** `{code[:12]}...`")
        st.write(f"**Verifier in session_state:** `{verifier is not None}` → `{str(verifier)[:40] if verifier else 'None'}`")
        st.write(f"**Verifier found during URL generation:** `{debug.get('verifier_found')}`")
        if debug:
            st.write("**Storage scan BEFORE oauth call:**")
            st.json(debug.get("pre", {}))
            st.write("**Storage scan AFTER oauth call:**")
            st.json(debug.get("post", {}))

    # ── Attempt exchange ─────────────────────────────────────────
    try:
        supabase = _get_supabase()

        # Restore verifier into all possible storage slots
        if verifier:
            try:
                storage = supabase.auth._storage
                for key in ["supabase.auth.code_verifier", "code_verifier", "pkce_code_verifier"]:
                    try:
                        storage.set_item(key, verifier)
                    except Exception:
                        pass
                for attr in ["_storage", "_data", "store", "data"]:
                    d = getattr(storage, attr, None)
                    if isinstance(d, dict):
                        d["supabase.auth.code_verifier"] = verifier
                        d["code_verifier"] = verifier
            except Exception as ex:
                st.warning(f"⚠️ Could not restore verifier to storage: {ex}")

            # Also try setting directly on auth object
            for attr in ["_code_verifier", "code_verifier"]:
                try:
                    setattr(supabase.auth, attr, verifier)
                except Exception:
                    pass

        # Debug: snapshot storage just before exchange
        pre_exchange = _debug_storage(supabase, "BEFORE exchange_code_for_session")
        with st.expander("🔍 Storage BEFORE exchange", expanded=True):
            st.json(pre_exchange)

        res = supabase.auth.exchange_code_for_session({"auth_code": code})

        if res.user and res.session:
            _set_session_from_supabase(res.user, res.session)
            st.session_state.pop("_oauth_code_verifier", None)
            st.session_state.pop("_oauth_debug", None)
            st.query_params.clear()
            return True
        else:
            st.error("Exchange returned no user/session. Please try again.")
            st.query_params.clear()
            return False

    except Exception as e:
        st.error(f"**Exchange error:** `{e}`")
        st.write(f"**Full exception type:** `{type(e).__name__}`")
        import traceback
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
