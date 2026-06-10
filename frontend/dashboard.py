# ================================================================
# frontend/dashboard.py  —  Complete Post-Login Dashboard
# ================================================================
# Sidebar pages:
#   Dashboard · Projects · Upload Data · Analytics
#   Forecasting · Product Analysis · Region Analysis
#   AI Insights · Scenario Simulator · Reports · Settings
# ================================================================

import json
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

from backend.auth        import auth_logout, is_admin
from backend.database    import (db_create_project, db_get_projects, db_get_project,
                                  db_update_project, db_delete_project,
                                  db_save_dataset, db_get_dataset,
                                  db_save_forecast, db_get_forecasts,
                                  db_save_metrics, db_get_metrics,
                                  db_save_report, db_get_reports,
                                  db_get_all_users, db_update_user_role)
from services            import (validate_dataset, clean_dataset, engineer_features,
                                  compute_kpis, daily_trend, weekly_trend,
                                  monthly_trend, yearly_trend, seasonal_analysis,
                                  product_analysis, region_analysis,
                                  generate_insights, generate_recommendations,
                                  run_scenario)
from models              import (train_all_models, select_best_model,
                                  generate_forecast, get_feature_importance,
                                  save_model_bytes)
from frontend.charts     import (line_chart, bar_chart, multi_line, grouped_bar_pivot,
                                  pie_chart, area_chart, scatter_plot, heatmap,
                                  forecast_chart, model_comparison_chart, gauge_chart)
from reports             import generate_pdf_report, generate_excel_report
from utils               import (read_uploaded_file, to_csv_bytes, to_excel_bytes,
                                  detect_column, num_cols, fmt_currency,
                                  fmt_num, fmt_pct, delta_str, now_str)
from utils.demo_data     import get_demo_df
from config.settings     import FORECAST_HORIZONS, COLOR, PALETTE


# ================================================================
# ENTRY POINT
# ================================================================

def render_dashboard():
    """Main dispatcher — called from app.py when authenticated."""
    _sidebar()


def _sidebar():
    """Sidebar navigation + page routing."""
    uid   = st.session_state.user_id
    name  = st.session_state.full_name or "User"
    role  = st.session_state.role or "analyst"
    proj  = st.session_state.active_project
    is_demo = st.session_state.get("demo_mode", False)

    with st.sidebar:
        st.markdown("## 📊 Sales Platform")
        st.markdown(f"**{name}**")
        st.caption(f"Role: `{role.title()}` · {st.session_state.email}")
        st.divider()

        pages = [
            ("🏠", "Dashboard",          "home"),
            ("📁", "Projects",           "projects"),
            ("📤", "Upload Data",        "upload"),
            ("📈", "Analytics",          "analytics"),
            ("🔮", "Forecasting",        "forecasting"),
            ("📦", "Product Analysis",   "products"),
            ("🗺️", "Region Analysis",    "regions"),
            ("🧠", "AI Insights",        "insights"),
            ("🎮", "Scenario Simulator", "scenario"),
            ("📋", "Reports",            "reports"),
            ("⚙️", "Settings",           "settings"),
        ]

        # Filter out Projects and Upload for demo users
        if is_demo:
            pages = [p for p in pages if p[2] not in ["projects", "upload"]]

        for icon, label, key in pages:
            active = st.session_state.current_page == key
            btn_label = f"{icon} {label}" + (" ◀" if active else "")
            if st.button(btn_label, key=f"nav_{key}", use_container_width=True):
                st.session_state.current_page = key
                st.rerun()

        st.divider()
        if proj:
            st.success(f"📁 **{proj['name'][:20]}**")
            df = st.session_state.active_df
            if df is not None:
                st.caption(f"{len(df):,} rows · {len(df.columns)} cols")
        elif st.session_state.demo_mode:
            st.info("🎮 Demo Mode Active")

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            auth_logout()
            st.rerun()

    # Route to the correct page
    page = st.session_state.current_page
    if   page == "home":        _page_home()
    elif page == "projects":    _page_projects()
    elif page == "upload":      _page_upload()
    elif page == "analytics":   _page_analytics()
    elif page == "forecasting": _page_forecasting()
    elif page == "products":    _page_products()
    elif page == "regions":     _page_regions()
    elif page == "insights":    _page_insights()
    elif page == "scenario":    _page_scenario()
    elif page == "reports":     _page_reports()
    elif page == "settings":    _page_settings()
    else:                       _page_home()


# ================================================================
# PAGE: WELCOME DASHBOARD
# ================================================================

def _page_home():
    uid  = st.session_state.user_id
    name = st.session_state.full_name or "User"
    is_demo = st.session_state.get("demo_mode", False)

    # Auto-load demo dataset on first visit for demo users
    if is_demo and st.session_state.get("active_df") is None:
        _load_demo()
        st.rerun()

    st.title(f"👋 Welcome back, {name}!")
    st.markdown("Your intelligent sales forecasting and business analytics workspace.")
    st.divider()

    # ── Quick Action Buttons ──────────────────────────────
    cols = []
    if not is_demo:
        c1, c2, c3, c4 = st.columns(4)
        cols = [c1, c2, c3, c4]
        with c1:
            if st.button("🎮 Explore Demo Dataset", use_container_width=True, type="primary"):
                _load_demo()
                st.session_state.current_page = "analytics"
                st.rerun()
        with c2:
            if st.button("📤 Upload Your Dataset", use_container_width=True):
                st.session_state.current_page = "upload"
                st.rerun()
        with c3:
            if st.button("📁 New Project", use_container_width=True):
                st.session_state.current_page = "projects"
                st.rerun()
        with c4:
            if st.button("🔮 Go to Forecasting", use_container_width=True):
                st.session_state.current_page = "forecasting"
                st.rerun()
    else:
        # Demo mode: show only feature exploration buttons
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("📈 View Analytics", use_container_width=True, type="primary"):
                st.session_state.current_page = "analytics"
                st.rerun()
        with c2:
            if st.button("🔮 Forecasting", use_container_width=True):
                st.session_state.current_page = "forecasting"
                st.rerun()
        with c3:
            if st.button("📋 Generate Reports", use_container_width=True):
                st.session_state.current_page = "reports"
                st.rerun()
        st.info("🎮 **Demo Mode**: Explore all features using the built-in dataset. No file uploads or project management in demo mode.")

    st.divider()

    # ── Feature showcase ──────────────────────────────────
    st.subheader("✨ Platform Features")
    f1,f2,f3 = st.columns(3)
    with f1:
        st.info("**📤 Data Upload**\n\nCSV & Excel. Auto-detects sales, date, product, region columns.")
        st.info("**📈 Trend Analysis**\n\nDaily, weekly, monthly, yearly views with rolling averages.")
        st.info("**🌟 Seasonal Analysis**\n\nBest/worst months, quarterly breakdown, day-of-week patterns.")
    with f2:
        st.info("**🔮 ML Forecasting**\n\nLinear Regression, Random Forest, Gradient Boosting — auto-selects best model.")
        st.info("**📦 Product Analytics**\n\nTop products, revenue share, product trend lines.")
        st.info("**🗺️ Region Analytics**\n\nRegional breakdown, comparison charts, region-level forecast.")
    with f3:
        st.info("**🧠 AI Insights**\n\nAuto-generated growth trends, peak periods, revenue patterns.")
        st.info("**🎮 Scenario Simulator**\n\nTest growth, demand, and discount scenarios against forecast.")
        st.info("**📋 Reports**\n\nDownload PDF, Excel, and CSV reports of all analyses.")

    st.divider()

    # ── Recent Projects ───────────────────────────────────
    st.subheader("📁 Recent Projects")
    projects = db_get_projects(uid)

    if not projects:
        st.info("No projects yet. Click **New Project** or **Explore Demo Dataset** to get started.")
    else:
        for p in projects[:4]:
            with st.container():
                pc1, pc2, pc3 = st.columns([4,2,2])
                with pc1:
                    st.markdown(f"**{p['name']}**  \n{p.get('description','')[:60]}")
                with pc2:
                    st.caption(f"Rows: {p.get('dataset_rows',0):,}  ·  {p['created_at'][:10]}")
                with pc3:
                    if st.button("Open", key=f"open_{p['id']}"):
                        _open_project(p['id'])
                st.divider()

    # ── Platform stats ────────────────────────────────────
    st.subheader("📊 Your Statistics")
    s1,s2,s3,s4 = st.columns(4)
    s1.metric("Projects",   len(projects))
    forecasts = db_get_forecasts(projects[0]['id']) if projects else []
    s2.metric("Forecasts Run", len(forecasts))
    reports   = db_get_reports(projects[0]['id']) if projects else []
    s3.metric("Reports Generated", len(reports))
    s4.metric("Role", (st.session_state.role or "analyst").title())


def _load_demo():
    """Load the built-in demo dataset into session state."""
    df = get_demo_df()
    st.session_state.active_df   = df
    st.session_state.demo_mode   = True
    st.session_state.col_map = {
        "date":    "date",
        "sales":   "sales",
        "product": "product",
        "region":  "region",
    }
    # Create/use a demo project
    uid = st.session_state.user_id
    projects = db_get_projects(uid)
    demo_proj = next((p for p in projects if p["name"] == "Demo Project"), None)
    if not demo_proj:
        demo_proj = db_create_project(uid, "Demo Project",
                                       "Auto-created demo project with synthetic sales data.")
    if demo_proj:
        st.session_state.active_project = demo_proj
        db_update_project(demo_proj["id"], {
            "dataset_rows": len(df),
            "dataset_cols": len(df.columns),
            "date_range":   f"{df['date'].min().date()} → {df['date'].max().date()}"
        })
    st.success("🎮 Demo dataset loaded! Exploring 2 years of synthetic sales data.")


def _open_project(project_id):
    proj = db_get_project(project_id)
    if proj:
        st.session_state.active_project = proj
        st.session_state.current_page   = "analytics"


# ================================================================
# PAGE: PROJECTS
# ================================================================

def _page_projects():
    uid = st.session_state.user_id
    is_demo = st.session_state.get("demo_mode", False)

    if is_demo:
        st.warning("🎮 Project management is not available in Demo Mode. Explore all features with the demo dataset!")
        if st.button("← Back to Dashboard"):
            st.session_state.current_page = "home"
            st.rerun()
        return

    st.title("📁 Project Workspace")

    # ── Create new project ────────────────────────────────
    with st.expander("➕ Create New Project", expanded=False):
        with st.form("new_project"):
            pname = st.text_input("Project Name *", placeholder="Q4 Sales Analysis")
            pdesc = st.text_area("Description", placeholder="Brief description…", height=80)
            if st.form_submit_button("Create Project", type="primary"):
                if not pname.strip():
                    st.error("Project name is required.")
                else:
                    proj = db_create_project(uid, pname.strip(), pdesc.strip())
                    if proj:
                        st.success(f"✅ Project '{pname}' created!")
                        st.session_state.active_project = proj
                        st.rerun()
                    else:
                        st.error("Failed to create project.")

    st.divider()

    # ── List projects ─────────────────────────────────────
    projects = db_get_projects(uid)
    if not projects:
        st.info("No projects yet — create one above or explore the demo.")
        return

    st.subheader(f"Your Projects ({len(projects)})")
    for p in projects:
        with st.container():
            r1, r2, r3, r4 = st.columns([4, 2, 1, 1])
            with r1:
                active = (st.session_state.active_project or {}).get("id") == p["id"]
                label  = f"{'✅ ' if active else ''}**{p['name']}**"
                st.markdown(f"{label}  \n{p.get('description','')[:80]}")
            with r2:
                st.caption(f"{p.get('dataset_rows',0):,} rows · {p['created_at'][:10]}")
            with r3:
                if st.button("Open", key=f"proj_open_{p['id']}", use_container_width=True):
                    _open_project(p["id"])
                    st.rerun()
            with r4:
                if st.button("🗑️", key=f"proj_del_{p['id']}", help="Delete project"):
                    db_delete_project(p["id"], uid)
                    if (st.session_state.active_project or {}).get("id") == p["id"]:
                        st.session_state.active_project = None
                        st.session_state.active_df      = None
                    st.rerun()
            st.divider()


# ================================================================
# PAGE: UPLOAD DATA
# ================================================================

def _page_upload():
    uid  = st.session_state.user_id
    is_demo = st.session_state.get("demo_mode", False)
    proj = st.session_state.active_project

    if is_demo:
        st.warning("🎮 File upload is not available in Demo Mode. Explore all features with the demo dataset!")
        if st.button("← Back to Dashboard"):
            st.session_state.current_page = "home"
            st.rerun()
        return

    st.title("📤 Upload Dataset")

    if not proj:
        st.warning("⚠️ Please create or open a project first.")
        if st.button("Go to Projects"):
            st.session_state.current_page = "projects"
            st.rerun()
        return

    st.info(f"Active project: **{proj['name']}**")

    # ── File uploader ─────────────────────────────────────
    uploaded = st.file_uploader(
        "Drag & drop or browse — CSV or Excel",
        type=["csv","xlsx","xls"],
        help="Max 200MB. Columns are auto-normalised to lowercase."
    )

    if uploaded:
        with st.spinner("Reading file…"):
            df, err = read_uploaded_file(uploaded)
        if err:
            st.error(f"❌ {err}"); return

        st.success(f"✅ Loaded **{uploaded.name}** — {len(df):,} rows × {len(df.columns)} columns")
        st.session_state.demo_mode = False

        # ── Column mapping ────────────────────────────────
        st.subheader("🗂️ Column Mapping")
        st.caption("Auto-detected columns are pre-selected. Adjust if needed.")

        auto_date    = detect_column(df, "date")
        auto_sales   = detect_column(df, "sales")
        auto_product = detect_column(df, "product")
        auto_region  = detect_column(df, "region")
        all_cols     = ["(none)"] + list(df.columns)

        mc1, mc2, mc3, mc4 = st.columns(4)
        date_col    = mc1.selectbox("📅 Date Column *",    all_cols, index=all_cols.index(auto_date)    if auto_date    in all_cols else 0)
        sales_col   = mc2.selectbox("💰 Sales Column *",   all_cols, index=all_cols.index(auto_sales)   if auto_sales   in all_cols else 0)
        product_col = mc3.selectbox("📦 Product Column",   all_cols, index=all_cols.index(auto_product) if auto_product in all_cols else 0)
        region_col  = mc4.selectbox("🗺️ Region Column",    all_cols, index=all_cols.index(auto_region)  if auto_region  in all_cols else 0)

        if date_col == "(none)" or sales_col == "(none)":
            st.warning("Date and Sales columns are required for full analysis.")

        # ── Validation ────────────────────────────────────
        st.subheader("🔍 Data Validation")
        with st.spinner("Validating…"):
            val = validate_dataset(
                df,
                date_col  if date_col  != "(none)" else None,
                sales_col if sales_col != "(none)" else None
            )

        score = val["score"]
        score_col = "success" if score >= 80 else "warning" if score >= 60 else "error"
        getattr(st, score_col)(f"Data Quality Score: **{score}/100**")

        v1,v2,v3,v4 = st.columns(4)
        v1.metric("Missing Values", f"{val['missing_total']:,}")
        v2.metric("Duplicates",     f"{val['duplicates']:,}")
        v3.metric("Outlier Cols",   len(val["outliers"]))
        v4.metric("Total Rows",     f"{val['n_rows']:,}")

        if val["issues"]:
            with st.expander("❌ Issues"):
                for i in val["issues"]: st.error(f"• {i}")
        if val["warnings"]:
            with st.expander("⚠️ Warnings"):
                for w in val["warnings"]: st.warning(f"• {w}")

        # ── Auto-clean option ─────────────────────────────
        if val["missing_total"] > 0 or val["duplicates"] > 0:
            if st.checkbox("🧹 Auto-clean dataset (fill missing, remove duplicates)"):
                with st.spinner("Cleaning…"):
                    df, changes = clean_dataset(
                        df,
                        date_col  if date_col  != "(none)" else None,
                        sales_col if sales_col != "(none)" else None
                    )
                if changes:
                    st.success("✅ Cleaning applied:")
                    for c in changes: st.markdown(f"  - {c}")

        # ── Preview ───────────────────────────────────────
        st.subheader("👁️ Dataset Preview")
        st.dataframe(df.head(50), use_container_width=True)

        # ── Confirm & Save ────────────────────────────────
        st.divider()
        if st.button("✅ Confirm & Start Analysis", type="primary", use_container_width=True):
            col_map = {
                "date":    date_col    if date_col    != "(none)" else None,
                "sales":   sales_col   if sales_col   != "(none)" else None,
                "product": product_col if product_col != "(none)" else None,
                "region":  region_col  if region_col  != "(none)" else None,
            }
            st.session_state.active_df  = df
            st.session_state.col_map    = col_map

            # Save metadata to Supabase
            db_save_dataset(
                proj["id"], uid, uploaded.name,
                len(df), len(df.columns),
                json.dumps(list(df.columns)),
                col_map["date"]    or "",
                col_map["sales"]   or "",
                col_map["product"] or "",
                col_map["region"]  or "",
                val["score"]
            )
            db_update_project(proj["id"], {
                "dataset_rows": len(df),
                "dataset_cols": len(df.columns),
            })
            st.success("✅ Dataset saved! Redirecting to Analytics…")
            st.session_state.current_page = "analytics"
            st.rerun()


# ================================================================
# PAGE: ANALYTICS
# ================================================================

def _page_analytics():
    st.title("📈 Sales Analytics")
    df, col_map = _get_df_or_warn()
    if df is None: return

    date_col  = col_map.get("date")
    sales_col = col_map.get("sales")

    if not date_col or not sales_col:
        st.error("Date and Sales columns are required. Go to Upload Data to re-configure.")
        return

    # ── KPI Cards ─────────────────────────────────────────
    with st.spinner("Computing KPIs…"):
        kpis = compute_kpis(df, date_col, sales_col)

    st.subheader("📊 Key Performance Indicators")
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    k1.metric("Total Sales",     fmt_currency(kpis["total_sales"]))
    k2.metric("Avg per Record",  fmt_currency(kpis["avg_sales"]))
    k3.metric("Peak Transaction",fmt_currency(kpis["max_sales"]))
    k4.metric("Transactions",    f"{kpis['transactions']:,}")
    k5.metric("30-Day Growth",   f"{kpis['growth_pct']:+.1f}%",
              delta=f"{kpis['growth_pct']:+.1f}%",
              delta_color="normal" if kpis["growth_pct"] >= 0 else "inverse")
    k6.metric("Date Range",      kpis["date_range"].split("→")[0].strip())

    st.divider()

    # ── Trend tabs ────────────────────────────────────────
    t1,t2,t3,t4 = st.tabs(["Daily","Weekly","Monthly","Yearly"])

    with t1:
        daily = daily_trend(df, date_col, sales_col)
        st.plotly_chart(
            line_chart(daily, "date", "sales", "Daily Sales Trend", show_rolling=True),
            use_container_width=True
        )
        st.download_button("⬇️ CSV", to_csv_bytes(daily), "daily_sales.csv", "text/csv")

    with t2:
        weekly = weekly_trend(df, date_col, sales_col)
        st.plotly_chart(
            bar_chart(weekly, "week", "sales", "Weekly Sales"),
            use_container_width=True
        )

    with t3:
        monthly = monthly_trend(df, date_col, sales_col)
        st.plotly_chart(
            area_chart(monthly, "month", "sales", "Monthly Sales"),
            use_container_width=True
        )
        st.dataframe(monthly, use_container_width=True)
        st.download_button("⬇️ CSV", to_csv_bytes(monthly), "monthly_sales.csv", "text/csv")

    with t4:
        yearly = yearly_trend(df, date_col, sales_col)
        st.plotly_chart(
            bar_chart(yearly, "year", "sales", "Yearly Sales"),
            use_container_width=True
        )

    st.divider()

    # ── Seasonal ──────────────────────────────────────────
    st.subheader("🌟 Seasonal Analysis")
    sea = seasonal_analysis(df, date_col, sales_col)

    sc1, sc2 = st.columns(2)
    sc1.success(f"🏆 Best Month: **{sea['best_month']}**")
    sc2.warning(f"⚠️ Worst Month: **{sea['worst_month']}**")

    ss1, ss2, ss3 = st.columns(3)
    with ss1:
        st.plotly_chart(
            bar_chart(sea["by_month"], "month", "avg_sales", "Avg Sales by Month", PALETTE[0]),
            use_container_width=True
        )
    with ss2:
        by_q = sea["by_quarter"]
        st.plotly_chart(
            pie_chart(list(by_q["quarter_label"]), list(by_q["sales"]), "Sales by Quarter"),
            use_container_width=True
        )
    with ss3:
        st.plotly_chart(
            bar_chart(sea["by_dow"], "day", "avg_sales", "Avg Sales by Day"),
            use_container_width=True
        )

    # Store for other pages
    st.session_state["_kpis"]     = kpis
    st.session_state["_seasonal"] = sea
    st.session_state["_monthly"]  = monthly
    st.session_state["_daily"]    = daily


# ================================================================
# PAGE: FORECASTING
# ================================================================

def _page_forecasting():
    st.title("🔮 ML Sales Forecasting")
    df, col_map = _get_df_or_warn()
    if df is None: return

    date_col  = col_map.get("date")
    sales_col = col_map.get("sales")
    if not date_col or not sales_col:
        st.error("Date and Sales columns are required."); return

    uid  = st.session_state.user_id
    proj = st.session_state.active_project or {}

    # ── Train models ──────────────────────────────────────
    st.subheader("🤖 Train All Models")
    st.info(
        "Trains **Linear Regression**, **Random Forest**, and **Gradient Boosting** "
        "on your daily aggregated sales data, then auto-selects the best model."
    )

    if st.button("▶️ Train Models", type="primary"):
        with st.spinner("Engineering features & training models…"):
            try:
                daily = engineer_features(df, date_col, sales_col)
                results, feat_cols = train_all_models(daily, date_col)
                best_name = select_best_model(results)

                st.session_state.trained_models    = results
                st.session_state["_best_model"]    = best_name
                st.session_state["_daily_eng"]     = daily
                st.session_state["_feat_cols"]     = feat_cols

                # Save to Supabase
                for mname, res in results.items():
                    m = res["metrics"]
                    db_save_metrics(
                        proj.get("id",""), uid, mname,
                        m["mae"], m["rmse"], m["r2"], m["mape"],
                        res["split_idx"], len(daily) - res["split_idx"]
                    )
                st.success(f"✅ All models trained! Best model: **{best_name}**")
            except Exception as e:
                st.error(f"Training failed: {e}")
                return

    results    = st.session_state.get("trained_models", {})
    best_name  = st.session_state.get("_best_model")

    if not results:
        st.info("Click **Train Models** to begin.")
        return

    # ── Model comparison ──────────────────────────────────
    st.subheader("📊 Model Performance Comparison")
    metrics_list = [
        {"model_name": n, **r["metrics"]} for n, r in results.items()
    ]

    cm1, cm2 = st.columns(2)
    with cm1:
        metric_sel = st.selectbox("Compare by", ["rmse","mae","r2","mape"], key="cmp_metric")
        st.plotly_chart(
            model_comparison_chart(metrics_list, metric_sel),
            use_container_width=True
        )
    with cm2:
        st.dataframe(
            pd.DataFrame(metrics_list).round(4),
            use_container_width=True
        )

    # ── Model details ─────────────────────────────────────
    for mname, res in results.items():
        is_best = (mname == best_name)
        label   = f"{'🏆 Best — ' if is_best else ''}{mname}"
        with st.expander(label, expanded=is_best):
            m = res["metrics"]
            mc1,mc2,mc3,mc4 = st.columns(4)
            mc1.metric("MAE",  f"{m['mae']:.2f}")
            mc2.metric("RMSE", f"{m['rmse']:.2f}")
            mc3.metric("R²",   f"{m['r2']:.4f}")
            mc4.metric("MAPE", f"{m['mape']:.2f}%")

            fi = get_feature_importance(res, res["feature_cols"])
            if fi is not None:
                st.plotly_chart(
                    bar_chart(fi.head(10), "feature", "importance",
                              f"{mname} — Feature Importance", horizontal=True),
                    use_container_width=True
                )
            st.download_button(
                f"⬇️ Download {mname} Model",
                data=save_model_bytes(res),
                file_name=f"{mname.replace(' ','_').lower()}.pkl",
                mime="application/octet-stream",
                key=f"dl_{mname}"
            )

    st.divider()

    # ── Generate forecast ─────────────────────────────────
    st.subheader("📅 Generate Forecast")
    fc1, fc2 = st.columns([2,1])
    with fc1:
        horizon_name = st.selectbox(
            "Forecast Horizon",
            list(FORECAST_HORIZONS.keys()),
            key="horizon_sel"
        )
    with fc2:
        model_sel = st.selectbox(
            "Use Model",
            list(results.keys()),
            index=list(results.keys()).index(best_name) if best_name in results else 0,
            key="model_sel"
        )

    if st.button("🔮 Generate Forecast", type="primary"):
        horizon_days = FORECAST_HORIZONS[horizon_name]
        with st.spinner(f"Forecasting {horizon_days} days…"):
            try:
                daily_eng = st.session_state.get("_daily_eng")
                if daily_eng is None:
                    daily_eng = engineer_features(df, date_col, sales_col)

                fc_df = generate_forecast(daily_eng, date_col, results[model_sel], horizon_days)

                forecast_results = st.session_state.get("forecast_results")
                if forecast_results is None:
                    forecast_results = {}
                    st.session_state.forecast_results = forecast_results
                forecast_results[horizon_name] = fc_df

                # Historical for chart
                hist_daily = daily_eng[[date_col, "daily_sales"]].tail(90).copy()
                hist_daily.columns = ["date","sales"]

                st.success(f"✅ Forecast ready: {len(fc_df)} days")
                st.plotly_chart(
                    forecast_chart(hist_daily, fc_df,
                                   f"{model_sel} — {horizon_name}"),
                    use_container_width=True
                )

                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Forecast Table")
                    st.dataframe(fc_df, use_container_width=True)
                with col2:
                    st.subheader("Summary")
                    st.metric("Total Forecast Sales", fmt_currency(fc_df["forecast"].sum()))
                    st.metric("Avg Daily Forecast",   fmt_currency(fc_df["forecast"].mean()))
                    st.metric("Peak Day",             fmt_currency(fc_df["forecast"].max()))

                st.download_button("⬇️ Download Forecast CSV",
                                    to_csv_bytes(fc_df),
                                    f"forecast_{horizon_name.replace(' ','_')}.csv",
                                    "text/csv")

                # Save forecast to DB
                db_save_forecast(
                    proj.get("id",""), uid, model_sel, horizon_name,
                    results[model_sel]["metrics"]["mae"],
                    results[model_sel]["metrics"]["rmse"],
                    results[model_sel]["metrics"]["r2"],
                    results[model_sel]["metrics"]["mape"],
                    fc_df.to_json(orient="records"),
                    is_best=(model_sel == best_name)
                )
            except Exception as e:
                st.error(f"Forecast failed: {e}")


# ================================================================
# PAGE: PRODUCT ANALYSIS
# ================================================================

def _page_products():
    st.title("📦 Product Analysis")
    df, col_map = _get_df_or_warn()
    if df is None: return

    date_col    = col_map.get("date")
    sales_col   = col_map.get("sales")
    product_col = col_map.get("product")

    if not product_col:
        st.warning("No product column mapped. Go to Upload Data to set it.")
        return

    res = product_analysis(df, date_col or "date", sales_col, product_col)
    by_prod = res["by_product"]

    # ── Top-level KPIs ────────────────────────────────────
    p1,p2,p3 = st.columns(3)
    p1.metric("Total Products",  len(by_prod))
    p2.metric("Top Product",     str(by_prod.iloc[0][product_col]) if not by_prod.empty else "N/A")
    top_share = float(by_prod["share_pct"].iloc[0]) if not by_prod.empty else 0
    p3.metric("Top Product Share", fmt_pct(top_share))

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            bar_chart(by_prod.head(10), product_col, "total",
                      "Top 10 Products by Revenue", horizontal=True),
            use_container_width=True
        )
    with c2:
        st.plotly_chart(
            pie_chart(list(by_prod[product_col].head(8)),
                      list(by_prod["total"].head(8)),
                      "Revenue Share by Product"),
            use_container_width=True
        )

    # ── Product trend ─────────────────────────────────────
    if not res["prod_trend"].empty:
        st.subheader("📈 Top 5 Products — Monthly Trend")
        st.plotly_chart(
            grouped_bar_pivot(res["prod_trend"], "month", "product", "sales",
                              "Monthly Sales by Product"),
            use_container_width=True
        )

    # ── Full table ────────────────────────────────────────
    st.subheader("📋 Product Performance Table")
    st.dataframe(by_prod, use_container_width=True)
    st.download_button("⬇️ Download CSV", to_csv_bytes(by_prod),
                        "product_analysis.csv","text/csv")


# ================================================================
# PAGE: REGION ANALYSIS
# ================================================================

def _page_regions():
    st.title("🗺️ Region Analysis")
    df, col_map = _get_df_or_warn()
    if df is None: return

    date_col   = col_map.get("date")
    sales_col  = col_map.get("sales")
    region_col = col_map.get("region")

    if not region_col:
        st.warning("No region column mapped. Go to Upload Data to set it.")
        return

    res       = region_analysis(df, date_col or "date", sales_col, region_col)
    by_region = res["by_region"]

    region_options = ["All Regions"] + list(by_region[region_col].astype(str))
    selected_region = st.selectbox("Select region for analysis", region_options)

    if selected_region != "All Regions":
        filtered_df = df[df[region_col].astype(str) == selected_region]
        res = region_analysis(filtered_df, date_col or "date", sales_col, region_col)
        by_region = res["by_region"]

    r1,r2,r3 = st.columns(3)
    r1.metric("Regions",     len(by_region))
    r2.metric("Top Region",  str(by_region.iloc[0][region_col]) if not by_region.empty else "N/A")
    top_share = float(by_region["share_pct"].iloc[0]) if not by_region.empty else 0
    r3.metric("Top Region Share", fmt_pct(top_share))

    st.info("Select a region from the list above to refresh the regional summary.")
    st.divider()
    rc1, rc2 = st.columns(2)
    with rc1:
        st.plotly_chart(
            bar_chart(by_region, region_col, "total", "Revenue by Region", horizontal=True),
            use_container_width=True
        )
    with rc2:
        st.plotly_chart(
            pie_chart(list(by_region[region_col]), list(by_region["total"]),
                      "Region Revenue Share"),
            use_container_width=True
        )

    st.dataframe(by_region, use_container_width=True)
    st.download_button("⬇️ Download CSV", to_csv_bytes(by_region),
                        "region_analysis.csv","text/csv")


# ================================================================
# PAGE: AI INSIGHTS
# ================================================================

def _page_insights():
    st.title("🧠 AI Insights & Recommendations")
    df, col_map = _get_df_or_warn()
    if df is None: return

    date_col    = col_map.get("date")
    sales_col   = col_map.get("sales")
    product_col = col_map.get("product")
    region_col  = col_map.get("region")

    kpis = st.session_state.get("_kpis")
    if not kpis:
        with st.spinner("Computing analytics…"):
            kpis = compute_kpis(df, date_col, sales_col)
        st.session_state["_kpis"] = kpis

    seasonal = st.session_state.get("_seasonal")
    if not seasonal:
        seasonal = seasonal_analysis(df, date_col, sales_col)
        st.session_state["_seasonal"] = seasonal

    product_res = None
    if product_col:
        product_res = product_analysis(df, date_col, sales_col, product_col)

    region_res = None
    if region_col:
        region_res = region_analysis(df, date_col, sales_col, region_col)

    # ── Insights ──────────────────────────────────────────
    st.subheader("💡 Business Insights")
    insights = generate_insights(df, date_col, sales_col, kpis, seasonal)
    for ins in insights:
        st.markdown(f"- {ins}")

    st.divider()

    # ── Recommendations ───────────────────────────────────
    st.subheader("🎯 AI Recommendations")
    recs = generate_recommendations(kpis, seasonal, product_res, region_res)
    for rec in recs:
        st.info(rec)

    # ── Correlation heatmap ───────────────────────────────
    nc = num_cols(df)
    if len(nc) >= 3:
        st.divider()
        st.subheader("🔥 Correlation Heatmap")
        corr = df[nc[:8]].corr()
        st.plotly_chart(heatmap(corr, "Feature Correlations"), use_container_width=True)


# ================================================================
# PAGE: SCENARIO SIMULATOR
# ================================================================

def _page_scenario():
    st.title("🎮 Scenario Simulator")
    st.info(
        "Adjust business levers below to simulate how they affect "
        "your sales forecast. Requires a forecast to be generated first."
    )

    # Check if any forecast is available
    forecast_results = st.session_state.get("forecast_results", {})
    if not forecast_results:
        st.warning("No forecast available. Run the Forecasting module first.")
        if st.button("Go to Forecasting"):
            st.session_state.current_page = "forecasting"
            st.rerun()
        return

    horizon = st.selectbox("Select Forecast", list(forecast_results.keys()), key="scen_horizon")
    baseline = forecast_results[horizon]

    st.subheader("⚙️ Adjust Scenario Parameters")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        growth_pct   = st.slider("📈 Sales Growth Change (%)", -30, 50, 0, key="scen_growth",
                                  help="Simulate a growth or decline in sales rate")
    with sc2:
        demand_change = st.slider("📦 Demand Change (%)",      -20, 40, 0, key="scen_demand",
                                  help="Increase or decrease customer demand")
    with sc3:
        discount_pct  = st.slider("🏷️ Discount Applied (%)",    0,  30, 0, key="scen_discount",
                                  help="Simulate offering discounts to customers")

    scenario_df = run_scenario(baseline, growth_pct, demand_change, discount_pct)

    st.divider()
    st.subheader("📊 Scenario Results")

    base_total  = float(baseline["forecast"].sum())
    scen_total  = float(scenario_df["scenario_sales"].sum())
    diff_total  = scen_total - base_total

    m1, m2, m3 = st.columns(3)
    m1.metric("Baseline Forecast",  fmt_currency(base_total))
    m2.metric("Scenario Forecast",  fmt_currency(scen_total),
              delta=f"{fmt_currency(diff_total)} ({diff_total/max(base_total,1)*100:+.1f}%)",
              delta_color="normal" if diff_total >= 0 else "inverse")
    m3.metric("Net Impact",         fmt_currency(diff_total))

    # Combined chart
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=scenario_df["date"], y=scenario_df["forecast"],
                              name="Baseline", mode="lines",
                              line=dict(color="#6366F1", width=2, dash="dash")))
    fig.add_trace(go.Scatter(x=scenario_df["date"], y=scenario_df["scenario_sales"],
                              name="Scenario", mode="lines",
                              line=dict(color="#10B981", width=2.5),
                              fill="tonexty", fillcolor="rgba(16,185,129,0.1)"))
    fig.update_layout(
        title="Baseline vs Scenario Forecast",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#F1F5F9"), height=380,
        legend=dict(orientation="h", x=0, y=1.1)
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(scenario_df, use_container_width=True)
    st.download_button("⬇️ Download Scenario CSV",
                        to_csv_bytes(scenario_df), "scenario.csv", "text/csv")


# ================================================================
# PAGE: REPORTS
# ================================================================

def _page_reports():
    st.title("📋 Reports")
    uid  = st.session_state.user_id
    proj = st.session_state.active_project or {}
    df, col_map = _get_df_or_warn(silent=True)

    tab1, tab2 = st.tabs(["📥 Generate Reports", "📄 Report History"])

    with tab1:
        if df is None:
            st.info("Load a dataset to generate reports.")
            return

        date_col  = col_map.get("date")
        sales_col = col_map.get("sales")

        kpis    = st.session_state.get("_kpis")
        monthly = st.session_state.get("_monthly")
        seasonal= st.session_state.get("_seasonal", {})
        insights= []
        recs    = []

        if kpis and seasonal:
            insights = generate_insights(df, date_col, sales_col, kpis, seasonal)
            recs     = generate_recommendations(kpis, seasonal, None, None)
        elif date_col and sales_col:
            kpis     = compute_kpis(df, date_col, sales_col)
            seasonal = seasonal_analysis(df, date_col, sales_col)
            insights = generate_insights(df, date_col, sales_col, kpis, seasonal)
            recs     = generate_recommendations(kpis, seasonal, None, None)
            monthly  = monthly_trend(df, date_col, sales_col)

        forecast_results = st.session_state.get("forecast_results", {})
        forecast_df      = list(forecast_results.values())[0] if forecast_results else None

        metrics = st.session_state.get("trained_models")
        metrics_list = None
        if metrics:
            metrics_list = [{"model_name": n, **r["metrics"]} for n, r in metrics.items()]

        r1, r2, r3 = st.columns(3)

        with r1:
            st.subheader("📄 PDF Report")
            if st.button("Generate PDF", use_container_width=True, type="primary", key="gen_pdf"):
                with st.spinner("Generating PDF…"):
                    try:
                        pdf_bytes = generate_pdf_report(
                            proj.get("name","Project"),
                            kpis or {}, monthly, forecast_df,
                            insights, recs, metrics_list
                        )
                        st.download_button(
                            "⬇️ Download PDF Report",
                            pdf_bytes,
                            f"sales_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                            "application/pdf",
                            key="dl_pdf"
                        )
                        db_save_report(proj.get("id",""), uid,
                                        "Sales Analytics Report", "pdf",
                                        f"Generated {now_str()}")
                        st.success("✅ PDF ready!")
                    except Exception as e:
                        st.error(f"PDF generation failed: {e}")

        with r2:
            st.subheader("📊 Excel Report")
            if st.button("Generate Excel", use_container_width=True, key="gen_excel"):
                with st.spinner("Generating Excel…"):
                    try:
                        daily = st.session_state.get("_daily")
                        xlsx_bytes = generate_excel_report(
                            proj.get("name","Project"),
                            kpis or {}, monthly, forecast_df,
                            daily, metrics_list
                        )
                        st.download_button(
                            "⬇️ Download Excel Report",
                            xlsx_bytes,
                            f"sales_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_xlsx"
                        )
                        db_save_report(proj.get("id",""), uid,
                                        "Sales Analytics Report", "excel",
                                        f"Generated {now_str()}")
                        st.success("✅ Excel ready!")
                    except Exception as e:
                        st.error(f"Excel generation failed: {e}")

        with r3:
            st.subheader("📝 CSV Export")
            if st.button("Export Dataset CSV", use_container_width=True, key="gen_csv"):
                st.download_button(
                    "⬇️ Download Dataset CSV",
                    to_csv_bytes(df),
                    f"dataset_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv", key="dl_csv"
                )
                db_save_report(proj.get("id",""), uid,
                                "Dataset CSV Export", "csv",
                                f"Generated {now_str()}")

    with tab2:
        reports = db_get_reports(proj.get("id",""))
        if not reports:
            st.info("No reports generated yet.")
        else:
            for r in reports:
                st.markdown(
                    f"- **{r['title']}** · `{r['report_type'].upper()}` "
                    f"· {r['created_at'][:16]}"
                )


# ================================================================
# PAGE: SETTINGS
# ================================================================

def _page_settings():
    st.title("⚙️ Settings")
    uid  = st.session_state.user_id

    tab1, tab2, tab3 = st.tabs(["👤 Profile", "🗄️ Dataset Info", "👑 Admin"])

    with tab1:
        st.subheader("Account Information")
        st.markdown(f"**Name:** {st.session_state.full_name}")
        st.markdown(f"**Email:** {st.session_state.email}")
        st.markdown(f"**Role:** {(st.session_state.role or 'analyst').title()}")
        st.markdown(f"**User ID:** `{uid}`")

    with tab2:
        proj = st.session_state.active_project
        if proj:
            ds = db_get_dataset(proj["id"])
            if ds:
                st.subheader("Active Dataset Info")
                st.markdown(f"**File:** {ds['filename']}")
                st.markdown(f"**Rows:** {ds['rows']:,}  ·  **Cols:** {ds['cols']}")
                st.markdown(f"**Quality Score:** {ds['quality_score']}/100")
                st.markdown(f"**Date Col:** `{ds['date_col']}`  ·  **Sales Col:** `{ds['sales_col']}`")
                try:
                    cols = json.loads(ds["columns_json"])
                    st.markdown(f"**Columns:** {', '.join(cols)}")
                except: pass
            else:
                st.info("No dataset metadata found.")
        else:
            st.info("No active project.")

    with tab3:
        if not is_admin():
            st.warning("🔒 Admin access required.")
            return
        st.subheader("User Management (Admin)")
        users = db_get_all_users()
        for u in users:
            uc1, uc2, uc3 = st.columns([3,2,2])
            uc1.markdown(f"**{u['email']}**  \n{u['full_name']}")
            uc2.caption(u["role"].title())
            new_role = uc3.selectbox(
                "Change Role", ["analyst","admin"],
                index=0 if u["role"]=="analyst" else 1,
                key=f"role_{u['id']}"
            )
            if new_role != u["role"]:
                if st.button("Save", key=f"save_role_{u['id']}"):
                    db_update_user_role(u["id"], new_role)
                    st.success("Role updated.")
                    st.rerun()


# ================================================================
# HELPERS
# ================================================================

def _get_df_or_warn(silent=False):
    """Return (df, col_map) or (None, None) with a warning."""
    df      = st.session_state.get("active_df")
    col_map = st.session_state.get("col_map", {})
    if df is None and not silent:
        st.info(
            "📤 No dataset loaded.  \n"
            "Click **Explore Demo Dataset** on the Dashboard "
            "or go to **Upload Data** to load your own file."
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🎮 Load Demo"):
                _load_demo()
                st.rerun()
        with c2:
            if st.button("📤 Upload Data"):
                st.session_state.current_page = "upload"
                st.rerun()
        return None, None
    return df, col_map
