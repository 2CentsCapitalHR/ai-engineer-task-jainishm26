# rag.py
from __future__ import annotations

import re
from pathlib import Path
from typing import List
from urllib.parse import urlparse
from urllib.request import urlretrieve

from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

# -----------------------------
# Config
# -----------------------------
_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_DB_DIR = Path("data/.chroma")
_REF_DIR = Path("data/reference")


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
    """
    Build a stable local filename from an ADGM URL.
    Many ADGM links end with a UUID; we try to capture the first *.pdf or *.docx
    occurrence in the path, otherwise fall back to the last path segment.
    """
    parsed = urlparse(url)
    path = parsed.path

    # extracting first occurrence of a real file name with extension
    m = re.search(r"([^/]+\.(pdf|docx))", path, flags=re.IGNORECASE)
    if m:
        base = m.group(1)
    else:
        base = Path(path).name or "adgm_ref"

    # If no extension is visible, infer from URL text
    lower = url.lower()
    if not base.lower().endswith((".pdf", ".docx")):
        if ".pdf" in lower:
            base += ".pdf"
        elif ".docx" in lower:
            base += ".docx"

    # Sanitize
    base = re.sub(r"[^A-Za-z0-9._+-]", "_", base)
    return base


def _download_if_needed(urls: List[str], outdir: Path) -> List[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    for url in urls:
        name = _guess_filename_from_url(url)
        dest = outdir / name
        if not dest.exists() or dest.stat().st_size == 0:
            print(f"[RAG] Downloading: {url} -> {dest}")
            urlretrieve(url, dest)
        else:
            print(f"[RAG] Using cached: {dest}")
        paths.append(dest)
    return paths


def _load_reference_docs(ref_paths: List[Path]):
    docs = []
    for p in ref_paths:
        suffix = p.suffix.lower()
        try:
            if suffix == ".pdf":
                docs.extend(PyPDFLoader(str(p)).load())
            elif suffix == ".docx":
                docs.extend(Docx2txtLoader(str(p)).load())
            else:
                print(f"[RAG] Skipping unsupported file type: {p}")
        except Exception as e:
            print(f"[RAG] Failed to load {p}: {e}")
    return docs


def _split_docs(docs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=150
    )
    return splitter.split_documents(docs)


# -----------------------------
# Public API
# -----------------------------
def build_or_load_vectorstore(force_rebuild: bool = False):
    """
    Returns a LangChain Retriever over a Chroma vector store.
    - Downloads ADGM references from REFERENCE_URLS (cached in data/reference/)
    - Builds a persistent Chroma index in data/.chroma on first run
    - Reuses the index on subsequent runs unless force_rebuild=True
    """
    _DB_DIR.mkdir(parents=True, exist_ok=True)

    if not force_rebuild:
        try:
            vs = Chroma(persist_directory=str(_DB_DIR))
            # Smoke test
            _ = vs.similarity_search("ADGM", k=1)
            print("[RAG] Loaded existing Chroma index.")
            return vs.as_retriever(search_kwargs={"k": 4})
        except Exception:
            print("[RAG] No usable index found. Building a new one...")

    # Ensure local cache of reference files
    ref_paths = _download_if_needed(REFERENCE_URLS, _REF_DIR)

    # Load & split
    raw_docs = _load_reference_docs(ref_paths)
    if not raw_docs:
        raise RuntimeError("No reference documents could be loaded. Check URLs and network connectivity.")
    chunks = _split_docs(raw_docs)

    # Embeddings
    print("[RAG] Computing embeddings...")
    embedder = SentenceTransformer(_EMBED_MODEL_NAME)

    # Small wrapper because Chroma.from_texts expects a callable that returns a list of vectors
    def _embed(batch_texts: List[str]):
        return embedder.encode(batch_texts, convert_to_numpy=True).tolist()

    # Build & persist vector store
    vs = Chroma.from_texts(
        texts=[c.page_content for c in chunks],
        embedding=_embed,
        metadatas=[c.metadata for c in chunks],
        persist_directory=str(_DB_DIR),
    )
    vs.persist()
    print("[RAG] Chroma index built and persisted.")
    return vs.as_retriever(search_kwargs={"k": 4})


# -----------------------------
# Manual test
# -----------------------------
if __name__ == "__main__":
    retriever = build_or_load_vectorstore(force_rebuild=False)
    hits = retriever.get_relevant_documents("ADGM jurisdiction clause Companies Regulations")
    print(f"Retrieved {len(hits)} chunks. Example snippet:")
    if hits:
        print(hits[0].page_content[:300], "...\n", hits[0].metadata)
