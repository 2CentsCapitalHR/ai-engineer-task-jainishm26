# rag.py
from __future__ import annotations

import re
import time
import shutil
from pathlib import Path
from typing import List
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings  # <-- use proper Embeddings object

# -----------------------------
# Config
# -----------------------------
_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_DB_DIR = Path("data/.chroma")
_REF_DIR = Path("data/reference")

# Inline reference URLs
REFERENCE_URLS: List[str] = [
    # Checklists (PDF)
    "https://www.adgm.com/documents/registration-authority/registration-and-incorporation/checklist/branch-non-financial-services-20231228.pdf",
    "https://www.adgm.com/documents/registration-authority/registration-and-incorporation/checklist/private-company-limited-by-guarantee-non-financial-services-20231228.pdf",

    # Data Protection (PDF)
    "https://www.adgm.com/documents/office-of-data-protection/templates/adgm-dpr-2021-appropriate-policy-document.pdf",

    # Templates (DOCX)
    "https://assets.adgm.com/download/assets/ADGM+Standard+Employment+Contract+Template+-+ER+2024+(Feb+2025).docx/ee14b252edbe11efa63b12b3a30e5e3a",
    "https://assets.adgm.com/download/assets/ADGM+Standard+Employment+Contract+-+ER+2019+-+Short+Version+(May+2024).docx/33b57a92ecfe11ef97a536cc36767ef8",
    "https://assets.adgm.com/download/assets/Templates_SHReso_AmendmentArticles-v1-20220107.docx/97120d7c5af911efae4b1e183375c0b2?forcedownload=1",
    "https://assets.adgm.com/download/assets/adgm-ra-resolution-multiple-incorporate-shareholders-LTD-incorporation-v2.docx/186a12846c3911efa4e6c6223862cd87",
]

# -----------------------------
# Helpers
# -----------------------------
def _guess_filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path
    m = re.search(r"([^/]+\.(pdf|docx))", path, flags=re.IGNORECASE)
    if m:
        base = m.group(1)
    else:
        base = Path(path).name or "adgm_ref"

    lower = url.lower()
    if not base.lower().endswith((".pdf", ".docx")):
        if ".pdf" in lower:
            base += ".pdf"
        elif ".docx" in lower:
            base += ".docx"

    base = re.sub(r"[^A-Za-z0-9._+-]", "_", base)
    return base


def _download_with_headers(url: str, dest: Path, retries: int = 3, backoff: float = 1.5):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Referer": "https://www.adgm.com/",
        "Accept-Language": "en-US,en;q=0.9",
    }
    last_err = None
    for i in range(retries):
        try:
            req = Request(url, headers=headers, method="GET")
            with urlopen(req, timeout=30) as r, open(dest, "wb") as f:
                shutil.copyfileobj(r, f)
            if dest.stat().st_size == 0:
                raise IOError("Downloaded zero bytes")
            return
        except (HTTPError, URLError, IOError) as e:
            last_err = e
            time.sleep(backoff ** i)
    raise last_err


def _download_if_needed(urls: List[str], outdir: Path) -> List[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    for url in urls:
        name = _guess_filename_from_url(url)
        dest = outdir / name
        if not dest.exists() or dest.stat().st_size == 0:
            print(f"[RAG] Downloading: {url} -> {dest}")
            _download_with_headers(url, dest)
        else:
            print(f"[RAG] Using cached: {dest}")
        paths.append(dest)
    return paths


def _load_reference_docs(ref_paths: List[Path]):
    docs = []
    for p in ref_paths:
        try:
            if p.suffix.lower() == ".pdf":
                docs.extend(PyPDFLoader(str(p)).load())
            elif p.suffix.lower() == ".docx":
                docs.extend(Docx2txtLoader(str(p)).load())
            else:
                print(f"[RAG] Skipping unsupported file type: {p}")
        except Exception as e:
            print(f"[RAG] Failed to load {p}: {e}")
    return docs


def _split_docs(docs):
    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)
    return splitter.split_documents(docs)


def _get_embeddings():
    # Proper LangChain Embeddings object (fixes the '_type' issue)
    return HuggingFaceEmbeddings(model_name=_EMBED_MODEL_NAME)

# -----------------------------
# Public API
# -----------------------------
def build_or_load_vectorstore(force_rebuild: bool = False):
    """
    Returns a LangChain Retriever over a Chroma vector store.
    - Downloads ADGM references (cached to data/reference/)
    - Builds a persistent Chroma index in data/.chroma on first run
    - Reuses the index on subsequent runs unless force_rebuild=True
    """
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    embeddings = _get_embeddings()  # <-- create once

    if not force_rebuild:
        try:
            # IMPORTANT: pass the same embeddings when loading
            vs = Chroma(persist_directory=str(_DB_DIR), embedding_function=embeddings)
            _ = vs.similarity_search("ADGM", k=1)  # smoke test
            print("[RAG] Loaded existing Chroma index.")
            return vs.as_retriever(search_kwargs={"k": 4})
        except Exception as e:
            print(f"[RAG] No usable index found. Rebuilding... ({type(e).__name__}: {e})")

    # Download / cache reference files
    ref_paths = _download_if_needed(REFERENCE_URLS, _REF_DIR)

    if not any(p.exists() and p.stat().st_size > 0 for p in ref_paths):
        raise RuntimeError(
            "No reference documents available. "
            "Place ADGM PDFs/DOCXs into data/reference/ and retry."
        )

    # Load & split
    raw_docs = _load_reference_docs(ref_paths)
    if not raw_docs:
        raise RuntimeError("Reference documents could not be loaded. Check files/URLs.")

    chunks = _split_docs(raw_docs)

    # Build & persist with embeddings
    print("[RAG] Computing embeddings and building index...")
    vs = Chroma.from_texts(
        texts=[c.page_content for c in chunks],
        embedding=embeddings,  # <-- pass Embeddings object here too
        metadatas=[c.metadata for c in chunks],
        persist_directory=str(_DB_DIR),
    )
    vs.persist()
    print("[RAG] Chroma index built and persisted.")
    return vs.as_retriever(search_kwargs={"k": 4})


if __name__ == "__main__":
    retriever = build_or_load_vectorstore(force_rebuild=False)
    hits = retriever.get_relevant_documents("ADGM jurisdiction clause Companies Regulations")
    print(f"Retrieved {len(hits)} chunks.")
    if hits:
        print(hits[0].page_content[:300], "...\n", hits[0].metadata)
