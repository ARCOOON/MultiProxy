"""Convenience entry point for running the proxy server.

This script ensures the project's ``src`` directory is on ``sys.path`` so
that the ``proxy`` package can be imported without installation.  It then
invokes :func:`proxy.server.main` which exposes the same command line
interface as ``python -m proxy.server``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add the src directory to sys.path to make ``proxy`` importable
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proxy.server import main as run_server  # noqa: E402


if __name__ == "__main__":
    run_server()
