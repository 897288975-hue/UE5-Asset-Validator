"""Mock-based tests. These do not replace live testing in UE5."""

import csv
import runpy
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class FakeMesh:
    def __init__(self, lods, vertices, triangles, material_slots=1,
                 shapes=1, mode="CTF_USE_DEFAULT", body_setup=True):
        self.lods = lods
        self.vertices = vertices
        self.triangles = triangles
        self.material_slots = material_slots
        self.shapes = shapes
        self.mode = mode
        self.body_setup = body_setup

    def get_num_lods(self):
        return self.lods

    def get_num_triangles(self, lod_index):
        assert lod_index == 0
        return self.triangles

    def get_editor_property(self, key):
        if key == "static_materials":
            return [object()] * self.material_slots
        if key == "body_setup":
            return FakeBodySetup(self.shapes, self.mode) if self.body_setup else None
        raise KeyError(key)


class FakeBodySetup:
    def __init__(self, shapes, mode):
        self.shapes = shapes
        self.mode = mode

    def get_editor_property(self, key):
        if key == "agg_geom":
            return FakeAggGeom(self.shapes)
        if key == "collision_trace_flag":
            return f"<CollisionTraceFlag.{self.mode}: 0>"
        raise KeyError(key)


class FakeAggGeom:
    def __init__(self, count):
        self.count = count

    def get_editor_property(self, key):
        if key == "box_elems":
            return [object()] * self.count
        if key in {"sphere_elems", "sphyl_elems", "convex_elems"}:
            return []
        raise KeyError(key)


class FakeAssetData:
    def __init__(self, path, mesh):
        self.asset_name = path.rsplit("/", 1)[-1]
        self.package_name = path
        self.asset_class_path = types.SimpleNamespace(asset_name="StaticMesh")
        self.mesh = mesh

    def get_asset(self):
        return self.mesh


class FakeRegistry:
    def __init__(self, assets):
        self.assets = assets

    def get_assets_by_path(self, path, recursive=False):
        assert path == "/Game" and recursive is True
        return self.assets


class FakeStaticMeshSubsystem:
    def get_number_verts(self, mesh, lod_index):
        assert lod_index == 0
        return mesh.vertices


def execute_in_fake_editor(tmp_path, assets):
    """Copy the released files to a new path and simulate `py <script>`."""
    shutil.copy(ROOT / "ue_mesh_info.py", tmp_path / "ue_mesh_info.py")
    shutil.copy(ROOT / "validation_rules.json", tmp_path / "validation_rules.json")
    logs = []
    registry = FakeRegistry(assets)
    ue = types.ModuleType("unreal")
    ue.AssetRegistryHelpers = types.SimpleNamespace(get_asset_registry=lambda: registry)
    ue.StaticMeshEditorSubsystem = FakeStaticMeshSubsystem
    ue.get_editor_subsystem = lambda _: FakeStaticMeshSubsystem()
    ue.log = lambda message: logs.append(("INFO", message))
    ue.log_warning = lambda message: logs.append(("WARNING", message))
    ue.log_error = lambda message: logs.append(("ERROR", message))

    with patch.dict(sys.modules, {"unreal": ue}):
        runpy.run_path(str(tmp_path / "ue_mesh_info.py"))

    report_path = tmp_path / "reports" / "UE5_MeshReport.csv"
    with report_path.open("r", encoding="utf-8-sig", newline="") as report_file:
        rows = list(csv.DictReader(report_file))
    return rows, logs


class TestValidatorWorkflow(unittest.TestCase):
    def test_category_override_inherits_defaults_and_aggregates_warnings(self):
        assets = [
            FakeAssetData(
                "/Game/LevelPrototyping/Meshes/SM_ChamferCube",
                FakeMesh(1, 176, 256),
            ),
            FakeAssetData(
                "/Game/Props/SM_ChamferCube",
                FakeMesh(1, 176, 256),
            ),
            FakeAssetData(
                "/Game/Props/SM_Valid",
                FakeMesh(2, 50, 300),
            ),
            FakeAssetData(
                "/Game/Props/SM_MultiWarning",
                FakeMesh(1, 1200, 4000, material_slots=4,
                         shapes=6, mode="CTF_USE_COMPLEX_AS_SIMPLE"),
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            rows, logs = execute_in_fake_editor(Path(directory), assets)

        self.assertEqual(len(rows), 4)
        by_path = {row["Asset Path"]: row for row in rows}
        original = by_path["/Game/LevelPrototyping/Meshes/SM_ChamferCube"]
        copied = by_path["/Game/Props/SM_ChamferCube"]
        valid = by_path["/Game/Props/SM_Valid"]
        multi = by_path["/Game/Props/SM_MultiWarning"]

        self.assertEqual(original["Status"], "WARNING")
        self.assertIn("256/200", original["Warning Reasons"])
        self.assertEqual(original["Rule Source"], "Default")
        self.assertEqual(copied["Category"], "Props")
        self.assertEqual(copied["Triangle Limit"], "3000")
        self.assertEqual(copied["Rule Source"], "Category Override")
        self.assertEqual(copied["Status"], "WARNING")
        self.assertEqual(copied["Warning Reasons"], "Insufficient LODs: 1/2")
        self.assertEqual(valid["Status"], "PASS")
        self.assertEqual(valid["Warning Reasons"], "")

        reasons = multi["Warning Reasons"].split("; ")
        self.assertEqual(len(reasons), 5)
        self.assertIn("Triangle budget exceeded (4000/3000)", reasons)
        self.assertIn("Too many material slots (4/3)", reasons)
        self.assertIn("Too many collision shapes (6/5)", reasons)
        self.assertIn("Insufficient LODs: 1/2", reasons)
        self.assertIn("Invalid collision mode: CTF_USE_COMPLEX_AS_SIMPLE", reasons)
        self.assertTrue(any("Passed: 1" in message for _, message in logs))
        self.assertTrue(any("Warnings: 3" in message for _, message in logs))
        self.assertFalse(any(level == "ERROR" for level, _ in logs))

    def test_empty_project_writes_header_and_no_division_error(self):
        with tempfile.TemporaryDirectory() as directory:
            rows, logs = execute_in_fake_editor(Path(directory), [])
        self.assertEqual(rows, [])
        self.assertTrue(any("Pass Rate: 0.0%" in message for _, message in logs))
        self.assertFalse(any(level == "ERROR" for level, _ in logs))


if __name__ == "__main__":
    unittest.main()
