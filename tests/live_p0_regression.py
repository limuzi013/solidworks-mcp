"""Live SOLIDWORKS regression checks for the previously confirmed P0 defects.

Run this only on a workstation with SOLIDWORKS already running:

    ..\\.venv\\Scripts\\python.exe tests\\live_p0_regression.py

The test uses the public handler functions, so it exercises the same COM calls
and unit conversions as the MCP server.  It deliberately creates new unsaved
documents and leaves them open for visual inspection; it never edits an
existing document.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from solidworks_direct.sw_feature import boss_extrude, cut_extrude
from solidworks_direct.sw_file import create_new_document
from solidworks_direct.sw_inspect import get_mass_properties
from solidworks_direct.sw_sketch import (
    add_relation,
    close_sketch,
    create_sketch,
    draw_circle,
    draw_line,
    draw_rectangle,
    list_sketch_segments,
    sketch_trim,
)


def require(payload: dict[str, Any], context: str) -> dict[str, Any]:
    if not payload.get("ok"):
        raise AssertionError(f"{context} failed: {payload.get('message')}")
    return payload


def segments() -> list[dict[str, Any]]:
    return require(list_sketch_segments({}), "list_sketch_segments")["data"]["segments"]


def test_through_all_both() -> None:
    require(create_new_document({"kind": "part"}), "create through-all test part")
    require(create_sketch({"plane": "front", "name": "P0_Through_Base"}), "create base sketch")
    require(draw_rectangle({"x1_mm": -50, "y1_mm": -50, "x2_mm": 50, "y2_mm": 50}), "draw base")
    require(close_sketch({}), "close base sketch")
    require(
        boss_extrude({
            "sketch_name": "P0_Through_Base", "depth_mm": 10,
            "end_condition": "mid_plane", "name": "P0_Through_BaseBoss",
        }),
        "build symmetric test block",
    )
    before = require(get_mass_properties({}), "read pre-cut volume")["data"]["volume_mm3"]
    require(create_sketch({"plane": "front", "name": "P0_Through_Circle"}), "create cut sketch")
    require(draw_circle({"x_mm": 0, "y_mm": 0, "radius_mm": 10}), "draw cut circle")
    require(close_sketch({}), "close cut sketch")
    require(
        cut_extrude({
            "sketch_name": "P0_Through_Circle", "end_condition": "through_all_both",
            "name": "P0_Through_All_Both",
        }),
        "cut through both directions",
    )
    after = require(get_mass_properties({}), "read post-cut volume")["data"]["volume_mm3"]
    expected_removed = math.pi * 10**2 * 10
    removed = before - after
    if not math.isclose(removed, expected_removed, rel_tol=0, abs_tol=0.05):
        raise AssertionError(
            f"through_all_both removed {removed:.3f} mm^3; expected {expected_removed:.3f} mm^3"
        )


def test_equal_circles() -> None:
    require(create_new_document({"kind": "part"}), "create equal-circle test part")
    require(create_sketch({"plane": "front", "name": "P0_Equal_Circles"}), "create equal-circle sketch")
    require(draw_circle({"x_mm": -15, "y_mm": 0, "radius_mm": 5}), "draw first circle")
    require(draw_circle({"x_mm": 15, "y_mm": 0, "radius_mm": 10}), "draw second circle")
    require(add_relation({"relation": "equal", "selection": {"sketch_segments": [0, 1]}}), "add equal relation")
    radii = [segment.get("radius_mm") for segment in segments()]
    if len(radii) != 2 or not math.isclose(float(radii[0]), float(radii[1]), abs_tol=1e-6):
        raise AssertionError(f"equal relation did not equalize circle radii: {radii}")
    require(close_sketch({}), "close equal-circle sketch")


def test_trim_selected_segment() -> None:
    require(create_new_document({"kind": "part"}), "create trim test part")
    require(create_sketch({"plane": "front", "name": "P0_Trim"}), "create trim sketch")
    require(draw_line({"x1_mm": -20, "y1_mm": 0, "x2_mm": 20, "y2_mm": 0}), "draw target line")
    require(draw_line({"x1_mm": 0, "y1_mm": -10, "x2_mm": 0, "y2_mm": 10}), "draw crossing line")
    require(
        sketch_trim({"selection": {"sketch_segments": [0]}, "x_mm": -10, "y_mm": 0, "mode": "closest"}),
        "trim the selected left-hand line piece",
    )
    lines = segments()
    target = lines[0]
    endpoints = {round(target["start_mm"][0], 6), round(target["end_mm"][0], 6)}
    if endpoints != {0.0, 20.0}:
        raise AssertionError(f"trim modified the wrong line or segment: {target}")
    require(close_sketch({}), "close trim sketch")


def main() -> None:
    test_through_all_both()
    test_equal_circles()
    test_trim_selected_segment()
    print("P0 part/sketch regressions passed: through_all_both, equal circles, selected-segment trim.")


if __name__ == "__main__":
    main()
