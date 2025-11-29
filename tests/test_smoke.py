# tests/test_smoke.py
from pathlib import Path
import sys
import importlib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def test_smoke_imports():
    importlib.import_module("services.api.app.main")
    importlib.import_module("services.worker.worker.tasks")