import os
from pathlib import Path

# Base directory for relative paths
BASE_DIR = Path(__file__).resolve().parent

# Cohere (internal endpoint)
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
COHERE_ENDPOINT_URL = os.getenv("COHERE_ENDPOINT_URL", "https://cohere.internal/chat")
COHERE_VERIFY_SSL = os.getenv("COHERE_VERIFY_SSL", "true").lower() == "true"
COHERE_REQUEST_TIMEOUT_SEC = int(os.getenv("COHERE_REQUEST_TIMEOUT_SEC", "30"))

# Models
EMBEDDINGS_MODEL_PATH = os.getenv("EMBEDDINGS_MODEL_PATH", "/path/to/local/embedding-model")
CHAT_MODEL = os.getenv("CHAT_MODEL", "")

# Paths (override via env if needed)
INDEX_DIR = Path(os.getenv("INDEX_DIR", BASE_DIR / "All embeddings"))
TAX_AREA_FILE = Path(os.getenv("TAX_AREA_FILE", BASE_DIR / "tax_areas.txt"))
REPLACEMENT_XLSX = Path(
    os.getenv("REPLACEMENT_XLSX", BASE_DIR / "IFRS_Word_Replacement.xlsx")
)

# OCR
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")

# App
DEFAULT_TAX_AREAS = [
    "Corporate Income Tax",
    "Customs",
    "E-invoicing",
    "Excise Tax",
    "Transfer Pricing",
    "VAT",
    "Zakat",
]
INVALID_IDS = {None, "Unknown"}
