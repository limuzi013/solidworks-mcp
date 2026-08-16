# Contributing

## What the tests can and cannot tell you

`tests/test_sw_core.py` runs anywhere: it covers the parts that are plain Python
— the method-flagging control flow, unit conversion, the assembly transform
maths. CI runs it on Windows across Python 3.10–3.13.

It cannot tell you that SOLIDWORKS accepts a call. The COM behaviour that
matters here does not mock faithfully, so anything touching geometry has to be
checked against a live session:

```powershell
.\.venv\Scripts\python.exe tests\live_p0_regression.py
```

A change to a feature or sketch tool is not done until it has run against a real
SOLIDWORKS with the result checked numerically — read the geometry back and
compare it to a closed-form value, rather than trusting the tool's own success
report. SOLIDWORKS returns null far more often than it raises.

## Check the type library before writing a tool

The published API reference disagrees with the shipped type library often enough
to matter: `FeatureFillet3` takes 14 arguments here, not the documented 7. Read
the signature off your own installation first:

```bash
python tools/tlb_probe.py methods '^IFeatureManager$' '^FeatureFillet3$'
python tools/tlb_probe.py enums '^swMateType_e$'
```

## Adding a tool

One decorated function; the registry does the rest.

```python
@tool("my_tool", "What it does. Lengths are millimetres.",
      {"depth_mm": {"type": "number"}}, ["depth_mm"])
def my_tool(args: dict[str, Any]) -> dict[str, Any]:
    _, doc = require_part()
    ...
    return result(True, "Did the thing.")
```

House rules that are not negotiable, because breaking them is how this server
silently lies to a model:

- **Units at the boundary.** Every length parameter ends in `_mm`, every angle
  in `_deg`. Convert once, in `sw_core`. No tool takes metres.
- **Take geometry as a `selection` object**, never as raw COM selection state.
  Let `sw_core` set the marks.
- **Rebuild and report `GetWhatsWrong`** after anything that changes the model.
  A tool that returns success without checking is worse than one that fails.
- **Judge success by the model, not the return value.** `SketchTrim` returns
  `False` on success; `SketchAddConstraints` silently ignores a string it does
  not recognise.
- **Never open a modal dialog.** One modal box blocks the COM call that opened
  it and deadlocks the whole server.

## Scope

This server attaches to a session the user already has open and calls the
documented API. It does not launch SOLIDWORKS, register an add-in, execute
arbitrary code, or touch the network, and a pull request that adds any of those
will not be merged — a `run_macro`-shaped tool would hand an MCP client
arbitrary code execution inside the user's CAD session.
