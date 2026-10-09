"""DocuMatch API.

Run from the project root:  uvicorn backend.main:app --reload
Docs at http://127.0.0.1:8000/docs
"""
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ml"))
from features import MISMATCH_COLS, NAME_COLS, mismatch_features, name_features, toks  # noqa: E402

name_model = joblib.load(ROOT / "models" / "name_matcher.joblib")
severity_model = joblib.load(ROOT / "models" / "severity_tree.joblib")
metrics = json.loads((ROOT / "models" / "metrics.json").read_text())
records = pd.read_csv(ROOT / "data" / "identity_records.csv", dtype=str)
persons = pd.read_csv(ROOT / "data" / "persons.csv", dtype=str)

app = FastAPI(title="DocuMatch API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

FIELDS = ["name", "father_name", "dob", "gender", "address"]
SEVERITY_RANK = {"acceptable": 0, "risky": 1, "critical": 2}
STATUS = {0: "clean", 1: "needs_review", 2: "critical"}
EXPLAIN = {
    "acceptable": "Formatting difference only (case, spacing or initials). Safe to accept.",
    "risky": "Spelling variant or different value. Needs a manual check.",
    "critical": "Likely a different person, date or gender. Do not accept without proof.",
}

# Common Indian-name spelling variations, applied in this order.
PHONETIC_RULES = [
    ("x", "ks"), ("ee", "i"), ("oo", "u"), ("aa", "a"),
    ("th", "t"), ("dh", "d"), ("bh", "b"), ("kh", "k"), ("gh", "g"),
    ("ph", "f"), ("sh", "s"), ("w", "v"), ("z", "j"),
]
SOUND_ALIKE_PROB = 0.95


# ---------- Schemas ----------
class NamePair(BaseModel):
    name_a: str = Field(..., examples=["Karthik Arun"])
    name_b: str = Field(..., examples=["KARTHIK A"])


class Document(BaseModel):
    doc_type: str = Field(..., examples=["aadhaar"])
    name: Optional[str] = None
    father_name: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None


class DocumentSet(BaseModel):
    documents: list[Document]


# ---------- Helpers ----------
def same_after_cleaning(a: str, b: str) -> bool:
    """True when two names differ only in case, dots, spacing or honorifics."""
    return " ".join(toks(a)) == " ".join(toks(b))


def phonetic(word: str) -> str:
    for old, new in PHONETIC_RULES:
        word = word.replace(old, new)
    return re.sub(r"(.)\1+", r"\1", word)  # collapse double letters


def sounds_alike(a: str, b: str) -> bool:
    """True when two names are spelling variants of each other (Ritu / Reetu, Laxmi / Lakshmi)."""
    return sorted(phonetic(t) for t in toks(a)) == sorted(phonetic(t) for t in toks(b))


def match_names(a: str, b: str) -> dict:
    feats = name_features(a, b)
    if same_after_cleaning(a, b):
        prob = 1.0  # identical after cleaning
    else:
        prob = float(name_model.predict_proba(pd.DataFrame([feats], columns=NAME_COLS))[0][1])
        if sounds_alike(a, b):
            prob = max(prob, SOUND_ALIKE_PROB)  # spelling variant of the same name
    return {
        "same_person_probability": round(prob, 4),
        "verdict": "same person" if prob >= 0.5 else "different person",
        "features": dict(zip(NAME_COLS, [round(float(f), 3) for f in feats])),
    }


def clean(v: Optional[str]) -> Optional[str]:
    return v.strip() if isinstance(v, str) and v.strip() else None


# ---------- Routes ----------
@app.get("/")
def root():
    return {"status": "ok", "service": "DocuMatch API"}


@app.post("/api/compare-names")
def compare_names(pair: NamePair):
    if not pair.name_a.strip() or not pair.name_b.strip():
        raise HTTPException(400, "Both names are required.")
    return {"name_a": pair.name_a, "name_b": pair.name_b, **match_names(pair.name_a, pair.name_b)}


@app.post("/api/check-documents")
def check_documents(payload: DocumentSet):
    docs = payload.documents
    if len(docs) < 2:
        raise HTTPException(400, "Provide at least 2 documents.")

    # Aadhaar is the reference document (as in the dataset); otherwise the first one.
    ref = next((d for d in docs if d.doc_type.lower() == "aadhaar"), docs[0])
    reference = {f: clean(getattr(ref, f)) for f in FIELDS}
    # Aadhaar has no father's name, so take it from the first document that has one.
    if reference["father_name"] is None:
        reference["father_name"] = next((clean(d.father_name) for d in docs if clean(d.father_name)), None)

    mismatches = []
    for d in docs:
        if d is ref:
            continue
        for f in FIELDS:
            rv, cv = reference[f], clean(getattr(d, f))
            if rv is None or cv is None or rv == cv:
                continue
            X = pd.DataFrame([mismatch_features(f, rv, cv)], columns=MISMATCH_COLS)
            severity = str(severity_model.predict(X)[0])
            # Names that differ only in case/dots/spacing are always just formatting.
            if f in ("name", "father_name") and same_after_cleaning(rv, cv):
                severity = "acceptable"
            item = {
                "compared_doc": d.doc_type,
                "field": f,
                "reference_value": rv,
                "compared_value": cv,
                "severity": severity,
                "explanation": EXPLAIN[severity],
            }
            if f in ("name", "father_name"):
                item["name_match"] = match_names(rv, cv)
            mismatches.append(item)

    worst = max((SEVERITY_RANK[m["severity"]] for m in mismatches), default=0)
    return {
        "reference_doc": ref.doc_type,
        "documents_checked": len(docs) - 1,
        "status": STATUS[worst],
        "summary": {s: sum(m["severity"] == s for m in mismatches) for s in SEVERITY_RANK},
        "mismatches": mismatches,
    }


@app.get("/api/metrics")
def get_metrics():
    return metrics


@app.get("/api/samples")
def samples(status: Optional[str] = None, n: int = 6):
    """Random sample people from the synthetic dataset, to try in the document checker."""
    pool = persons if status is None else persons[persons.verification_status == status]
    if pool.empty:
        raise HTTPException(404, "No people with that status.")
    picked = pool.sample(min(n, len(pool)))
    out = []
    for p in picked.itertuples():
        docs = records[records.person_id == p.person_id][["doc_type", *FIELDS]]
        out.append({
            "person_id": p.person_id,
            "full_name": p.full_name,
            "expected_status": p.verification_status,
            "documents": docs.astype(object).where(docs.notna(), None).to_dict(orient="records"),
        })
    return out