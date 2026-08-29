# tests/conftest.py
import sys
from pathlib import Path

# Add workspace directory to sys.path so tests can import local modules
sys.path.insert(0, str(Path(__file__).parent.parent))
