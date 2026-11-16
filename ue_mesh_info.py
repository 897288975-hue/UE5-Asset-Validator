"""UE5 Static Mesh Asset Validator.

Run this script from the Unreal Engine editor, not a system Python interpreter.
All validation budgets are read from validation_rules.json next to this file.
"""

import csv
import json
from pathlib import Path

import unreal  # Provided by Unreal Engine's embedded Python environment.


PROJECT_DIR = Path(__file__).resolve().parent
RULES_PATH = PROJECT_DIR / "validation_rules.json"
REPORT_PATH = PROJECT_DIR / "reports" / "UE5_MeshReport.csv"
CONTENT_ROOT = "/Game"

CSV_COLUMNS = [
    "Asset Name",
    "LODs",
    "Vertices",
    "Triangles",
    "Status",
    "Material Slots",
    "Collision Count",
    "Collision Complexity",
    "Warning Reasons",
    "Asset Path",
    "Category",
    "Triangle Limit",
    "Rule Source",
]


def load_validation_rules():
    """Load the project-specific validation rules from JSON."""
    with RULES_PATH.open("r", encoding="utf-8") as rule_file:
        rules = json.load(rule_file)
    return rules["default"], rules.get("categories", {})


def get_asset_category(asset_path, categories):
    """Identify an asset category by its folder segment, ignoring case."""
    normalized_path = asset_path.lower().replace("\\", "/")
    for category in categories:
        if f"/{category.lower()}/" in normalized_path:
            return category
    return "Default"


def get_collision_info(mesh):
    """Return simple collision shape count and readable collision mode."""
    body_setup = mesh.get_editor_property("body_setup")
    if body_setup is None:
        return 0, "UNKNOWN"

    agg_geom = body_setup.get_editor_property("agg_geom")
    collision_count = sum(
        len(agg_geom.get_editor_property(shape_property))
        for shape_property in (
            "box_elems",
            "sphere_elems",
            "sphyl_elems",
            "convex_elems",
        )
    )
    collision_flag = body_setup.get_editor_property("collision_trace_flag")
    # E.g. <CollisionTraceFlag.CTF_USE_DEFAULT: 0> -> CTF_USE_DEFAULT
    collision_mode = str(collision_flag).split(".")[-1].split(":")[0].strip()
    return collision_count, collision_mode


def validate_asset(asset_data, default_rules, categories, mesh_subsystem):
    """Inspect a single Static Mesh and return one CSV-ready result."""
    asset_name = str(asset_data.asset_name)
    asset_path = str(asset_data.package_name)
    category = get_asset_category(asset_path, categories)
    category_rules = categories.get(category, {})
    asset_rules = {**default_rules, **category_rules}
    rule_source = "Category Override" if category_rules else "Default"

    max_triangles = asset_rules["max_triangles"]
    max_material_slots = asset_rules["max_material_slots"]
    max_collision_shapes = asset_rules["max_collision_shapes"]
    allowed_collision_modes = set(asset_rules["allowed_collision_modes"])
    # Read the merged rules: category rules inherit default min_lods.
    min_lods = asset_rules["min_lods"]

    mesh = asset_data.get_asset()
    if mesh is None:
        raise RuntimeError("Static Mesh could not be loaded")

    lod_count = mesh.get_num_lods()
    vertex_count = mesh_subsystem.get_number_verts(mesh, 0)
    triangle_count = mesh.get_num_triangles(0)
    material_count = len(mesh.get_editor_property("static_materials"))
    collision_count, collision_mode = get_collision_info(mesh)

    warning_reasons = []
    if lod_count < min_lods:
        warning_reasons.append(f"Insufficient LODs: {lod_count}/{min_lods}")
    if triangle_count > max_triangles:
        warning_reasons.append(
            f"Triangle budget exceeded ({triangle_count}/{max_triangles})"
        )
    if material_count > max_material_slots:
        warning_reasons.append(
            f"Too many material slots ({material_count}/{max_material_slots})"
        )
    if collision_count > max_collision_shapes:
        warning_reasons.append(
            f"Too many collision shapes ({collision_count}/{max_collision_shapes})"
        )
    if collision_mode not in allowed_collision_modes:
        warning_reasons.append(f"Invalid collision mode: {collision_mode}")

    return {
        "name": asset_name,
        "lods": lod_count,
        "vertices": vertex_count,
        "triangles": triangle_count,
        "status": "WARNING" if warning_reasons else "PASS",
        "materials": material_count,
        "collision_count": collision_count,
        "collision_complexity": collision_mode,
        "warning_reasons": "; ".join(warning_reasons),
        "asset_path": asset_path,
        "category": category,
        "triangle_limit": max_triangles,
        "rule_source": rule_source,
    }


def export_report(results):
    """Write a UTF-8 BOM CSV so Excel can display non-ASCII text correctly."""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", newline="", encoding="utf-8-sig") as report_file:
        writer = csv.writer(report_file)
        writer.writerow(CSV_COLUMNS)
        for item in results:
            writer.writerow([
                item["name"],
                item["lods"],
                item["vertices"],
                item["triangles"],
                item["status"],
                item["materials"],
                item["collision_count"],
                item["collision_complexity"],
                item["warning_reasons"],
                item["asset_path"],
                item["category"],
                item["triangle_limit"],
                item["rule_source"],
            ])


def run_validation():
    unreal.log("MESH_INFO_STARTED")
    default_rules, categories = load_validation_rules()
    unreal.log(f"Validation rules loaded: {RULES_PATH}")
    unreal.log(f"Default triangle limit: {default_rules['max_triangles']}")
    unreal.log(f"Default material slot limit: {default_rules['max_material_slots']}")

    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = registry.get_assets_by_path(CONTENT_ROOT, recursive=True)
    unreal.log(f"Assets found in registry: {len(assets)}")

    mesh_subsystem = unreal.get_editor_subsystem(
        unreal.StaticMeshEditorSubsystem
    )
    results = []
    error_count = 0
    for asset_data in assets:
        if str(asset_data.asset_class_path.asset_name) != "StaticMesh":
            continue
        asset_name = str(asset_data.asset_name)
        asset_path = str(asset_data.package_name)
        try:
            record = validate_asset(
                asset_data, default_rules, categories, mesh_subsystem
            )
            results.append(record)
            message = (
                f"{asset_name} | Category: {record['category']} | "
                f"LODs: {record['lods']} | Vertices: {record['vertices']} | "
                f"Triangles: {record['triangles']} | "
                f"Material Slots: {record['materials']} | "
                f"Collision Count: {record['collision_count']} | "
                f"Collision Mode: {record['collision_complexity']} | "
                f"Status: {record['status']}"
            )
            if record["status"] == "WARNING":
                unreal.log_warning(message)
                unreal.log_warning(
                    f"{asset_path} | Warning Reasons: {record['warning_reasons']}"
                )
            else:
                unreal.log(message)
        except Exception as error:
            error_count += 1
            unreal.log_error(f"{asset_path} | Inspection error: {error}")

    pass_count = sum(1 for record in results if record["status"] == "PASS")
    warning_count = sum(1 for record in results if record["status"] == "WARNING")
    pass_rate = (pass_count / len(results) * 100) if results else 0.0

    unreal.log("=== Mesh Validation Summary ===")
    unreal.log(f"Validated Static Meshes: {len(results)}")
    unreal.log(f"Passed: {pass_count}")
    unreal.log(f"Warnings: {warning_count}")
    unreal.log(f"Inspection errors (not included above): {error_count}")
    unreal.log(f"Pass Rate: {pass_rate:.1f}%")

    export_report(results)
    unreal.log(f"CSV report exported: {REPORT_PATH}")


# Execute when invoked with the UE5 editor `py "<script path>"` command.
run_validation()
