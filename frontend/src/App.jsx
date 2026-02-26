import React, { useEffect, useMemo, useState } from "react";
import {
  addDoc,
  addTaxArea,
  chat,
  deleteDoc,
  getTaxAreas,
  listDocs,
  replaceDoc
} from "./api.js";

const NAV_PAGES = ["Tax AI Chat", "Document Managing Dashboard"];

function useAsync(fn, deps = []) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  useEffect(() => {
    let alive = true;
    setState({ loading: true, data: null, error: null });
    fn()
      .then((data) => alive && setState({ loading: false, data, error: null }))
      .catch((error) => alive && setState({ loading: false, data: null, error }));
    return () => {
      alive = false;
    };
  }, deps);
  return state;
}

export default function App() {
  const [page, setPage] = useState(NAV_PAGES[0]);
  const [refreshKey, setRefreshKey] = useState(0);

  const taxAreasState = useAsync(getTaxAreas, [refreshKey]);
  const docsState = useAsync(listDocs, [refreshKey]);

  const taxAreas = taxAreasState.data?.areas || [];
  const documents = docsState.data?.documents || {};

  const docEntries = useMemo(() => Object.entries(documents), [documents]);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-title">Tax Digital Co-worker</div>
        </div>
        <div className="nav">
          {NAV_PAGES.map((p) => (
            <button
              key={p}
              className={p === page ? "nav-btn active" : "nav-btn"}
              onClick={() => setPage(p)}
            >
              {p}
            </button>
          ))}
        </div>
      </aside>
      <main className="main">
        {page === "Document Managing Dashboard" ? (
          <DocumentDashboard
            taxAreas={taxAreas}
            documents={documents}
            onRefresh={() => setRefreshKey((k) => k + 1)}
          />
        ) : (
          <TaxChat
            taxAreas={taxAreas}
            documents={documents}
            onRefresh={() => setRefreshKey((k) => k + 1)}
          />
        )}
      </main>
    </div>
  );
}

function DocumentDashboard({ taxAreas, documents, onRefresh }) {
  const [action, setAction] = useState("Add File");
  const [docId, setDocId] = useState("");
  const [taxArea, setTaxArea] = useState("");
  const [customArea, setCustomArea] = useState("");
  const [file, setFile] = useState(null);
  const [replaceId, setReplaceId] = useState("");
  const [removeId, setRemoveId] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const docIds = Object.keys(documents);

  useEffect(() => {
    if (!replaceId && docIds.length) setReplaceId(docIds[0]);
    if (!removeId && docIds.length) setRemoveId(docIds[0]);
  }, [docIds, replaceId, removeId]);

  async function handleAdd() {
    if (!docId || !file) return setStatus("Document name/ID and PDF are required.");
    setBusy(true);
    setStatus("Processing document...");
    try {
      const res = await addDoc({
        docId,
        taxArea,
        customArea,
        file
      });
      setStatus(`Added ${res.doc_id}.`);
      setDocId("");
      setTaxArea("");
      setCustomArea("");
      setFile(null);
      onRefresh();
    } catch (err) {
      setStatus(err.message || "Failed to add document.");
    } finally {
      setBusy(false);
    }
  }

  async function handleReplace() {
    if (!replaceId || !file) return setStatus("Document ID and PDF are required.");
    setBusy(true);
    setStatus("Replacing document...");
    try {
      await replaceDoc({ docId: replaceId, file });
      setStatus(`Replaced ${replaceId}.`);
      setFile(null);
      onRefresh();
    } catch (err) {
      setStatus(err.message || "Failed to replace document.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove() {
    if (!removeId) return setStatus("Select a document to remove.");
    setBusy(true);
    setStatus("Removing document...");
    try {
      await deleteDoc(removeId);
      setStatus(`Removed ${removeId}.`);
      onRefresh();
    } catch (err) {
      setStatus(err.message || "Failed to remove document.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <header className="panel-header">
        <h1>Document Managing Dashboard</h1>
        <p>Manage the document database used by the Tax AI Chat.</p>
      </header>

      <div className="segmented">
        {["Add File", "Replace", "Remove"].map((a) => (
          <button
            key={a}
            className={a === action ? "seg-btn active" : "seg-btn"}
            onClick={() => setAction(a)}
          >
            {a}
          </button>
        ))}
      </div>

      <div className="card">
        {action === "Add File" && (
          <>
            <div className="field">
              <label>Document name/ID</label>
              <input value={docId} onChange={(e) => setDocId(e.target.value)} />
            </div>
            <div className="field">
              <label>Select area of tax</label>
              <select value={taxArea} onChange={(e) => setTaxArea(e.target.value)}>
                <option value="">Select…</option>
                {taxAreas.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
                <option value="Other">Other</option>
              </select>
            </div>
            {taxArea === "Other" && (
              <div className="field">
                <label>Enter new tax area name</label>
                <input value={customArea} onChange={(e) => setCustomArea(e.target.value)} />
              </div>
            )}
            <div className="field">
              <label>Upload PDF</label>
              <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files[0] || null)} />
            </div>
            <button className="primary" disabled={busy} onClick={handleAdd}>
              Add document to database
            </button>
          </>
        )}

        {action === "Replace" && (
          <>
            <div className="field">
              <label>Choose document to replace</label>
              <select value={replaceId} onChange={(e) => setReplaceId(e.target.value)}>
                {docIds.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </div>
            {replaceId && documents[replaceId] && (
              <div className="info-box">
                <div className="info-title">Current summary</div>
                <div>{documents[replaceId].description}</div>
              </div>
            )}
            <div className="field">
              <label>Upload new PDF</label>
              <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files[0] || null)} />
            </div>
            <button className="primary" disabled={busy} onClick={handleReplace}>
              Replace document
            </button>
          </>
        )}

        {action === "Remove" && (
          <>
            <div className="field">
              <label>Choose document to delete</label>
              <select value={removeId} onChange={(e) => setRemoveId(e.target.value)}>
                {docIds.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </div>
            {removeId && documents[removeId] && (
              <div className="info-box">
                <div className="info-title">Details</div>
                <div>{documents[removeId].description}</div>
                <div className="muted">Area: {documents[removeId].tax_area}</div>
              </div>
            )}
            <button className="danger" disabled={busy} onClick={handleRemove}>
              Remove document
            </button>
          </>
        )}
      </div>

      {status && <div className="status">{status}</div>}
    </section>
  );
}

function TaxChat({ taxAreas, documents }) {
  const [query, setQuery] = useState("");
  const [selectedAreas, setSelectedAreas] = useState([]);
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [selectAll, setSelectAll] = useState(false);
  const [selectAreaAll, setSelectAreaAll] = useState(false);
  const [translate, setTranslate] = useState(false);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  const docEntries = Object.entries(documents);
  const areaOptions = Array.from(
    new Set(docEntries.map(([, v]) => v.tax_area || "Unclassified"))
  ).sort();

  const areaFilteredDocIds = docEntries
    .filter(([, v]) => (selectedAreas.length ? selectedAreas.includes(v.tax_area) : true))
    .map(([k]) => k);

  useEffect(() => {
    if (selectAll) {
      setSelectedDocs(docEntries.map(([k]) => k));
    }
  }, [selectAll, docEntries]);

  useEffect(() => {
    if (selectAreaAll) {
      setSelectedDocs(areaFilteredDocIds);
    }
  }, [selectAreaAll, areaFilteredDocIds]);

  async function handleAsk(mode) {
    if (!query.trim()) return;
    setBusy(true);
    setStatus("Thinking...");
    try {
      const res = await chat({
        query,
        selectedDocIds: selectedDocs,
        selectedAreas,
        translate: mode === "ar" ? "ar" : null
      });
      setHistory((h) => [
        {
          user: mode === "followup" && h.length ? `${h[0].user} ${query}` : query,
          answer: res.answer,
          sources: res.sources
        },
        ...h
      ]);
      setQuery("");
      setStatus("");
    } catch (err) {
      setStatus(err.message || "Failed to get answer.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <header className="panel-header">
        <h1>Tax AI Chat</h1>
        <p>Ask questions across the document database.</p>
      </header>

      <div className="filters">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={selectAll}
            onChange={(e) => {
              setSelectAll(e.target.checked);
              if (!e.target.checked) setSelectedDocs([]);
            }}
          />
          Select all documents in the database
        </label>

        {!selectAll && (
          <>
            <div className="field">
              <label>Select Area(s) of Tax</label>
              <select
                multiple
                value={selectedAreas}
                onChange={(e) =>
                  setSelectedAreas(Array.from(e.target.selectedOptions).map((o) => o.value))
                }
              >
                {areaOptions.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </div>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={selectAreaAll}
                onChange={(e) => {
                  setSelectAreaAll(e.target.checked);
                  if (!e.target.checked) setSelectedDocs([]);
                }}
              />
              Select all documents from selected Area(s)
            </label>
            <div className="field">
              <label>Choose document(s) to search from</label>
              <select
                multiple
                value={selectedDocs}
                onChange={(e) =>
                  setSelectedDocs(Array.from(e.target.selectedOptions).map((o) => o.value))
                }
              >
                {areaFilteredDocIds.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}
      </div>

      <div className="chat-box">
        <div className="field">
          <label>Ask your question</label>
          <input value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="btn-row">
          <button className="primary" disabled={busy} onClick={() => handleAsk("ask")}>
            Ask
          </button>
          <button
            className="secondary"
            disabled={busy}
            onClick={() => handleAsk("followup")}
          >
            Follow-up
          </button>
          <button className="secondary" disabled={busy} onClick={() => handleAsk("ar")}>
            Answer in Arabic
          </button>
        </div>
      </div>

      {status && <div className="status">{status}</div>}

      <div className="history">
        {history.map((h, i) => (
          <div className="history-item" key={`${h.user}-${i}`}>
            <div className="history-user">User: {h.user}</div>
            <div className="history-answer">{h.answer}</div>
            {!!h.sources?.length && (
              <div className="history-sources">
                <div className="info-title">References</div>
                {h.sources.map(([docId, desc]) => (
                  <div className="source" key={`${docId}-${desc}`}>
                    <div>Document ID: {docId}</div>
                    <div className="muted">Summary: {desc}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
