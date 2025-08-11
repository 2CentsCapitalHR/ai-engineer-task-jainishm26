import streamlit as st
from pathlib import Path
import json
import tempfile
from doc_processor import analyze_documents
from rag import build_or_load_vectorstore
from checklist import detect_process_from_docs, REQUIRED_DOCS
from utils import ensure_dirs

st.set_page_config(page_title="ADGM Corporate Agent", layout="wide")

st.title("ADGM-Compliant Corporate Agent (Document Intelligence)")

st.markdown("""
Upload your **.docx** files (Articles, MoA, Resolutions, UBO, etc.).  
The app will:
1) Detect the process (e.g., Company Incorporation)  
2) Check against ADGM checklist  
3) Flag red flags and insert inline comments in the `.docx`  
4) Export a JSON summary  
""")

ensure_dirs()

# Build/load RAG index (vectorstore) once
with st.spinner("Loading legal reference index (RAG) ..."):
    retriever = build_or_load_vectorstore()

uploads = st.file_uploader("Upload one or more .docx files", type=["docx"], accept_multiple_files=True)

run = st.button("Analyze")

if run and uploads:
    with st.spinner("Analyzing documents..."):
        # Save uploads to temp files
        temp_files = []
        for uf in uploads:
            suffix = ".docx"
            tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tf.write(uf.read())
            tf.flush()
            temp_files.append((uf.name, tf.name))

        process_guess = detect_process_from_docs([n for n, _ in temp_files])

        results = analyze_documents(
            uploaded_files=temp_files,
            retriever=retriever,
            process_hint=process_guess
        )

    st.success("Analysis complete.")
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
    if "reviewed_paths" in results:
        for item in results["reviewed_paths"]:
            rp = Path(item["path"])
            st.write(f"Reviewed: **{item['original_name']}** → `{rp.name}`")
            st.download_button("Download reviewed .docx", rp.read_bytes(), file_name=rp.name, key=rp.name)

    if "report_path" in results:
        rp = Path(results["report_path"])
        st.download_button("Download JSON report", rp.read_bytes(), file_name=rp.name)

elif run and not uploads:
    st.warning("Please upload at least one .docx file.")

