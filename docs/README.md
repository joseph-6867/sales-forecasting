# 📊 Intelligent Sales Forecasting & Business Analytics Platform

> **Production-Ready · Final-Year Project · Portfolio Showcase**  
> Python · Streamlit · Supabase · scikit-learn · XGBoost · Plotly · ReportLab

---

## 🚀 Features

| Module | Description |
|---|---|
| 🔐 Authentication | Register, Login, Logout, Forgot Password, Role-Based (Admin / Analyst) |
| 🏠 Welcome Dashboard | Feature showcase, demo dataset, recent projects, quick stats |
| 📁 Project Workspace | Create, open, delete projects; metadata stored in Supabase |
| 📤 Data Upload | CSV & Excel; auto-detects date/sales/product/region columns |
| 🔍 Data Validation | Missing values, duplicates, outliers, quality score 0–100 |
| 🧹 Auto-Cleaning | Fill nulls, remove duplicates, clip negatives |
| ⚙️ Feature Engineering | Year/month/quarter/week/DOW + lag + rolling features |
| 📈 Analytics | Daily/weekly/monthly/yearly trends, seasonal analysis |
| 📦 Product Analysis | Top products, revenue share, monthly trend comparison |
| 🗺️ Region Analysis | Regional breakdown, share pie, monthly comparison |
| 🔮 ML Forecasting | Linear Regression · Random Forest · XGBoost; auto-selects best |
| 📊 Model Evaluation | MAE · RMSE · R² · MAPE; feature importance charts |
| 🧠 AI Insights | Growth trends, peak periods, seasonal patterns (auto-generated) |
| 🎯 Recommendations | Inventory, demand alerts, revenue, regional suggestions |
| 🎮 Scenario Simulator | Growth%, demand%, discount% sliders vs baseline forecast |
| 📋 Reports | PDF (ReportLab), Excel (openpyxl), CSV downloads |

---

## 🗂️ Project Structure

```
sales_platform/
├── app.py                      ← Entry point (streamlit run app.py)
├── requirements.txt
├── .env.example
│
├── config/
│   └── settings.py             ← Global config, colour palette, constants
│
├── backend/
│   ├── auth.py                 ← Supabase Auth (register/login/logout/reset)
│   └── database.py             ← All Supabase CRUD operations
│
├── services/
│   ├── data_processor.py       ← Validation, cleaning, feature engineering
│   └── analytics.py            ← KPIs, trends, seasonal, product, region, insights
│
├── models/
│   └── forecaster.py           ← LR · RF · XGBoost training, evaluation, forecast
│
├── frontend/
│   ├── charts.py               ← All Plotly chart generators
│   └── dashboard.py            ← Complete 11-page dashboard UI
│
├── reports/
│   └── report_generator.py     ← PDF (ReportLab) + Excel (openpyxl) reports
│
├── utils/
│   ├── helpers.py              ← Formatters, file I/O, column detection
│   └── demo_data.py            ← 2-year synthetic sales dataset generator
│
├── database/
│   └── schema.sql              ← Full Supabase schema + RLS policies
│
└── docs/
    └── README.md               ← This file
```

---

## ⚡ Quick Start (4 Steps)

### 1 — Install Dependencies
```bash
pip install -r requirements.txt
```

### 2 — Set Up Supabase (Free)
1. Go to [supabase.com](https://supabase.com) → **New Project**
2. **SQL Editor → New Query** → paste `database/schema.sql` → **Run**
3. **Settings → API** → copy **Project URL** and **anon key**

### 3 — Configure Environment
```bash
cp .env.example .env
# Fill in SUPABASE_URL and SUPABASE_ANON_KEY
```

### 4 — Run
```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) 🎉

> **No Supabase?** Click **"Try Demo (no login)"** on the login page for instant access.

---

## 🗄️ Database Schema

```
users           — profile + role (analyst | admin)
projects        — workspace containers
datasets        — upload metadata (rows, cols, column mapping, quality score)
forecasts       — ML forecast results + metrics
model_metrics   — MAE/RMSE/R²/MAPE per model per project
reports         — generated report history
```

All tables have **Row Level Security (RLS)** enabled.

---

## 🤖 ML Models Explained

### Linear Regression
- Simple baseline; fast; works well on linear trends
- Feature coefficients show direction of influence

### Random Forest Regressor
- Ensemble of 200 decision trees
- Handles non-linear patterns and feature interactions
- Feature importance via mean decrease in impurity

### XGBoost Regressor
- Gradient-boosted trees; state-of-the-art for tabular data
- 300 estimators, learning rate 0.05, depth 6
- Often achieves lowest RMSE

**Feature Engineering** (all models):
- Calendar: year, month, quarter, week_num, day_of_week, is_weekend
- Lag features: lag_1, lag_7, lag_14, lag_30
- Rolling stats: rolling_mean_7/14/30, rolling_std_7/14/30

**Auto-selection**: The model with the lowest RMSE on the hold-out set is marked as Best.

---

## 📊 Sample Dataset

Built-in 2-year synthetic dataset (2022–2023):
- **8 products** across **5 regions**
- Seasonal peaks (Q4), weekly patterns, yearly growth trend
- Columns: date, product, category, region, city, quantity, unit_price, discount, sales, profit

Click **"Explore Demo Dataset"** on the home page — no upload needed.

---

## 🚢 Deployment

### Streamlit Cloud
1. Push to a **private** GitHub repo (`.env` in `.gitignore`)
2. [share.streamlit.io](https://share.streamlit.io) → New App → select `app.py`
3. **Advanced → Secrets** (TOML format):
```toml
SUPABASE_URL      = "https://..."
SUPABASE_ANON_KEY = "eyJ..."
```

### Render
Use the included `render.yaml` — connects to your GitHub repo.

---

## 🐛 Troubleshooting

| Problem | Fix |
|---|---|
| `Supabase credentials missing` | Check `.env` has correct URL and key |
| `No date column detected` | Column name must contain: date, time, period, month |
| `Training failed` | Need ≥ 30 rows; ensure sales column is numeric |
| `PDF generation error` | Run `pip install reportlab` |
| `XGBoost not found` | Run `pip install xgboost` |
| `Demo mode, can't save` | Register/Login to enable project saving |

---

## 📝 License
MIT — free for educational and portfolio use.
