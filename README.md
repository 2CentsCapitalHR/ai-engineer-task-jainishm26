[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/vgbm4cZ0)
# ADGM Corporate Agent – Document Intelligence (Jainish Malhotra's submission)

An AI assistant that reviews `.docx` legal documents for **ADGM** processes, checks completeness against official **ADGM checklists**, flags red flags, inserts **inline Word comments**, and exports a **JSON report**. Built with **Streamlit** + **RAG** (Chroma + Sentence-Transformers).

## Features
- Upload `.docx` (Articles, MoA, UBO, Resolutions, etc.)
- Auto-detect process (Company Incorporation, etc.)
- Verify against **ADGM** required-document checklist
- Red-flag detection (jurisdiction, ambiguous language, missing signatory blocks)
- Inline comments in `.docx` (OOXML; safe highlight fallback)
- JSON summary export
- Pluggable RAG retriever over official ADGM PDFs

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

streamlit run app.py
