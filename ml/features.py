"""Feature engineering shared by training (ml/train.py) and the API (backend/)."""
from difflib import SequenceMatcher

import pandas as pd

HONORIFICS = {"mr", "ms", "mrs", "kumari", "selvi", "thiru", "shri", "smt"}

NAME_COLS = ["similarity", "sorted_similarity", "token_overlap", "initials_match", "length_diff"]
MISMATCH_COLS = ["similarity", "initials_match", "dob_diff", "is_name", "is_dob", "is_gender"]


def sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def toks(name: str) -> list[str]:
    return [t for t in str(name).lower().replace(".", " ").split() if t not in HONORIFICS]


def initials_ok(full: list[str], short: list[str]) -> bool:
    """True if `short` has single-letter initials that all match words in `full`."""
    inits = [t for t in short if len(t) == 1]
    return bool(inits) and all(any(len(w) > 1 and w[0] == i for w in full) for i in inits)


def name_features(a: str, b: str) -> list[float]:
    """5 features for a pair of names (Program 2 of the lab manual)."""
    ta, tb = toks(a), toks(b)
    union = set(ta) | set(tb)
    return [
        sim(" ".join(ta), " ".join(tb)),
        sim(" ".join(sorted(ta)), " ".join(sorted(tb))),
        len(set(ta) & set(tb)) / len(union) if union else 0.0,
        int(initials_ok(ta, tb) or initials_ok(tb, ta)),   # works in both directions now
        abs(len(" ".join(ta)) - len(" ".join(tb))),         # length of cleaned names
    ]


def mismatch_features(field: str, reference_value, compared_value) -> list[float]:
    """6 features for one field-level mismatch (Program 5.1 of the lab manual)."""
    a, b = str(reference_value), str(compared_value)
    days = 0
    if field == "dob":
        try:
            days = abs((pd.Timestamp(b) - pd.Timestamp(a)).days)
        except (ValueError, TypeError):
            days = 400
    return [
        sim(a.lower(), b.lower()),
        name_features(a, b)[3],
        min(days, 400) / 400,
        int(field in ("name", "father_name")),
        int(field == "dob"),
        int(field == "gender"),
    ]