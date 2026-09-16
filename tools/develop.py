"""Run TRIGRIX Studio directly from the working tree."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(root / "run_trigrix_studio.py")], cwd=root, check=True)
