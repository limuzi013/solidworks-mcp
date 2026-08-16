"""A local, stdio-only MCP server for a running SOLIDWORKS session.

Importing this package is cheap: the COM connection is made on the first tool
call, not at import time, so the offline tests and the packaging metadata can
both load it without SOLIDWORKS installed.
"""

__version__ = "0.1.0"
