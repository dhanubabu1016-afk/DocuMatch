import { useEffect, useState } from "react";
import "./index.css";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const FIELDS = ["name", "father_name", "dob", "gender", "address"];
const DOC_LABELS = {
  aadhaar: "Aadhaar",
  pan: "PAN",
  marksheet_10: "10th Marksheet",
  marksheet_12: "12th Marksheet",
  passport: "Passport",
  birth_certificate: "Birth Certificate",
};
const STATUS_TEXT = {
  clean: "All documents are consistent",
  needs_review: "Needs manual review",
  critical: "Critical mismatch found",
};

async function api(path, body) {
  const res = await fetch(API + path, body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : undefined);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

const pct = (x) => `${(x * 100).toFixed(1)}%`;
const pctProb = (x) => x > 0.99 ? "> 99%" : x < 0.01 ? "< 1%" : `${(x * 100).toFixed(1)}%`;
const label = (s) => s.replace(/_/g, " ");

export default function App() {
  const [tab, setTab] = useState("check");
  const tabs = [
    ["check", "Check Documents"],
    ["compare", "Compare Names"],
    ["dashboard", "Dashboard"],
  ];
  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="logo">DM</span>
          <div>
            <h1>DocuMatch</h1>
            <p>Cross-document identity consistency checker</p>
          </div>
        </div>
        <nav className="tabs">
          {tabs.map(([key, text]) => (
            <button key={key} className={tab === key ? "tab active" : "tab"} onClick={() => setTab(key)}>
              {text}
            </button>
          ))}
        </nav>
      </header>
      <main>
        {tab === "check" && <CheckDocuments />}
        {tab === "compare" && <CompareNames />}
        {tab === "dashboard" && <Dashboard />}
      </main>
      <footer>Synthetic data only. No real person's documents are used.</footer>
    </div>
  );
}

/* ---------------- Check Documents ---------------- */
function CheckDocuments() {
  const [person, setPerson] = useState(null);
  const [docs, setDocs] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function loadSample(status) {
    setError(""); setResult(null); setLoading(true);
    try {
      const [p] = await api(`/api/samples?n=1&status=${status}`);
      setPerson(p);
      setDocs(p.documents);
    } catch (e) { setError(e.message); }
    setLoading(false);
  }

  async function runCheck() {
    setError(""); setLoading(true);
    try { setResult(await api("/api/check-documents", { documents: docs })); }
    catch (e) { setError(e.message); }
    setLoading(false);
  }

  function edit(i, field, value) {
    setDocs(docs.map((d, j) => (j === i ? { ...d, [field]: value || null } : d)));
    setResult(null);
  }

  return (
    <section>
      <div className="card">
        <h2>Check a document set</h2>
        <p className="muted">
          Load a person from the dataset, edit any field if you like, then run the check.
          Aadhaar is the reference; every other document is compared against it.
        </p>
        <div className="row">
          <button className="btn" onClick={() => loadSample("clean")} disabled={loading}>Load clean person</button>
          <button className="btn" onClick={() => loadSample("needs_review")} disabled={loading}>Load needs-review person</button>
          <button className="btn" onClick={() => loadSample("critical")} disabled={loading}>Load critical person</button>
        </div>
        {error && <p className="error">{error}</p>}
      </div>

      {docs.length > 0 && (
        <div className="card">
          <div className="row spread">
            <h3>{person.full_name} <span className="muted small">({person.person_id})</span></h3>
            <button className="btn primary" onClick={runCheck} disabled={loading}>
              {loading ? "Checking..." : "Run check"}
            </button>
          </div>
          <div className="table-wrap">
            <table className="doc-table">
              <thead>
                <tr><th>Document</th>{FIELDS.map((f) => <th key={f}>{label(f)}</th>)}</tr>
              </thead>
              <tbody>
                {docs.map((d, i) => (
                  <tr key={i}>
                    <td className="doc-name">{DOC_LABELS[d.doc_type] || d.doc_type}</td>
                    {FIELDS.map((f) => (
                      <td key={f}>
                        <input value={d[f] ?? ""} placeholder="-" onChange={(e) => edit(i, f, e.target.value)} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {result && (
        <div className="card">
          <div className={`status ${result.status}`}>
            <strong>{STATUS_TEXT[result.status]}</strong>
            <span>{result.documents_checked} documents checked against {DOC_LABELS[result.reference_doc] || result.reference_doc}</span>
          </div>
          <div className="row chips">
            {Object.entries(result.summary).map(([s, n]) => (
              <span key={s} className={`badge ${s}`}>{n} {s}</span>
            ))}
          </div>
          {person && (
            <p className="muted small">
              Ground-truth status in the dataset: <b>{label(person.expected_status)}</b>
              {person.expected_status === result.status ? " (matches)" : " (differs)"}
            </p>
          )}
          {result.mismatches.length === 0 ? (
            <p>No differences between documents.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Document</th><th>Field</th><th>Aadhaar / reference</th><th>This document</th><th>Severity</th><th>Why</th></tr>
                </thead>
                <tbody>
                  {result.mismatches.map((m, i) => (
                    <tr key={i}>
                      <td>{DOC_LABELS[m.compared_doc] || m.compared_doc}</td>
                      <td>{label(m.field)}</td>
                      <td>{m.reference_value}</td>
                      <td>{m.compared_value}</td>
                      <td><span className={`badge ${m.severity}`}>{m.severity}</span></td>
                      <td className="small">
                        {m.explanation}
                        {m.name_match && <div className="muted">Name match: {pctProb(m.name_match.same_person_probability)}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

/* ---------------- Compare Names ---------------- */
const EXAMPLES = [
  ["Karthik Arun", "KARTHIK A"],
  ["Ritu Mishra", "Reetu Mishra"],
  ["Priya Ramesh", "R. Priya"],
  ["Amit Gupta", "Anagha Kurup"],
];

function CompareNames() {
  const [a, setA] = useState("Karthik Arun");
  const [b, setB] = useState("KARTHIK A");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function compare(x = a, y = b) {
    setError("");
    try { setResult(await api("/api/compare-names", { name_a: x, name_b: y })); }
    catch (e) { setError(e.message); setResult(null); }
  }

  const same = result && result.same_person_probability >= 0.5;
  return (
    <section>
      <div className="card">
        <h2>Compare two names</h2>
        <p className="muted">The Random Forest model decides whether two spellings belong to the same person.</p>
        <div className="row">
          <input className="big" value={a} onChange={(e) => setA(e.target.value)} placeholder="Name on document A" />
          <input className="big" value={b} onChange={(e) => setB(e.target.value)} placeholder="Name on document B" />
          <button className="btn primary" onClick={() => compare()}>Compare</button>
        </div>
        <div className="row chips">
          <span className="muted small">Try:</span>
          {EXAMPLES.map(([x, y]) => (
            <button key={x + y} className="chip" onClick={() => { setA(x); setB(y); compare(x, y); }}>
              {x} vs {y}
            </button>
          ))}
        </div>
        {error && <p className="error">{error}</p>}
      </div>

      {result && (
        <div className="card">
          <div className={`status ${same ? "clean" : "critical"}`}>
            <strong>{same ? "Same person" : "Different person"}</strong>
            <span>Match probability {pctProb(result.same_person_probability)}</span>
          </div>
          <div className="meter"><div style={{ width: pct(result.same_person_probability) }} /></div>
          <h3>Features the model used</h3>
          <div className="features">
            {Object.entries(result.features).map(([k, v]) => (
              <div key={k} className="feature">
                <span className="muted small">{label(k)}</span>
                <b>{v}</b>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

/* ---------------- Dashboard ---------------- */
function Bars({ data, total }) {
  const max = Math.max(...Object.values(data));
  return (
    <div className="bars">
      {Object.entries(data).map(([k, v]) => (
        <div key={k} className="bar-row">
          <span className="bar-label">{DOC_LABELS[k] || label(k)}</span>
          <div className="bar"><div style={{ width: `${(v / max) * 100}%` }} /></div>
          <span className="bar-value">{v.toLocaleString()}{total ? ` (${((v / total) * 100).toFixed(0)}%)` : ""}</span>
        </div>
      ))}
    </div>
  );
}

function Dashboard() {
  const [m, setM] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api("/api/metrics").then(setM).catch((e) => setError(e.message)); }, []);

  if (error) return <div className="card"><p className="error">{error}</p></div>;
  if (!m) return <div className="card"><p className="muted">Loading...</p></div>;

  const d = m.dataset;
  const sev = m.severity_classifier.report;
  return (
    <section>
      <div className="stats">
        <Stat label="People" value={d.persons} />
        <Stat label="Documents" value={d.documents} />
        <Stat label="Name pairs" value={d.name_pairs} />
        <Stat label="Mismatches" value={d.mismatches} />
      </div>

      <div className="grid2">
        <div className="card">
          <h3>Name matcher</h3>
          <p className="muted small">{m.name_matcher.model} · {m.name_matcher.test_size.toLocaleString()} test pairs</p>
          <p className="big-number">{pct(m.name_matcher.accuracy)}</p>
          <h4>Feature importance</h4>
          <Bars data={m.name_matcher.feature_importance} />
        </div>
        <div className="card">
          <h3>Severity classifier</h3>
          <p className="muted small">{m.severity_classifier.model} · {m.severity_classifier.test_size.toLocaleString()} test mismatches</p>
          <p className="big-number">{pct(m.severity_classifier.accuracy)}</p>
          <h4>Per-class results</h4>
          <table>
            <thead><tr><th>Class</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead>
            <tbody>
              {["acceptable", "risky", "critical"].map((c) => (
                <tr key={c}>
                  <td><span className={`badge ${c}`}>{c}</span></td>
                  <td>{sev[c].precision.toFixed(2)}</td>
                  <td>{sev[c].recall.toFixed(2)}</td>
                  <td>{sev[c]["f1-score"].toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid2">
        <div className="card"><h3>Documents by type</h3><Bars data={d.doc_types} /></div>
        <div className="card"><h3>Verification status of people</h3><Bars data={d.verification_status} total={d.persons} /></div>
        <div className="card"><h3>Mismatch severity</h3><Bars data={d.severity} total={d.mismatches} /></div>
        <div className="card"><h3>Mismatch types</h3><Bars data={d.mismatch_types} /></div>
      </div>
    </section>
  );
}

function Stat({ label: text, value }) {
  return (
    <div className="card stat">
      <span className="muted small">{text}</span>
      <b>{value.toLocaleString()}</b>
    </div>
  );
}