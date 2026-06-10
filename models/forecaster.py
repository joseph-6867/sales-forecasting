# ================================================================
# models/forecaster.py  —  ML Forecasting Engine
# ================================================================
# Models:
#   1. Linear Regression      (sklearn)
#   2. Random Forest          (sklearn)
#   3. Gradient Boosting Regressor  (sklearn)
#
# Each model is trained, evaluated, and can predict forward.
# Evaluation metrics: MAE, RMSE, R², MAPE
# ================================================================

import numpy as np
import pandas as pd
import joblib
import io
from datetime import timedelta

from sklearn.linear_model     import LinearRegression
from sklearn.ensemble         import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing    import StandardScaler
from sklearn.model_selection  import TimeSeriesSplit
from sklearn.metrics          import mean_absolute_error, mean_squared_error, r2_score

from services.data_processor import engineer_features, get_feature_cols


# ── Metric Helpers ────────────────────────────────────────────

def calc_mape(y_true, y_pred):
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    mask   = y_true != 0
    if mask.sum() == 0: return 0.0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)

def calc_metrics(y_true, y_pred):
    mae  = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2   = r2_score(y_true, y_pred)
    mape = calc_mape(y_true, y_pred)
    return {"mae": mae, "rmse": rmse, "r2": r2, "mape": mape}


# ── Model Builders ────────────────────────────────────────────

def _build_lr():
    return LinearRegression()

def _build_rf():
    return RandomForestRegressor(
        n_estimators=200, max_depth=8,
        min_samples_leaf=2, random_state=42, n_jobs=-1
    )

def _build_gb():
    return GradientBoostingRegressor(
        n_estimators=300, max_depth=6,
        learning_rate=0.05, subsample=0.8,
        random_state=42
    )

MODEL_BUILDERS = {
    "Linear Regression": _build_lr,
    "Random Forest":     _build_rf,
    "Gradient Boosting": _build_gb,
}


# ── Train All Models ──────────────────────────────────────────

def train_all_models(daily_df, date_col, test_size=0.2):
    """
    Train all three models on the daily aggregated DataFrame.

    Returns:
      results: dict  {model_name: {model, scaler, metrics, y_test, y_pred}}
      feature_cols: list of feature column names
    """
    feature_cols = get_feature_cols(daily_df, date_col)
    X = daily_df[feature_cols].values
    y = daily_df["daily_sales"].values

    split_idx  = int(len(X) * (1 - test_size))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    results = {}

    for name, builder in MODEL_BUILDERS.items():
        try:
            # Scale features (important for LR and XGB)
            scaler  = StandardScaler()
            Xtr_sc  = scaler.fit_transform(X_train)
            Xte_sc  = scaler.transform(X_test)

            model   = builder()
            model.fit(Xtr_sc, y_train)
            y_pred  = model.predict(Xte_sc)
            metrics = calc_metrics(y_test, y_pred)

            results[name] = {
                "model":        model,
                "scaler":       scaler,
                "metrics":      metrics,
                "y_test":       y_test,
                "y_pred":       y_pred,
                "feature_cols": feature_cols,
                "split_idx":    split_idx,
            }
        except Exception as e:
            print(f"[Forecaster] {name} training failed: {e}")

    return results, feature_cols


def select_best_model(results):
    """
    Pick the model with the lowest RMSE.
    Returns model_name string.
    """
    if not results: return None
    return min(results.keys(), key=lambda k: results[k]["metrics"]["rmse"])


# ── Forecasting ───────────────────────────────────────────────

def generate_forecast(daily_df, date_col, model_info, horizon_days):
    """
    Generate future-date predictions for `horizon_days` ahead.

    Strategy:
      1. Start from the last known date
      2. For each future day, build features based on the
         rolling history (including previously predicted values)
      3. Predict iteratively

    Returns a DataFrame with columns: date, forecast
    """
    model        = model_info["model"]
    scaler       = model_info["scaler"]
    feature_cols = model_info["feature_cols"]

    # Work on a copy extended with predictions
    hist = daily_df[[date_col, "daily_sales"]].copy()
    hist[date_col] = pd.to_datetime(hist[date_col])
    hist = hist.sort_values(date_col).reset_index(drop=True)

    last_date   = hist[date_col].max()
    pred_dates  = []
    pred_values = []

    for i in range(1, horizon_days + 1):
        future_date = last_date + timedelta(days=i)

        # Append a placeholder so feature eng works
        new_row = pd.DataFrame({date_col: [future_date], "daily_sales": [np.nan]})
        extended = pd.concat([hist, new_row], ignore_index=True)

        # Re-engineer features
        try:
            feat_df = _build_one_row_features(extended, date_col, future_date, feature_cols)
        except Exception:
            break

        if feat_df is None or not isinstance(feat_df, dict):
            break

        try:
            X_future = np.array([[feat_df.get(c, 0) for c in feature_cols]])
            X_scaled = scaler.transform(X_future)
            pred_val  = max(0.0, float(model.predict(X_scaled)[0]))

            pred_dates.append(future_date)
            pred_values.append(round(pred_val, 2))

            # Fill the placeholder with prediction so next lag is correct
            hist = pd.concat([hist, pd.DataFrame({
                date_col: [future_date], "daily_sales": [pred_val]
            })], ignore_index=True)
        except Exception:
            # If prediction fails, stop forecasting
            break

    return pd.DataFrame({"date": pred_dates, "forecast": pred_values})


def _build_one_row_features(hist, date_col, target_date, feature_cols):
    """
    Build the feature vector for a single future date
    based on the current history DataFrame.
    """
    try:
        engineered = engineer_features(hist, date_col, "daily_sales")
        if engineered is None:
            raise ValueError("engineer_features returned None")
        row = engineered[engineered[date_col] == target_date]
        if row.empty:
            # Take last row as approximation
            row = engineered.tail(1)
        result = row[feature_cols].iloc[0].to_dict()
        if result is None:
            raise ValueError("Feature row is None")
        return result
    except Exception as e:
        # Fallback: manual calendar features only
        try:
            d = pd.Timestamp(target_date)
            sales_hist = hist["daily_sales"].dropna().values
            lag1 = float(sales_hist[-1]) if len(sales_hist) >= 1 else 0
            lag7 = float(sales_hist[-7]) if len(sales_hist) >= 7 else lag1
            roll = float(np.mean(sales_hist[-7:])) if len(sales_hist) >= 7 else lag1
            row = {
                "year": d.year, "month": d.month,
                "quarter": d.quarter, "week_num": d.isocalendar().week,
                "day_of_week": d.dayofweek, "is_weekend": int(d.dayofweek >= 5),
                "day_of_year": d.dayofyear,
                "lag_1": lag1, "lag_7": lag7,
                "rolling_mean_7": roll, "rolling_std_7": 0,
                "rolling_mean_14": roll, "rolling_std_14": 0,
                "rolling_mean_30": roll, "rolling_std_30": 0,
            }
            fallback_dict = {k: row.get(k, 0) for k in feature_cols}
            if fallback_dict is None:
                # Final safety: return minimal dict
                fallback_dict = {k: 0 for k in feature_cols}
            return fallback_dict
        except Exception:
            # Ultimate fallback: return zero dict for all features
            return {k: 0 for k in feature_cols}


# ── Feature Importance ────────────────────────────────────────

def get_feature_importance(model_info, feature_cols):
    """
    Return a DataFrame of feature importances for RF / Gradient Boosting.
    Returns None for Linear Regression.
    """
    model = model_info["model"]
    try:
        if hasattr(model, "feature_importances_"):
            fi = pd.DataFrame({
                "feature":    feature_cols,
                "importance": model.feature_importances_
            }).sort_values("importance", ascending=False)
            return fi
        if hasattr(model, "coef_"):
            fi = pd.DataFrame({
                "feature":    feature_cols,
                "importance": np.abs(model.coef_)
            }).sort_values("importance", ascending=False)
            return fi
    except Exception: pass
    return None


# ── Save / Load Model ─────────────────────────────────────────

def save_model_bytes(model_info):
    """Serialise model + scaler to bytes for download."""
    buf = io.BytesIO()
    joblib.dump(model_info, buf)
    return buf.getvalue()
