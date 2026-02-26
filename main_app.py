import os
import re
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import fitz
import requests
import pandas as pd
import pdfplumber
import pytesseract
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from langchain.docstore.document import Document
from langchain.vectorstores import FAISS
from PIL import Image

import config

if not config.COHERE_API_KEY:
    raise RuntimeError("COHERE_API_KEY is not set.")

if config.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD


@dataclass
class AppState:
    faiss_index: Optional[FAISS] = None
    descriptions: Dict[str, Dict[str, str]] = field(default_factory=dict)
    contents: Dict[str, str] = field(default_factory=dict)


STATE = AppState()

from sentence_transformers import SentenceTransformer  # noqa: E402

embedder = SentenceTransformer(config.EMBEDDINGS_MODEL_PATH)


class LocalEmbeddingsWrapper:
    def __init__(self, model: SentenceTransformer):
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts, convert_to_numpy=True).tolist()

    def embed_query(self, text: str) -> List[float]:
        return self.model.encode([text], convert_to_numpy=True)[0].tolist()


embeddings = LocalEmbeddingsWrapper(embedder)


def update_faiss_index(index_obj: Optional[FAISS]) -> None:
    STATE.faiss_index = index_obj
    if index_obj is not None:
        config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
        index_obj.save_local(str(config.INDEX_DIR))


def load_index_if_exists() -> None:
    if STATE.faiss_index is not None:
        return
    if config.INDEX_DIR.exists():
        idx = FAISS.load_local(
            str(config.INDEX_DIR),
            embeddings,
            allow_dangerous_deserialization=True,
        )
        valid = [
            Document(page_content=d.page_content, metadata=d.metadata)
            for d in idx.docstore._dict.values()
            if d.metadata.get("doc_id") not in config.INVALID_IDS
        ]
        idx = FAISS.from_documents(valid, embeddings) if len(valid) < len(idx.docstore._dict) else idx
        update_faiss_index(idx)
        rebuild_metadata_from_index()


def rebuild_metadata_from_index() -> None:
    STATE.descriptions = {}
    STATE.contents = {}
    fi = STATE.faiss_index
    if not fi:
        return
    for d in fi.docstore._dict.values():
        did = d.metadata.get("doc_id")
        if did not in config.INVALID_IDS:
            STATE.descriptions[did] = {
                "description": d.metadata.get("description", ""),
                "tax_area": d.metadata.get("tax_area", "Unclassified"),
            }
            STATE.contents[did] = d.page_content


def load_tax_areas() -> List[str]:
    areas = list(config.DEFAULT_TAX_AREAS)
    if config.TAX_AREA_FILE.exists():
        with open(config.TAX_AREA_FILE, "r", encoding="utf-8") as f:
            custom = [line.strip() for line in f if line.strip()]
            areas = sorted(list(set(areas + custom)))
    return areas


def save_tax_area(area: str) -> None:
    config.TAX_AREA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(config.TAX_AREA_FILE, "a", encoding="utf-8") as f:
        f.write(area.strip() + "\n")


def is_arabic_text(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06FF" for ch in text)


def cohere_chat(message: str, system: str, temperature: float = 0) -> str:
    try:
        payload = {
            "message": f"{system}\n\n{message}",
            "temperature": temperature,
            "max_tokens": 1000,
            "response_format": {"type": "text"},
        }
        if config.CHAT_MODEL:
            payload["model"] = config.CHAT_MODEL
        headers = {
            "Authorization": f"Bearer {config.COHERE_API_KEY}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            config.COHERE_ENDPOINT_URL,
            headers=headers,
            json=payload,
            timeout=config.COHERE_REQUEST_TIMEOUT_SEC,
            verify=config.COHERE_VERIFY_SSL,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("text", "") or ""
    except Exception:
        return ""


def translate_to_english(text: str) -> str:
    result = cohere_chat(
        text,
        (
            "You are a professional translator specialized in financial and legal documents "
            "related to Saudi Arabian VAT, Tax, and Zakat regulations. Translate the following "
            "Arabic text to English with accuracy and preserve technical terminology."
        ),
        temperature=0,
    )
    return result.strip() if result else text


def translate_to_arabic(text: str) -> str:
    result = cohere_chat(
        text,
        "Translate the following text from English to Arabic:",
        temperature=0,
    )
    return result or text


def sanitize_for_latin1(s: str) -> str:
    return s.replace("\u2026", "...")


def is_scanned_pdf(pdf_path: str, min_text_chars: int = 20) -> bool:
    doc = fitz.open(pdf_path)
    return all(len(page.get_text("text").strip()) < min_text_chars for page in doc)


def extract_text_with_ocr(pdf_path: str) -> List[Dict[str, str]]:
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img, lang="eng+ara", config="--oem 1 --psm 3")
        pages.append(text)
    full_text = " ".join(pages)
    if is_arabic_text(full_text):
        full_text = translate_to_english(full_text)
    return [{"content": full_text}]


def analyze_document(pdf_path: str) -> List[Dict[str, str]]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            txt = p.extract_text() or ""
            pages.append(re.sub(r"\s+", " ", txt).strip())
    full_text = "".join(pages)
    if is_arabic_text(full_text):
        full_text = translate_to_english(full_text)
    return [{"content": full_text}] if full_text else []


def text_to_table(text: str) -> str:
    prompt = f"Summarize into one paragraph (≤200 words):\n\n{text}"
    result = cohere_chat(prompt, "You are helpful.", temperature=0.3)
    return result.strip()


def replace_keywords(text: str) -> str:
    df = pd.read_excel(
        str(config.REPLACEMENT_XLSX),
        sheet_name="Arabic" if is_arabic_text(text) else "English",
    )
    repl = pd.Series(df["Replacement"].values, index=df["Word"].str.lower()).to_dict()
    pattern = re.compile("|".join(re.escape(k) for k in repl.keys()), re.IGNORECASE)
    return pattern.sub(lambda m: repl[m.group().lower()], text)


def emphasize_headers(text: str) -> str:
    lines = text.split("\n")
    return "\n".join(
        f"**{l}**" if re.match(r".+:$", l) and not l.strip().startswith("**") else l for l in lines
    )


def load_retriever(k: int = 3, selected_ids: Optional[List[str]] = None):
    load_index_if_exists()
    if STATE.faiss_index is None:
        raise RuntimeError("FAISS index not found. Please add a document first.")

    if not selected_ids or set(selected_ids) == set(STATE.descriptions.keys()):
        return STATE.faiss_index.as_retriever(
            search_type="similarity", search_kwargs={"k": k, "fetch_k": 20}
        )

    filtered_docs = [
        Document(
            page_content=STATE.contents[did],
            metadata={
                "doc_id": did,
                "description": STATE.descriptions[did],
                "tax_area": STATE.descriptions[did].get("tax_area", "Unclassified"),
            },
        )
        for did in selected_ids
        if did in STATE.contents
    ]
    if not filtered_docs:
        raise RuntimeError("No documents match the selected filters.")

    filtered_index = FAISS.from_documents(filtered_docs, embeddings)
    return filtered_index.as_retriever(search_type="similarity", search_kwargs={"k": k, "fetch_k": 20})


def conversational_chat(user_input: str, selected_ids: List[str]) -> Tuple[str, List[Tuple[str, str]]]:
    retriever = load_retriever(selected_ids=selected_ids)
    docs = retriever.get_relevant_documents(user_input)
    context = "\n\n".join(
        f"[{d.metadata.get('doc_id', 'Unknown')}] {d.page_content}" for d in docs
    )
    system = (
        "You are a tax policy assistant. Use the provided context to answer. "
        "Always begin with an introduction and end with a conclusion. "
        "Give a very detailed bullet-point answer. "
        "Mention the Article Number and the Document name in brackets with header."
    )
    message = f"Context:\n{context}\n\nQuestion:\n{user_input}"
    text = cohere_chat(message, system, temperature=0)
    meta = [
        (d.metadata.get("doc_id", "Unknown"), d.metadata.get("description", ""))
        for d in docs
    ]
    return text, meta


def init_app_state() -> None:
    load_index_if_exists()
    if STATE.faiss_index is None:
        STATE.descriptions = {}
        STATE.contents = {}


FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
app = Flask(__name__, static_folder=str(FRONTEND_DIST), static_url_path="/")
CORS(app)
init_app_state()


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/")
def index():
    if FRONTEND_DIST.exists():
        return send_from_directory(str(FRONTEND_DIST), "index.html")
    return jsonify({"error": "Frontend not built. Run `npm run build` in frontend/."}), 501


@app.get("/assets/<path:filename>")
def assets(filename: str):
    if FRONTEND_DIST.exists():
        return send_from_directory(str(FRONTEND_DIST / "assets"), filename)
    return jsonify({"error": "Frontend not built. Run `npm run build` in frontend/."}), 501


@app.get("/tax-areas")
def get_tax_areas():
    return jsonify({"areas": load_tax_areas()})


@app.post("/tax-areas")
def add_tax_area():
    payload = request.get_json(silent=True) or {}
    area = (payload.get("area") or "").strip()
    if not area:
        return jsonify({"error": "area is required"}), 400
    save_tax_area(area)
    return jsonify({"ok": True, "area": area})


@app.get("/docs")
def list_docs():
    return jsonify({"documents": STATE.descriptions})


@app.post("/docs/add")
def add_doc():
    doc_id = (request.form.get("doc_id") or "").strip()
    tax_area = (request.form.get("tax_area") or "").strip()
    custom_area = (request.form.get("custom_area") or "").strip()
    upload = request.files.get("file")

    if not upload or not doc_id:
        return jsonify({"error": "doc_id and file are required"}), 400
    if doc_id in STATE.descriptions:
        return jsonify({"error": "Document with this ID already exists"}), 409

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(upload.read())
        path = tmp.name

    data = extract_text_with_ocr(path) if is_scanned_pdf(path) else analyze_document(path)
    if not data:
        return jsonify({"error": "Could not extract text from document"}), 422

    full_text = data[0]["content"]
    summary = sanitize_for_latin1(text_to_table(full_text))
    final_area = custom_area if tax_area == "Other" and custom_area else tax_area or "Unclassified"
    if tax_area == "Other" and custom_area:
        save_tax_area(custom_area)

    doc = Document(
        page_content=full_text,
        metadata={"doc_id": doc_id, "description": summary, "tax_area": final_area},
    )

    fi = STATE.faiss_index
    if fi is None:
        update_faiss_index(FAISS.from_documents([doc], embeddings))
    else:
        fi.add_documents([doc])
        update_faiss_index(fi)

    STATE.descriptions[doc_id] = {"description": summary, "tax_area": final_area}
    STATE.contents[doc_id] = full_text

    return jsonify({"ok": True, "doc_id": doc_id, "summary": summary, "tax_area": final_area})


@app.post("/docs/replace")
def replace_doc():
    doc_id = (request.form.get("doc_id") or "").strip()
    upload = request.files.get("file")
    if not upload or not doc_id:
        return jsonify({"error": "doc_id and file are required"}), 400
    if doc_id not in STATE.descriptions:
        return jsonify({"error": "Document not found"}), 404

    existing_area = STATE.descriptions.get(doc_id, {}).get("tax_area", "Unclassified")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(upload.read())
        path = tmp.name

    data = extract_text_with_ocr(path) if is_scanned_pdf(path) else analyze_document(path)
    if not data:
        return jsonify({"error": "Could not extract text from document"}), 422

    new_desc = sanitize_for_latin1(text_to_table(data[0]["content"]))
    descs, conts = STATE.descriptions, STATE.contents
    descs.pop(doc_id, None)
    conts.pop(doc_id, None)
    rem = [
        Document(
            page_content=conts[k],
            metadata={
                "doc_id": k,
                "description": descs[k]["description"],
                "tax_area": descs[k].get("tax_area", "Unclassified"),
            },
        )
        for k in descs
    ]
    update_faiss_index(FAISS.from_documents(rem, embeddings) if rem else None)

    new_doc = Document(
        page_content=data[0]["content"],
        metadata={
            "doc_id": doc_id,
            "description": new_desc,
            "tax_area": existing_area,
        },
    )
    if STATE.faiss_index is None:
        update_faiss_index(FAISS.from_documents([new_doc], embeddings))
    else:
        STATE.faiss_index.add_documents([new_doc])
        update_faiss_index(STATE.faiss_index)

    STATE.descriptions[doc_id] = {"description": new_desc, "tax_area": existing_area}
    STATE.contents[doc_id] = data[0]["content"]

    return jsonify({"ok": True, "doc_id": doc_id, "summary": new_desc})


@app.delete("/docs/<doc_id>")
def delete_doc(doc_id: str):
    if doc_id not in STATE.descriptions:
        return jsonify({"error": "Document not found"}), 404
    descs = STATE.descriptions
    conts = STATE.contents
    descs.pop(doc_id, None)
    conts.pop(doc_id, None)
    rem = [
        Document(
            page_content=conts[k],
            metadata={
                "doc_id": k,
                "description": descs[k]["description"],
                "tax_area": descs[k].get("tax_area", "Unclassified"),
            },
        )
        for k in descs
    ]
    update_faiss_index(FAISS.from_documents(rem, embeddings) if rem else None)
    STATE.descriptions = descs
    STATE.contents = conts
    return jsonify({"ok": True, "doc_id": doc_id})


@app.post("/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    user_input = (payload.get("query") or "").strip()
    if not user_input:
        return jsonify({"error": "query is required"}), 400

    selected_doc_ids = payload.get("selected_doc_ids") or []
    selected_areas = payload.get("selected_areas") or []
    translate = payload.get("translate")  # "ar" or None

    if selected_areas and not selected_doc_ids:
        selected_doc_ids = [
            k for k, v in STATE.descriptions.items() if v.get("tax_area") in selected_areas
        ]

    try:
        resp, meta = conversational_chat(user_input, selected_doc_ids)
        resp = replace_keywords(resp)
        resp = emphasize_headers(resp)
        if translate == "ar":
            resp = translate_to_arabic(resp)
        return jsonify({"answer": resp, "sources": meta})
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 422


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
