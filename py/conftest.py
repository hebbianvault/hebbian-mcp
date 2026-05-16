"""
conftest.py — ensure src/ is on sys.path for pytest.

Belt-and-braces for uv editable installs where the .pth file may not be
processed (Python 3.11+ + uv venv combinations). See coding-factory LEARNINGS
2026-05-15.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
