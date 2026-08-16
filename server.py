"""Launcher for the clone-and-point-at-a-path install.

A package install (``pip install .``, ``uvx``) gets the ``solidworks-mcp``
console script instead. This file exists so that an MCP host configured with the
absolute path to a checkout keeps working without one, which is how the server
was set up before it was packaged.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from solidworks_mcp.server import run  # noqa: E402  (path set above)

if __name__ == "__main__":
    run()
