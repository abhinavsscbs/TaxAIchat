const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function handleJson(res) {
  if (!res.ok) {
    let msg = "Request failed";
    try {
      const data = await res.json();
      msg = data.error || msg;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }
  return res.json();
}

export async function getHealth() {
  return handleJson(await fetch(`${API_BASE}/health`));
}

export async function getTaxAreas() {
  return handleJson(await fetch(`${API_BASE}/tax-areas`));
}

export async function addTaxArea(area) {
  return handleJson(
    await fetch(`${API_BASE}/tax-areas`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ area })
    })
  );
}

export async function listDocs() {
  return handleJson(await fetch(`${API_BASE}/docs`));
}

export async function addDoc({ docId, taxArea, customArea, file }) {
  const fd = new FormData();
  fd.append("doc_id", docId);
  fd.append("tax_area", taxArea || "");
  fd.append("custom_area", customArea || "");
  fd.append("file", file);
  return handleJson(
    await fetch(`${API_BASE}/docs/add`, {
      method: "POST",
      body: fd
    })
  );
}

export async function replaceDoc({ docId, file }) {
  const fd = new FormData();
  fd.append("doc_id", docId);
  fd.append("file", file);
  return handleJson(
    await fetch(`${API_BASE}/docs/replace`, {
      method: "POST",
      body: fd
    })
  );
}

export async function deleteDoc(docId) {
  return handleJson(
    await fetch(`${API_BASE}/docs/${encodeURIComponent(docId)}`, {
      method: "DELETE"
    })
  );
}

export async function chat({ query, selectedDocIds, selectedAreas, translate }) {
  return handleJson(
    await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        selected_doc_ids: selectedDocIds,
        selected_areas: selectedAreas,
        translate
      })
    })
  );
}
