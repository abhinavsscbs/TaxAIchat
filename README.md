# TaxAIchat

Tax document assistant for VAT, Zakat, corporate income tax, and related topics. A Flask backend ingests PDFs, stores document embeddings in FAISS, and uses a configurable Cohere chat endpoint. A React/Vite frontend provides the interface.

## Features

- Add, replace, list, and delete indexed documents.
- Classify documents by tax area and maintain custom tax areas.
- Extract PDF text and use Tesseract OCR for scanned documents.
- Translate Arabic/English content and chat over selected documents.

## Layout

| Path | Purpose |
| --- | --- |
| `main_app.py` | Flask backend and document/chat workflows |
| `config.py` | Environment-driven runtime configuration |
| `frontend/` | React/Vite interface |
| `All embeddings/` | Stored FAISS artifacts |
| `IFRS_Word_Replacement.xlsx` | Terminology replacements |
| `tax_areas.txt` | Custom tax areas |

## Setup

```bash
git clone https://github.com/abhinavsscbs/TaxAIchat.git
cd TaxAIchat
python -m venv .venv
# Activate .venv before continuing.
python -m pip install -r requirements.txt
```

Install Tesseract separately, including English and Arabic language data for OCR.

Set these environment variables before starting:

| Variable | Purpose |
| --- | --- |
| `COHERE_API_KEY` | Required chat-service credential |
| `COHERE_ENDPOINT_URL` | Reachable, compatible chat endpoint |
| `EMBEDDINGS_MODEL_PATH` | Local SentenceTransformer model |
| `TESSERACT_CMD` | Optional Tesseract executable path |
| `INDEX_DIR` | Optional FAISS storage override |
| `REPLACEMENT_XLSX` | Optional replacement workbook override |

The model and endpoint defaults are placeholders and must be configured.

```bash
python main_app.py
```

The API runs on port `8000`. The frontend uses `http://localhost:8000` by default; set `VITE_API_BASE` to change it.

In a separate terminal, start the React UI:

```bash
cd frontend
npm install
npm run dev
```

Create a production UI build with `npm run build`.

