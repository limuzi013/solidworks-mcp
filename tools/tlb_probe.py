"""Inspect the locally installed SOLIDWORKS type libraries.

Use this instead of relying on method signatures remembered from another
SOLIDWORKS release.  For example:

    python tools\\tlb_probe.py methods '^IFeatureManager$' '^FeatureCut4$'
    python tools\\tlb_probe.py enums '^swMateType_e$'
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import pythoncom


def candidate_roots() -> list[Path]:
    """Where sldworks.tlb might live, best guess first.

    A running SOLIDWORKS knows its own install directory, which beats guessing
    at folder names that vary between installs.
    """
    roots: list[Path] = []
    override = os.environ.get("SW_MCP_INSTALL_DIR")
    if override:
        roots.append(Path(override))
    try:
        import win32com.client

        app = win32com.client.GetActiveObject("SldWorks.Application")
        # GetExecutablePath reports the install *directory*, not the .exe.
        reported = Path(str(getattr(app, "GetExecutablePath", "") or ""))
        roots += [reported, reported.parent]
    except Exception:
        pass
    for base in (Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)")):
        roots += sorted(base.glob("*/SOLIDWORKS")) + sorted(base.glob("SOLIDWORKS*"))
    return [root for root in roots if root.parts]


def find_library(name: str) -> Path:
    for root in candidate_roots():
        candidate = root / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Could not find {name}. Set SW_MCP_INSTALL_DIR to the folder that contains it."
    )


def matching_type_infos(library: object, pattern: str):
    matcher = re.compile(pattern)
    for index in range(library.GetTypeInfoCount()):
        type_info = library.GetTypeInfo(index)
        name = library.GetDocumentation(index)[0]
        if matcher.search(name):
            yield name, type_info


def inspect_methods(interface_pattern: str, method_pattern: str) -> None:
    library = pythoncom.LoadTypeLib(str(find_library("sldworks.tlb")))
    method_matcher = re.compile(method_pattern)
    found = False
    for interface_name, type_info in matching_type_infos(library, interface_pattern):
        for index in range(type_info.GetTypeAttr().cFuncs):
            descriptor = type_info.GetFuncDesc(index)
            names = type_info.GetNames(descriptor.memid)
            if names and method_matcher.search(names[0]):
                found = True
                print(f"{interface_name}.{names[0]}({', '.join(names[1:])})")
                print(f"  parameters={len(descriptor.args)} invkind={descriptor.invkind} flags={descriptor.wFuncFlags}")
    if not found:
        raise SystemExit("No matching methods found.")


def inspect_enums(enum_pattern: str) -> None:
    library = pythoncom.LoadTypeLib(str(find_library("swconst.tlb")))
    found = False
    for enum_name, type_info in matching_type_infos(library, enum_pattern):
        found = True
        print(enum_name)
        for index in range(type_info.GetTypeAttr().cVars):
            descriptor = type_info.GetVarDesc(index)
            name = type_info.GetNames(descriptor.memid)[0]
            print(f"  {name} = {descriptor.value}")
    if not found:
        raise SystemExit("No matching enums found.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    methods = commands.add_parser("methods", help="Inspect matching interface methods.")
    methods.add_argument("interface_pattern")
    methods.add_argument("method_pattern")
    enums = commands.add_parser("enums", help="Inspect matching swconst enums.")
    enums.add_argument("enum_pattern")
    args = parser.parse_args()
    if args.command == "methods":
        inspect_methods(args.interface_pattern, args.method_pattern)
    else:
        inspect_enums(args.enum_pattern)


if __name__ == "__main__":
    main()
