from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import log_loss, brier_score_loss
from .features import FEATURES, build_features


LEAKAGE_COLUMNS = {
    "is_winner",
    "is_top3",
    "finish_position",
    "first",
    "second",
    "third",
    "payout",
    "profit",
    "roi",
    "result",
}


def validate_no_leakage_features(features=FEATURES):
    leaked = sorted(set(features) & LEAKAGE_COLUMNS)
    if leaked:
        raise ValueError(f"Post-race columns cannot be used as features: {leaked}")


def time_split(df, holdout_days=30):
    x = df.copy()
    x["date"] = pd.to_datetime(x["date"])
    cutoff = x["date"].max() - pd.Timedelta(days=holdout_days)
    train, valid = x[x["date"] < cutoff], x[x["date"] >= cutoff]
    if train.empty or valid.empty:
        raise ValueError("時系列分割に必要な期間が不足しています")
    return train, valid

def train_model(df, holdout_days=30):
    validate_no_leakage_features()
    data = build_features(df)
    if "is_winner" not in data.columns:
        raise ValueError("is_winner is required as the training target")
    train, valid = time_split(data, holdout_days)
    base = HistGradientBoostingClassifier(learning_rate=0.05,max_leaf_nodes=15,min_samples_leaf=20,l2_regularization=1.0,random_state=42)
    model = CalibratedClassifierCV(base, method="sigmoid", cv=3)
    model.fit(train[FEATURES], train["is_winner"].astype(int))
    p = np.clip(model.predict_proba(valid[FEATURES])[:,1], 1e-6, 1-1e-6)
    report = {"rows":len(data),"races":data["race_id"].nunique(),"log_loss":float(log_loss(valid["is_winner"],p)),"brier":float(brier_score_loss(valid["is_winner"],p))}
    return model, report

def save_model(model, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)

def load_model(path):
    return joblib.load(path)

def predict_win_prob(model, df):
    data = build_features(df)
    data["win_prob_model_raw"] = model.predict_proba(data[FEATURES])[:,1]
    denom = data.groupby("race_id")["win_prob_model_raw"].transform("sum")
    data["win_prob_model"] = data["win_prob_model_raw"] / denom
    return data
