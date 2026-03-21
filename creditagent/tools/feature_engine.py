"""
feature_engine.py
Transform raw bank_data / borrower input → normalized feature vector
matching the FEATURES list used during XGBoost training.
"""

import numpy as np
from typing import Optional

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

# Median imputation values derived from LendingClub dataset
MEDIANS = {
    "dti": 18.5,
    "revol_util": 52.1,
    "int_rate": 13.5,
    "annual_inc": 65_000.0,
    "loan_amnt": 12_000.0,
    "open_acc": 11.0,
    "pub_rec": 0.0,
    "delinq_2yrs": 0.0,
    "inq_last_6mths": 0.0,
    "mort_acc": 1.0,
}


def build_feature_vector(bank_data: Optional[dict], loan_amnt: float = 10_000_000) -> dict:
    """
    Convert raw bank_data (from persona) to model features.
    If bank_data is None (thin-file), use median imputation.

    Parameters
    ----------
    bank_data : dict or None — raw bank data from persona
    loan_amnt : float — requested loan amount in VND

    Returns
    -------
    dict with keys matching FEATURES list
    """
    if bank_data is None:
        # Thin-file borrower → use medians (slightly pessimistic)
        features = {k: MEDIANS[k] for k in FEATURES}
        # Mark as thin-file with slightly worse-than-median defaults
        features["dti"] = 0.40 * 100          # 40% DTI → percentage
        features["revol_util"] = 60.0          # 60% utilization
        features["int_rate"] = 16.0            # higher rate proxy
        features["annual_inc"] = 30_000.0      # VND → USD rough proxy
        features["loan_amnt"] = loan_amnt / 24_000  # VND→USD rough proxy
        features["open_acc"] = 2.0
        features["pub_rec"] = 0.0
        features["delinq_2yrs"] = 0.0
        features["inq_last_6mths"] = 0.0
        features["mort_acc"] = 0.0
        return features

    annual_inc_usd = bank_data.get("annual_inc", bank_data.get("monthly_income", 0) * 12) / 24_000
    loan_amnt_usd = bank_data.get("loan_amnt", loan_amnt) / 24_000

    dti_raw = bank_data.get("dti", MEDIANS["dti"] / 100)
    revol_raw = bank_data.get("revol_util", MEDIANS["revol_util"] / 100)

    return {
        "dti": dti_raw * 100 if dti_raw <= 1.0 else dti_raw,
        "revol_util": revol_raw * 100 if revol_raw <= 1.0 else revol_raw,
        "int_rate": bank_data.get("int_rate", MEDIANS["int_rate"]),
        "annual_inc": max(annual_inc_usd, 1.0),
        "loan_amnt": max(loan_amnt_usd, 100.0),
        "open_acc": float(bank_data.get("open_acc", MEDIANS["open_acc"])),
        "pub_rec": float(bank_data.get("pub_rec", 0)),
        "delinq_2yrs": float(bank_data.get("delinq_2yrs", 0)),
        "inq_last_6mths": float(bank_data.get("inq_last_6mths", 0)),
        "mort_acc": float(bank_data.get("mort_acc", 0)),
    }


def to_array(features: dict) -> np.ndarray:
    """Convert features dict to numpy array in correct column order."""
    return np.array([[features[f] for f in FEATURES]], dtype=np.float32)
