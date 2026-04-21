"""Compatibility wrapper for legacy host path.

Prefer imports from `esp32_mcp_io_extender.bridge`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from esp32_mcp_io_extender.bridge import *  # noqa: F401,F403
