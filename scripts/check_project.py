from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
print(f"Project root: {root}")
result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=root, check=False)
raise SystemExit(result.returncode)
