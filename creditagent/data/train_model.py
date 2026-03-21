"""
Train XGBoost model on LendingClub dataset.
Saves model to models/xgboost_model.pkl
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DATA_PATH = os.getenv("DATA_PATH", str(ROOT.parent / "accepted_2007_to_2018Q4.csv.gz"))
MODEL_DIR = ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)

FEATURES = [
    "dti",
    "revol_util",
    "int_rate",
    "annual_inc",
    "loan_amnt",
    "open_acc",
    "pub_rec",
    "delinq_2yrs",
    "inq_last_6mths",
    "mort_acc",
]
TARGET = "loan_status"
SAMPLE_SIZE = 100_000
RANDOM_STATE = 42


def load_and_prepare(path: str) -> pd.DataFrame:
    print(f"Loading data from: {path}")
    df = pd.read_csv(path, low_memory=False)
    print(f"Total rows: {len(df):,}")

    # Keep only Fully Paid / Charged Off / Default
    valid_statuses = {"Fully Paid", "Charged Off", "Default"}
    df = df[df[TARGET].isin(valid_statuses)].copy()
    print(f"After filtering statuses: {len(df):,}")

    # Sample
    if len(df) > SAMPLE_SIZE:
        df = df.sample(n=SAMPLE_SIZE, random_state=RANDOM_STATE)
        print(f"Sampled {SAMPLE_SIZE:,} rows")

    # Create binary label: Default / Charged Off → 1, Fully Paid → 0
    df["label"] = df[TARGET].apply(lambda x: 0 if x == "Fully Paid" else 1)

    # Clean int_rate (may have % sign)
    if df["int_rate"].dtype == object:
        df["int_rate"] = df["int_rate"].str.replace("%", "").astype(float)

    # Clean revol_util
    if df["revol_util"].dtype == object:
        df["revol_util"] = df["revol_util"].str.replace("%", "").astype(float)

    # Keep only needed columns
    keep_cols = FEATURES + ["label"]
    df = df[keep_cols].copy()

    # Fill missing values with median
    for col in FEATURES:
        median_val = df[col].median()
        df[col] = df[col].fillna(median_val)

    print(f"Label distribution:\n{df['label'].value_counts()}")
    return df


def train(df: pd.DataFrame):
    X = df[FEATURES].values
    y = df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    print("\nTraining XGBoost…")
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=(y_train == 0).sum() / (y_train == 1).sum(),
        use_label_encoder=False,
        eval_metric="auc",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        verbose=50,
    )

    y_pred_proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_pred_proba)
    print(f"\n✅  Test AUC: {auc:.4f}")

    # Feature importance
    print("\nFeature Importances:")
    for feat, imp in sorted(
        zip(FEATURES, model.feature_importances_), key=lambda x: -x[1]
    ):
        print(f"  {feat:<25} {imp:.4f}")

    return model


def save(model):
    model_path = MODEL_DIR / "xgboost_model.pkl"
    feat_path = MODEL_DIR / "feature_names.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    with open(feat_path, "wb") as f:
        pickle.dump(FEATURES, f)
    print(f"\n✅  Model saved → {model_path}")
    print(f"✅  Feature names saved → {feat_path}")


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        DATA_PATH = os.getenv("DATA_PATH", DATA_PATH)
    except ImportError:
        pass

    df = load_and_prepare(DATA_PATH)
    model = train(df)
    save(model)
    print("\n🎉  Training complete!")
