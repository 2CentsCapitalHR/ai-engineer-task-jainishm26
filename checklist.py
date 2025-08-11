from typing import List, Dict

# Minimal mapping
REQUIRED_DOCS: Dict[str, List[str]] = {
    "Company Incorporation": [
        "Articles of Association",
        "Memorandum of Association",
        "Board Resolution",
        "Shareholder Resolution",
        "UBO Declaration Form",
        "Register of Members and Directors",
        "Incorporation Application Form"
    ],
    
    "Employment & HR": [
        "Employment Contract",
        "Offer Letter",
        "Employee Handbook"
    ],
}

# Naive detection from filenames
def detect_process_from_docs(filenames: List[str]) -> str:
    joined = " ".join([fn.lower() for fn in filenames])
    if any(k in joined for k in ["incorporation", "articles", "memorandum", "ubo", "register"]):
        return "Company Incorporation"
    if any(k in joined for k in ["employment", "contract", "hr"]):
        return "Employment & HR"
    # default
    return "Company Incorporation"

# Naive doc-type classifier 
DOC_TYPE_KEYWORDS = {
    "Articles of Association": ["articles of association", "aoa"],
    "Memorandum of Association": ["memorandum of association", "moa", "mou"],
    "Board Resolution": ["board resolution"],
    "Shareholder Resolution": ["shareholder resolution"],
    "UBO Declaration Form": ["ubo", "ultimate beneficial owner"],
    "Register of Members and Directors": ["register of members", "register of directors"],
    "Incorporation Application Form": ["incorporation application", "application form"],
    "Employment Contract": ["employment contract", "standard employment contract"]
}

def classify_doc_type(filename: str, text: str) -> str:
    hay = f"{filename.lower()} {text.lower()}"
    for doc_type, keys in DOC_TYPE_KEYWORDS.items():
        if any(k in hay for k in keys):
            return doc_type
    return "Unknown"
