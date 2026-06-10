-- ================================================================
-- schema.sql  —  Complete Supabase Database Schema
-- ================================================================
-- HOW TO RUN:
--   Supabase Dashboard → SQL Editor → New Query → Paste → Run
-- ================================================================

-- ── USERS (app-managed auth with password hashing) ──────────────
DROP TABLE IF EXISTS public.users CASCADE;

CREATE TABLE IF NOT EXISTS public.users (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email        TEXT NOT NULL UNIQUE,
    full_name    TEXT DEFAULT '',
    role         TEXT DEFAULT 'analyst' CHECK (role IN ('admin','analyst')),
    avatar_url   TEXT DEFAULT '',
    password_hash TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);

-- ── PROJECTS ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.projects (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    description  TEXT DEFAULT '',
    status       TEXT DEFAULT 'active' CHECK (status IN ('active','archived','deleted')),
    dataset_rows INTEGER DEFAULT 0,
    dataset_cols INTEGER DEFAULT 0,
    date_range   TEXT DEFAULT '',
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_projects_user ON public.projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON public.projects(status);

-- ── DATASETS ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.datasets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    rows            INTEGER DEFAULT 0,
    cols            INTEGER DEFAULT 0,
    columns_json    TEXT DEFAULT '[]',
    date_col        TEXT DEFAULT '',
    sales_col       TEXT DEFAULT '',
    product_col     TEXT DEFAULT '',
    region_col      TEXT DEFAULT '',
    quality_score   FLOAT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_datasets_project ON public.datasets(project_id);
CREATE INDEX IF NOT EXISTS idx_datasets_user    ON public.datasets(user_id);

-- ── FORECASTS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.forecasts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    model_name      TEXT NOT NULL,
    horizon         TEXT NOT NULL,   -- '7d','30d','90d','6m'
    mae             FLOAT DEFAULT 0,
    rmse            FLOAT DEFAULT 0,
    r2              FLOAT DEFAULT 0,
    mape            FLOAT DEFAULT 0,
    is_best         BOOLEAN DEFAULT FALSE,
    forecast_json   TEXT DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_forecasts_project ON public.forecasts(project_id);
CREATE INDEX IF NOT EXISTS idx_forecasts_best    ON public.forecasts(is_best);

-- ── MODEL METRICS ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.model_metrics (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    model_name   TEXT NOT NULL,
    mae          FLOAT DEFAULT 0,
    rmse         FLOAT DEFAULT 0,
    r2           FLOAT DEFAULT 0,
    mape         FLOAT DEFAULT 0,
    train_rows   INTEGER DEFAULT 0,
    test_rows    INTEGER DEFAULT 0,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_metrics_project ON public.model_metrics(project_id);

-- ── REPORTS ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.reports (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    report_type  TEXT DEFAULT 'pdf' CHECK (report_type IN ('pdf','excel','csv')),
    summary      TEXT DEFAULT '',
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reports_project ON public.reports(project_id);

-- ── AUTO-UPDATE updated_at ────────────────────────────────────
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END; $$;

DROP TRIGGER IF EXISTS users_touch    ON public.users;
DROP TRIGGER IF EXISTS projects_touch ON public.projects;
CREATE TRIGGER users_touch    BEFORE UPDATE ON public.users    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER projects_touch BEFORE UPDATE ON public.projects FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ── ROW LEVEL SECURITY ────────────────────────────────────────
ALTER TABLE public.users         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.datasets      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.forecasts     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.model_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reports       ENABLE ROW LEVEL SECURITY;

-- Open policies for service-role key (app enforces user_id checks)
DROP POLICY IF EXISTS "all_users"    ON public.users;
DROP POLICY IF EXISTS "all_projects" ON public.projects;
DROP POLICY IF EXISTS "all_datasets" ON public.datasets;
DROP POLICY IF EXISTS "all_forecast" ON public.forecasts;
DROP POLICY IF EXISTS "all_metrics"  ON public.model_metrics;
DROP POLICY IF EXISTS "all_reports"  ON public.reports;

CREATE POLICY "all_users"    ON public.users         FOR ALL USING (true);
CREATE POLICY "all_projects" ON public.projects      FOR ALL USING (true);
CREATE POLICY "all_datasets" ON public.datasets      FOR ALL USING (true);
CREATE POLICY "all_forecast" ON public.forecasts     FOR ALL USING (true);
CREATE POLICY "all_metrics"  ON public.model_metrics FOR ALL USING (true);
CREATE POLICY "all_reports"  ON public.reports       FOR ALL USING (true);

-- ── VERIFY ────────────────────────────────────────────────────
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' ORDER BY table_name;
