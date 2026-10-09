# DocuMatch

**Cross-document identity consistency checker.**

DocuMatch checks whether a person's identity documents (Aadhaar, PAN, marksheets, birth certificate) agree with each other. Aadhaar is the reference, and every other document is compared field by field (name, father's name, DOB, gender, address). Each mismatch is graded **Acceptable**, **Risky** or **Critical**, with a plain-language reason.

**Live demo:** [docu-match-beta.vercel.app](https://docu-match-beta.vercel.app)
<sub>The first request can take up to about 50 seconds while the server wakes up.</sub>

> Synthetic data only. No real person's documents are used.

---

## Screenshots

| Check Documents | Compare Names | Dashboard |
|---|---|---|
| ![Check documents](docs/screenshots/check-documents.png) | ![Compare names](docs/screenshots/compare-names.png) | ![Dashboard](docs/screenshots/dashboard.png) |

---

## How it works

| Component | Role |
|---|---|
| **Random Forest** name matcher | Decides whether two spellings are the same person (`Karthik Arun` vs `KARTHIK A`) using 5 features: similarity, sorted similarity, token overlap, initials match, length difference |
| **Phonetic rule layer** | Catches Indian spelling variants the model can't (`Ritu` / `Reetu`, `Laxmi` / `Lakshmi`) |
| **CART decision tree** | Grades each mismatch as Acceptable, Risky or Critical |

| Severity | Meaning | Example |
|---|---|---|
| Acceptable | Formatting only | `RAJU S` vs `Raju Senthil` |
| Risky | Needs manual check | `Madhavna` vs `Madhavan` |
| Critical | Likely a different person | DOB year shift, gender flip |

---

## Results

| Model | Accuracy | Test set |
|---|---|---|
| Name matcher (Random Forest, 200 trees) | **96.7%** | 7,500 name pairs |
| Severity classifier (CART, depth 3) | **98.4%** | 1,333 mismatches |

Trained on a synthetic dataset of 5,000 people, 23,829 documents and 50,000 labelled name pairs.

---

## Tech stack

**Frontend:** React, Vite (Vercel) · **Backend:** FastAPI (Render) · **ML:** scikit-learn, pandas

---

## Run locally

```bash
# Backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd backend && uvicorn main:app --reload

# Frontend (new terminal)
cd frontend && npm install && npm run dev
```

Open `http://localhost:5173`.

---

## Author

**Dhanalakshmi B**