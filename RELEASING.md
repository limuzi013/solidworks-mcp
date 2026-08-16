# Releasing

The MCP Registry stores metadata only, not artifacts, so a release is two
publishes in order: the package to PyPI first, then the registry entry that
points at it. The registry validates the PyPI package before accepting the
entry, so the order is not optional.

## The short version: push a tag

`.github/workflows/publish-mcp.yml` does the whole sequence on a `v*` tag —
version consistency check, ownership-marker check, build, PyPI, then the
registry — authenticating both publishes over OIDC, so no token is stored in
the repository.

**One-time setup on PyPI, before the first tag.** Under the project's
Publishing settings add a *pending publisher* for GitHub with owner
`limuzi013`, repository `solidworks-direct`, and workflow `publish-mcp.yml`.
Without it the PyPI step fails to authenticate.

```bash
git tag v0.1.0 && git push origin v0.1.0
```

The rest of this file is what that workflow automates, and what to do by hand if
it is not usable.

## 1. Bump the version in all three places

A release fails validation if these disagree:

| File | Field |
| --- | --- |
| `pyproject.toml` | `project.version` |
| `server.json` | `version` |
| `server.json` | `packages[0].version` |

`solidworks_direct/__init__.py` carries `__version__` for anyone reading it at
runtime; keep it in step too.

## 2. Check the ownership marker is intact

The registry verifies ownership of a PyPI package by looking for an
`mcp-name:` line in the package README, which becomes the PyPI description.
`README.md` carries it as a comment:

```markdown
<!-- mcp-name: io.github.limuzi013/solidworks-direct -->
```

The name after `mcp-name:` **must** match `name` in `server.json`. Deleting that
line is what "Registry validation failed for package" usually means.

## 3. Run the tests and build

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

```powershell
.\.venv\Scripts\python.exe -m pip install build && .\.venv\Scripts\python.exe -m build
```

## 4. Publish to PyPI

PyPA recommends [trusted publishing](https://docs.pypi.org/trusted-publishers/)
over API tokens: configure the publisher once on PyPI under the project's
settings, and CI mints a short-lived credential through OIDC with no stored
secret. Publishing by hand instead:

```powershell
.\.venv\Scripts\python.exe -m pip install twine && .\.venv\Scripts\python.exe -m twine upload dist/*
```

A PyPI version number can never be reused, even after deleting the release.
Check the version before uploading, not after.

## 5. Publish to the MCP Registry

Install the official `mcp-publisher` CLI:

```powershell
$arch = if ([System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -eq "Arm64") { "arm64" } else { "amd64" }; Invoke-WebRequest -Uri "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_windows_$arch.tar.gz" -OutFile "mcp-publisher.tar.gz"; tar xf mcp-publisher.tar.gz mcp-publisher.exe; rm mcp-publisher.tar.gz
```

Authenticate and publish. GitHub authentication is a device-code flow, and the
namespace it grants is `io.github.<your-username>/`, which is why the server is
named `io.github.limuzi013/solidworks-direct`:

```powershell
.\mcp-publisher.exe login github
```

```powershell
.\mcp-publisher.exe publish
```

Verify:

```powershell
curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.limuzi013/solidworks-direct"
```

## 6. Point the README at PyPI

Until the package is on PyPI, `uvx solidworks-direct` does not resolve, so the
README documents installing from a checkout instead. Once the first release is
live, add the shorter form:

```json
{
  "mcpServers": {
    "solidworks-direct": {
      "command": "uvx",
      "args": ["solidworks-direct"]
    }
  }
}
```
