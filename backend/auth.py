# ================================================================
# backend/auth.py (Updated Google OAuth Functions)
# ================================================================

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

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

    # 💡 FIX: Inject the verifier into the URL as the 'state' parameter so it survives the hard redirect
    if verifier:
        parsed_url = urlparse(res.url)
        query_params = parse_qs(parsed_url.query)
        query_params['state'] = [verifier]
        new_query = urlencode(query_params, doseq=True)
        modified_url = urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            new_query,
            parsed_url.fragment
        ))
        return modified_url

    return res.url


def auth_handle_google_callback() -> bool:
    params = st.query_params

    # Supabase error handling
    error = params.get("error")
    if error:
        desc = params.get("error_description", error)
        st.error(f"Google sign-in failed: {desc}")
        st.query_params.clear()
        return False

    code = params.get("code")
    if not code:
        return False

    # 💡 FIX: Recover the verifier from the incoming URL 'state' query parameter
    verifier = params.get("state") or st.session_state.get("_oauth_code_verifier")

    # ── Show debug panel ─────────────────────────────────────────
    debug = st.session_state.get("_oauth_debug", {})

    with st.expander("🔍 OAuth Debug Info (share this with developer)", expanded=False):
        st.write(f"**?code present:** `{code[:12]}...`")
        st.write(f"**Verifier recovered:** `{verifier is not None}` → `{str(verifier)[:40] if verifier else 'None'}`")
        if debug:
            st.write("**Storage scan BEFORE oauth call:**")
            st.json(debug.get("pre", {}))
            st.write("**Storage scan AFTER oauth call:**")
            st.json(debug.get("post", {}))

    # ── Attempt exchange ─────────────────────────────────────────
    try:
        supabase = _get_supabase()

        # Restore verifier into all possible storage slots for the new client context instance
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

            # Also try setting directly on auth object attributes
            for attr in ["_code_verifier", "code_verifier"]:
                try:
                    setattr(supabase.auth, attr, verifier)
                except Exception:
                    pass

        # 💡 FIX: Pass the code verifier explicitly in the parameter payload dictionary
        res = supabase.auth.exchange_code_for_session({
            "auth_code": code,
            "code_verifier": verifier
        })

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
