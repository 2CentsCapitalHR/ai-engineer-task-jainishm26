from pathlib import Path

def ensure_dirs():
    Path("outputs/reviewed").mkdir(parents=True, exist_ok=True)
    Path("outputs/reports").mkdir(parents=True, exist_ok=True)
    Path("data/reference").mkdir(parents=True, exist_ok=True)
    Path("data/samples").mkdir(parents=True, exist_ok=True)
