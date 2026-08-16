"""The basketball demo, kept out of the main namespace.

These tools were useful while proving the bridge out, but a tool named
create_basketball sitting next to revolve and fillet actively misleads tool
selection.  They now register only when SW_MCP_DEMO_TOOLS is set to 1/true/yes.
"""

from __future__ import annotations

import math
import os
from typing import Any

from sw_core import (
    active_document,
    clear_selection,
    document_info,
    document_type,
    double_array,
    feature_manager,
    feature_property,
    find_feature,
    invoke_no_arg,
    iter_features,
    latest_sketch,
    logger,
    reference_planes,
    result,
    selectable,
    select_by_id,
    sketch_manager,
    tool,
    value,
)
from sw_file import new_document


DEMO_ENABLED = os.environ.get("SW_MCP_DEMO_TOOLS", "").strip().lower() in {"1", "true", "yes", "on"}

ORANGE_BASKETBALL_APPEARANCE = (
    0.98, 0.45, 0.04,
    0.50, 0.92, 0.18,
    0.25, 0.0, 0.0,
)
BLACK_SEAM_APPEARANCE = (
    0.015, 0.015, 0.015,
    0.18, 0.72, 0.15,
    0.32, 0.0, 0.0,
)


def _apply_model_appearance(doc: Any, values: tuple[float, ...]) -> None:
    doc.MaterialPropertyValues = double_array(values)
    applied = tuple(float(v) for v in doc.MaterialPropertyValues)
    # RGB channels are stored at 8-bit precision, so a read-back can differ by
    # up to 1/255 even when the appearance was applied correctly.
    if len(applied) != len(values) or any(
        abs(actual - expected) > (1 / 255 + 1e-6) for actual, expected in zip(applied, values)
    ):
        raise RuntimeError(f"SOLIDWORKS did not retain the requested appearance values: {applied}")
    try:
        invoke_no_arg(doc, "GraphicsRedraw2")
    except Exception:
        logger.info("Appearance assigned, but SOLIDWORKS declined an immediate graphics redraw.")


def _set_feature_faces_appearance(feature: Any, values: tuple[float, ...]) -> None:
    """Colour the toroidal faces of a groove without darkening the ball skin."""
    try:
        faces = feature.GetFaces()
        if faces is None:
            return
        for face in faces:
            try:
                surface = value(face, "GetSurface")
                if bool(value(surface, "IsTorus")):
                    face.MaterialPropertyValues = double_array(values)
            except Exception:
                logger.info("Could not colour one basketball groove face.")
    except Exception:
        logger.info("Could not enumerate basketball groove faces.")


def _hide_sketch(doc: Any, name: str) -> None:
    feature = find_feature(doc, name)
    if feature is None:
        return
    try:
        clear_selection(doc)
        if selectable(feature).Select2(False, 0):
            invoke_no_arg(doc, "BlankSketch")
    except Exception:
        logger.info("Could not hide reference sketch %s", name)
    finally:
        clear_selection(doc)


def _hide_all_profile_sketches(doc: Any) -> None:
    for feature in iter_features(doc):
        if feature["type"] == "ProfileFeature" and feature["name"]:
            _hide_sketch(doc, feature["name"])


def _select_revolve_profile_and_axis(doc: Any, sketch_feature: Any, axis: Any) -> None:
    clear_selection(doc)
    if not bool(selectable(sketch_feature).Select2(False, 0)):
        raise RuntimeError("Could not select the groove profile sketch for revolve.")
    try:
        select_data = doc.SelectionManager.CreateSelectData()
        select_data.Mark = 4
        selected = bool(axis.Select4(True, select_data))
    except Exception:
        selected = bool(axis.Select2(True, 4))
    if not selected:
        raise RuntimeError("Could not select the revolve centerline.")


def _add_toroidal_groove(
    doc: Any,
    plane_name: str,
    sphere_radius_m: float,
    groove_radius_m: float,
    name: str,
    axis_offset_m: float = 0.0,
) -> Any:
    existing = find_feature(doc, name)
    if existing is not None:
        return existing
    if not select_by_id(doc, plane_name, "PLANE"):
        raise RuntimeError(f"Could not select seam plane '{plane_name}'.")
    manager = sketch_manager(doc)
    manager.InsertSketch(True)
    radial_distance = math.sqrt(max(0.0, sphere_radius_m**2 - axis_offset_m**2))
    manager.CreateCircleByRadius(radial_distance, axis_offset_m, 0.0, groove_radius_m)
    axis = manager.CreateLine(0.0, -sphere_radius_m * 1.2, 0.0, 0.0, sphere_radius_m * 1.2, 0.0)
    try:
        axis.ConstructionGeometry = True
    except Exception:
        logger.info("SOLIDWORKS did not flag the groove axis as construction geometry.")
    manager.InsertSketch(True)
    _, sketch_feature = latest_sketch(doc)
    sketch_feature.Name = f"{name}_Profile"
    _select_revolve_profile_and_axis(doc, sketch_feature, axis)
    groove = feature_manager(doc).FeatureRevolve2(
        True, True, False, True, False, False,
        0, 0, math.tau, 0.0,
        False, False, 0.0, 0.0,
        0, 0.0, 0.0, True, False, True,
    )
    if groove is None:
        raise RuntimeError(f"SOLIDWORKS did not create groove '{name}'.")
    groove.Name = name
    _hide_sketch(doc, f"{name}_Profile")
    invoke_no_arg(doc, "EditRebuild3")
    return groove


def create_basketball(args: dict[str, Any]) -> dict[str, Any]:
    diameter_mm = float(args.get("diameter_mm", 239))
    if not 20.0 <= diameter_mm <= 1000.0:
        return result(False, "diameter_mm must be between 20 and 1000.")
    created = new_document("part")
    if not created.get("ok"):
        return created

    _, doc = active_document()
    plane_names = reference_planes(doc)
    if not plane_names:
        return result(False, "The new part has no reference planes.")
    radius_m = diameter_mm / 2000.0

    if not select_by_id(doc, plane_names[0], "PLANE"):
        return result(False, f"Could not select reference plane '{plane_names[0]}'.")
    manager = sketch_manager(doc)
    manager.InsertSketch(True)
    # A closed semicircle revolved about its diameter makes a sphere; a full
    # circle would self-intersect during the revolve.
    manager.CreateArc(0.0, 0.0, 0.0, 0.0, radius_m, 0.0, 0.0, -radius_m, 0.0, 1)
    axis = manager.CreateLine(0.0, -radius_m, 0.0, 0.0, radius_m, 0.0)
    manager.InsertSketch(True)

    sketch_name, sketch_feature = latest_sketch(doc)
    clear_selection(doc)
    if not bool(selectable(sketch_feature).Select2(False, 0)):
        return result(False, f"Could not select base sketch '{sketch_name}'.")
    try:
        select_data = doc.SelectionManager.CreateSelectData()
        select_data.Mark = 4
        axis_selected = bool(axis.Select4(True, select_data))
    except Exception:
        axis_selected = bool(axis.Select2(True, 4))
    if not axis_selected:
        return result(False, "Could not select the revolve centerline.")

    sphere = feature_manager(doc).FeatureRevolve2(
        True, True, False, False, False, False,
        0, 0, math.tau, 0.0,
        False, False, 0.0, 0.0,
        0, 0.0, 0.0, True, True, True,
    )
    if sphere is None:
        return result(False, "SOLIDWORKS did not create the spherical revolve.")
    try:
        sphere.Name = "Basketball_Base"
    except Exception:
        pass
    invoke_no_arg(doc, "EditRebuild3")

    if bool(args.get("orange", True)):
        try:
            _apply_model_appearance(doc, ORANGE_BASKETBALL_APPEARANCE)
        except Exception:
            logger.info("The basketball was created but its display colour could not be assigned.")

    clear_selection(doc)
    invoke_no_arg(doc, "EditRebuild3")
    try:
        invoke_no_arg(doc, "ViewZoomtofit2")
    except Exception:
        pass
    return result(
        True,
        "Created a basketball demo part.",
        document=document_info(doc),
        diameter_mm=diameter_mm,
        base_feature="Basketball_Base",
    )


def upgrade_active_basketball(args: dict[str, Any]) -> dict[str, Any]:
    diameter_mm = float(args.get("diameter_mm", 239))
    groove_width_mm = float(args.get("groove_width_mm", 2.4))
    if not 20.0 <= diameter_mm <= 1000.0:
        return result(False, "diameter_mm must be between 20 and 1000.")
    if not 0.4 <= groove_width_mm <= 8.0:
        return result(False, "groove_width_mm must be between 0.4 and 8.")
    _, doc = active_document()
    if document_type(doc) != 1:
        return result(False, "upgrade_active_basketball requires an active part document.")
    if find_feature(doc, "Basketball_Base") is None:
        return result(False, "The active part does not contain Basketball_Base, so it is not the demo sphere.")

    _hide_all_profile_sketches(doc)
    planes = reference_planes(doc)
    if len(planes) < 3:
        return result(False, "The active part is missing one or more standard reference planes.", planes=planes)

    radius_m = diameter_mm / 2000.0
    groove_radius_m = groove_width_mm / 2000.0
    grooves: list[str] = []
    groove_specs = (
        ("Front", planes[0], 0.0),
        ("Top", planes[1], 0.0),
        ("FrontUpper", planes[0], radius_m * 0.38),
        ("FrontLower", planes[0], -radius_m * 0.38),
    )
    for suffix, plane_name, axis_offset_m in groove_specs:
        try:
            feature = _add_toroidal_groove(
                doc, plane_name, radius_m, groove_radius_m, f"Basketball_Groove_{suffix}", axis_offset_m
            )
            _set_feature_faces_appearance(feature, BLACK_SEAM_APPEARANCE)
            grooves.append(str(feature_property(feature, "Name", f"Basketball_Groove_{suffix}")))
        except RuntimeError as exc:
            logger.warning("Basketball groove %s was skipped: %s", suffix, exc)

    _apply_model_appearance(doc, ORANGE_BASKETBALL_APPEARANCE)
    # Recolour the seams after the body, so the orange model-level appearance
    # does not overwrite them.
    for groove_name in grooves:
        feature = find_feature(doc, groove_name)
        if feature is not None:
            _set_feature_faces_appearance(feature, BLACK_SEAM_APPEARANCE)
    _hide_all_profile_sketches(doc)
    clear_selection(doc)
    invoke_no_arg(doc, "EditRebuild3")
    try:
        invoke_no_arg(doc, "ViewZoomtofit2")
    except Exception:
        pass
    return result(
        True,
        "Upgraded the active basketball in place.",
        document=document_info(doc),
        grooves=grooves,
        diameter_mm=diameter_mm,
        groove_width_mm=groove_width_mm,
    )


if DEMO_ENABLED:
    tool(
        "demo_create_basketball",
        "Demo: create a basketball as a new part from a 360-degree spherical revolve. Millimetres.",
        {
            "diameter_mm": {"type": "number", "default": 239, "minimum": 20, "maximum": 1000},
            "orange": {"type": "boolean", "default": True},
        },
    )(create_basketball)

    tool(
        "demo_upgrade_basketball",
        "Demo: add revolved groove seams and an orange appearance to the active basketball part. "
        "Requires a Basketball_Base feature. Millimetres.",
        {
            "diameter_mm": {"type": "number", "default": 239, "minimum": 20, "maximum": 1000},
            "groove_width_mm": {"type": "number", "default": 2.4, "minimum": 0.4, "maximum": 8},
        },
    )(upgrade_active_basketball)
