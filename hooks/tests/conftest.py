"""Make hooks/ importable (the hooks are stdlib scripts, not a package)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
