"""Shared pytest configuration: import paths for app + services packages."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
for p in (str(REPO_ROOT / "apps" / "api"), str(REPO_ROOT / "services")):
    if p not in sys.path:
        sys.path.insert(0, p)
