import sys
from pathlib import Path

# Make "brandguard" importable when running pytest from the project folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
