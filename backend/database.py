# ================================================================
# backend/database.py  —  All Supabase Database Operations
# ================================================================

import os
import json
from datetime import datetime
import streamlit as st
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_ANON_KEY


@st.cache_resource
def get_db() -> Client:
    """Return cached Supabase client."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        st.error("❌ Supabase credentials missing — check .env file.")
        st.stop()
    try:
        return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    except Exception as e:
        st.error(f"❌ Supabase connection failed: {e}")
        st.stop()


# ── USERS ─────────────────────────────────────────────────────

def db_upsert_user(user_id, email, full_name="", role="analyst", avatar_url="", password_hash=None):
    db = get_db()
    payload = {
        "id": user_id,
        "email": email,
        "full_name": full_name,
        "role": role,
        "avatar_url": avatar_url,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if password_hash is not None:
        payload["password_hash"] = password_hash

    try:
        db.table("users").upsert(payload, on_conflict="id").execute()
        return True, None
    except Exception as e:
        return False, str(e)


def db_get_user(user_id):
    db = get_db()
    try:
        r = db.table("users").select("*").eq("id", user_id).single().execute()
        return r.data
    except: return None


def db_get_user_by_email(email):
    db = get_db()
    try:
        r = db.table("users").select("*").eq("email", email).single().execute()
        return r.data
    except: return None


def db_update_user_role(user_id, role):
    db = get_db()
    try:
        db.table("users").update({"role": role}).eq("id", user_id).execute()
    except Exception as e:
        print(f"[DB] update_role: {e}")

def db_get_all_users():
    db = get_db()
    try:
        r = db.table("users").select("*").order("created_at", desc=True).execute()
        return r.data or []
    except: return []


# ── PROJECTS ──────────────────────────────────────────────────

def db_create_project(user_id, name, description=""):
    db = get_db()
    try:
        r = db.table("projects").insert({
            "user_id": user_id, "name": name,
            "description": description
        }).execute()
        return r.data[0] if r.data else None
    except Exception as e:
        print(f"[DB] create_project: {e}")
        return None

def db_get_projects(user_id):
    db = get_db()
    try:
        r = (db.table("projects").select("*")
               .eq("user_id", user_id)
               .neq("status", "deleted")
               .order("created_at", desc=True).execute())
        return r.data or []
    except: return []

def db_get_project(project_id):
    db = get_db()
    try:
        r = db.table("projects").select("*").eq("id", project_id).single().execute()
        return r.data
    except: return None

def db_update_project(project_id, updates):
    db = get_db()
    try:
        db.table("projects").update(updates).eq("id", project_id).execute()
    except Exception as e:
        print(f"[DB] update_project: {e}")

def db_delete_project(project_id, user_id):
    db = get_db()
    try:
        db.table("projects").update({"status": "deleted"})\
            .eq("id", project_id).eq("user_id", user_id).execute()
        return True
    except: return False


# ── DATASETS ──────────────────────────────────────────────────

def db_save_dataset(project_id, user_id, filename, rows, cols,
                    columns_json, date_col, sales_col,
                    product_col, region_col, quality_score):
    db = get_db()
    try:
        r = db.table("datasets").insert({
            "project_id": project_id, "user_id": user_id,
            "filename": filename, "rows": rows, "cols": cols,
            "columns_json": columns_json,
            "date_col": date_col, "sales_col": sales_col,
            "product_col": product_col, "region_col": region_col,
            "quality_score": round(float(quality_score), 2)
        }).execute()
        return r.data[0] if r.data else None
    except Exception as e:
        print(f"[DB] save_dataset: {e}")
        return None

def db_get_dataset(project_id):
    db = get_db()
    try:
        r = (db.table("datasets").select("*")
               .eq("project_id", project_id)
               .order("created_at", desc=True).limit(1).execute())
        return r.data[0] if r.data else None
    except: return None


# ── FORECASTS ─────────────────────────────────────────────────

def db_save_forecast(project_id, user_id, model_name, horizon,
                     mae, rmse, r2, mape, forecast_json, is_best=False):
    db = get_db()
    try:
        # Clear old best if this is new best
        if is_best:
            db.table("forecasts").update({"is_best": False})\
                .eq("project_id", project_id).execute()
        r = db.table("forecasts").insert({
            "project_id": project_id, "user_id": user_id,
            "model_name": model_name, "horizon": horizon,
            "mae": round(float(mae), 4), "rmse": round(float(rmse), 4),
            "r2": round(float(r2), 4),   "mape": round(float(mape), 4),
            "is_best": is_best,
            "forecast_json": forecast_json
        }).execute()
        return r.data[0] if r.data else None
    except Exception as e:
        print(f"[DB] save_forecast: {e}")
        return None

def db_get_forecasts(project_id):
    db = get_db()
    try:
        r = (db.table("forecasts").select("*")
               .eq("project_id", project_id)
               .order("created_at", desc=True).execute())
        return r.data or []
    except: return []


# ── MODEL METRICS ─────────────────────────────────────────────

def db_save_metrics(project_id, user_id, model_name,
                    mae, rmse, r2, mape, train_rows, test_rows):
    db = get_db()
    try:
        db.table("model_metrics").insert({
            "project_id": project_id, "user_id": user_id,
            "model_name": model_name,
            "mae": round(float(mae), 4), "rmse": round(float(rmse), 4),
            "r2": round(float(r2), 4),   "mape": round(float(mape), 4),
            "train_rows": train_rows, "test_rows": test_rows
        }).execute()
    except Exception as e:
        print(f"[DB] save_metrics: {e}")

def db_get_metrics(project_id):
    db = get_db()
    try:
        r = (db.table("model_metrics").select("*")
               .eq("project_id", project_id)
               .order("created_at", desc=True).execute())
        return r.data or []
    except: return []


# ── REPORTS ───────────────────────────────────────────────────

def db_save_report(project_id, user_id, title, report_type, summary=""):
    db = get_db()
    try:
        db.table("reports").insert({
            "project_id": project_id, "user_id": user_id,
            "title": title, "report_type": report_type,
            "summary": summary[:2000]
        }).execute()
    except Exception as e:
        print(f"[DB] save_report: {e}")

def db_get_reports(project_id):
    db = get_db()
    try:
        r = (db.table("reports").select("*")
               .eq("project_id", project_id)
               .order("created_at", desc=True).execute())
        return r.data or []
    except: return []
