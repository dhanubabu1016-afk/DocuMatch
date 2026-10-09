"""Train DocuMatch's two models and save them to models/.

Run from the project root:  python ml/train.py

1. Name matcher  - Random Forest on name_pairs.csv  (same person or not)
2. Severity model - CART decision tree on mismatch_labels.csv (acceptable / risky / critical)
"""
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.tree import DecisionTreeClassifier

from features import MISMATCH_COLS, NAME_COLS, mismatch_features, name_features

ROOT = Path(__file__).resolve().parent.parent
DATA, MODELS = ROOT / "data", ROOT / "models"
MODELS.mkdir(exist_ok=True)

persons = pd.read_csv(DATA / "persons.csv")
records = pd.read_csv(DATA / "identity_records.csv")
pairs = pd.read_csv(DATA / "name_pairs.csv")
mismatches = pd.read_csv(DATA / "mismatch_labels.csv")

# ---------- 1. Name matcher ----------
print("Building name-pair features...")
X = pd.DataFrame([name_features(a, b) for a, b in zip(pairs.name_a, pairs.name_b)], columns=NAME_COLS)
train, test = pairs.split == "train", pairs.split == "test"

rf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
rf.fit(X[train], pairs.label[train])
name_pred = rf.predict(X[test])
name_acc = accuracy_score(pairs.label[test], name_pred)
print(f"Name matcher accuracy: {name_acc:.4f}")

# ---------- 2. Severity classifier ----------
print("Building mismatch features...")
M = pd.DataFrame(
    [mismatch_features(r.field, r.reference_value, r.compared_value) for r in mismatches.itertuples()],
    columns=MISMATCH_COLS,
)
split_of = persons.set_index("person_id").split
m_split = mismatches.person_id.map(split_of)
mtr, mte = m_split == "train", m_split == "test"

cart = DecisionTreeClassifier(max_depth=3, random_state=42)
cart.fit(M[mtr], mismatches.severity[mtr])
sev_pred = cart.predict(M[mte])
sev_acc = accuracy_score(mismatches.severity[mte], sev_pred)
print(f"Severity classifier accuracy: {sev_acc:.4f}")

# ---------- Save models + dashboard metrics ----------
joblib.dump(rf, MODELS / "name_matcher.joblib")
joblib.dump(cart, MODELS / "severity_tree.joblib")

metrics = {
    "dataset": {
        "persons": len(persons),
        "documents": len(records),
        "name_pairs": len(pairs),
        "mismatches": len(mismatches),
        "doc_types": records.doc_type.value_counts().to_dict(),
        "verification_status": persons.verification_status.value_counts().to_dict(),
        "severity": mismatches.severity.value_counts().to_dict(),
        "mismatch_types": mismatches.mismatch_type.value_counts().to_dict(),
        "pair_types": pairs.pair_type.value_counts().to_dict(),
    },
    "name_matcher": {
        "model": "Random Forest (200 trees)",
        "accuracy": round(name_acc, 4),
        "test_size": int(test.sum()),
        "report": classification_report(pairs.label[test], name_pred, output_dict=True),
        "feature_importance": dict(zip(NAME_COLS, rf.feature_importances_.round(3).tolist())),
    },
    "severity_classifier": {
        "model": "CART decision tree (depth 3)",
        "accuracy": round(sev_acc, 4),
        "test_size": int(mte.sum()),
        "report": classification_report(mismatches.severity[mte], sev_pred, output_dict=True),
    },
}
(MODELS / "metrics.json").write_text(json.dumps(metrics, indent=2))
print(f"Saved models and metrics to {MODELS}")
