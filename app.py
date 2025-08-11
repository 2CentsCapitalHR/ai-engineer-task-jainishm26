# app.py
from pathlib import Path
import json
import tempfile
import streamlit as st

from checklist import detect_process_from_docs
from doc_processor import analyze_documents
from utils import ensure_dirs

st.set_page_config(page_title="ADGM Corporate Agent", layout="wide")

# Sidebar
with st.sidebar:
    st.header("Corporate Agent")
    st.info(
        "An AI assistant for ADGM business incorporation and compliance. "
        "Upload all documents for your submission and click 'Analyze'."
    )

st.title("ADGM Corporate Agent 😎")
st.subheader("Your AI-Powered Legal Compliance Assistant")

st.markdown("""
### 1. Upload All Documents for Your Submission
**Choose your `.docx` files** (e.g., Articles of Association, Memorandum of Association, UBO Declaration, Board/Shareholder Resolutions, Register of Members/Directors, Incorporation Application), then click **Analyze**.

The agent will:
1. Detect your process (e.g., **Company Incorporation**)
2. Check against the **ADGM** required-document checklist and list **missing documents**
3. Flag **red flags** and insert inline comments in the `.docx`
4. Export a **JSON summary**
""")

ensure_dirs()

uploads = st.file_uploader(
    "Drag and drop files here",
    type=["docx"],
    accept_multiple_files=True
)

if uploads:
    for uf in uploads:
        st.caption(f"📄 {uf.name}")

analyze = st.button("Analyze Submission")

if analyze:
    # 1) Build/load the RAG index **on demand** (so the UI always loads)
    try:
        with st.spinner("Loading legal reference index (RAG) ..."):
            from rag import build_or_load_vectorstore
            retriever = build_or_load_vectorstore()  # downloads on first run
    except Exception as e:
        st.error(
            "Could not load ADGM references automatically.\n\n"
            "If your network blocks downloads, manually place the relevant "
            "ADGM PDFs/DOCXs into `data/reference/` and click Analyze again.\n\n"
            f"Details: {e}"
        )
        st.stop()

    if not uploads:
        st.warning("Please upload at least one `.docx` file.")
        st.stop()

    # 2) Persist uploads to temp files
    with st.spinner("Analyzing documents..."):
        temp_files = []
        for uf in uploads:
            tf = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            tf.write(uf.read())
            tf.flush()
            temp_files.append((uf.name, tf.name))

        # 3) Detect process and run analysis
        process_guess = detect_process_from_docs([n for n, _ in temp_files])
        results = analyze_documents(
            uploaded_files=temp_files,
            retriever=retriever,
            process_hint=process_guess
        )

    st.success("Analysis complete ✅")

    st.subheader("Checklist Summary")
    st.json({
        "process": results["process"],
        "documents_uploaded": results["documents_uploaded"],
        "required_documents": results["required_documents"],
        "missing_documents": results["missing_documents"]
    })

    st.subheader("Issues Found (Summary)")
    st.json({"issues_found": results["issues_found"]})

    st.subheader("Downloads")
    if "reviewed_paths" in results and results["reviewed_paths"]:
        for item in results["reviewed_paths"]:
            rp = Path(item["path"])
            st.write(f"Reviewed: **{item['original_name']}** → `{rp.name}`")
            st.download_button(
                "Download reviewed .docx",
                rp.read_bytes(),
                file_name=rp.name,
                key=str(rp)
            )

    if "report_path" in results:
        rp = Path(results["report_path"])
        st.download_button("Download JSON report", rp.read_bytes(), file_name=rp.name)
