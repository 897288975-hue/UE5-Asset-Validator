# Technical Notes — UE5 Asset Validator V0.1

## Problem statement

Manual asset inspection is repetitive and inconsistent. This prototype automates basic Static Mesh QC checks and exports a report that an artist or reviewer can inspect outside UE5.

## Processing pipeline

```text
Unreal Asset Registry (/Game)
          ↓
Filter assets by StaticMesh class
          ↓
Read model data + simple collision data
          ↓
Infer category from /Category/ directory segment
          ↓
Merge default + category JSON rules
          ↓
Collect ALL applicable warning reasons
          ↓
Mark PASS or WARNING and export CSV
```

## API usage

- `unreal.AssetRegistryHelpers.get_asset_registry()` and `get_assets_by_path()` — asset discovery.
- `asset_data.get_asset()` — asset loading.
- `StaticMesh.get_num_lods()` and `get_num_triangles(0)` — LOD count and LOD0 triangle count.
- `unreal.StaticMeshEditorSubsystem.get_number_verts(mesh, 0)` — LOD0 vertex count; avoids the deprecated `EditorStaticMeshLibrary.get_number_verts` used in an early prototype.
- `mesh.get_editor_property('static_materials')` — material slot list.
- `body_setup` → `agg_geom` — simple collision primitives (box, sphere, capsule, convex).
- `collision_trace_flag` — asset-level collision complexity enum.

Methods listed above were exercised by the original prototype in UE5.7. The GitHub-ready refactor also includes mock-based tests, but has **not been run against a live UE5 editor in this packaging environment**.

## Rule precedence

1. Look up the asset's category by matching `/Architecture/`, `/Props/` or `/Foliage/` based on the JSON keys.
2. Start with the `default` rule dictionary.
3. Apply the matching category override keys.
4. Validate against the merged dictionary, including inherited `min_lods`.

Case-insensitive directory segment matching is deliberate. If multiple recognized category segments appear in a path, the first category in `validation_rules.json` wins; a future version could support explicit priority or prefix mappings.

## Status semantics

- `PASS`: no configured rule was violated.
- `WARNING`: at least one configured rule was violated; the `Warning Reasons` field joins all reasons using `; `.
- Inspection exceptions are logged as **errors** and counted separately. They are omitted from the CSV currently, so validated count and errors count should be considered together.

## Interpretation cautions

- The default **200 triangle** cap is for demo/testing only. A real game needs asset-specific budgets.
- `min_lods` checks the number of LOD levels, **not their screen-size quality**. It does not account for Nanite-specific workflows.
- `CTF_USE_DEFAULT` references project defaults; the inspector does not resolve those project settings.
- Collision shape count is not enough to evaluate collision accuracy or runtime cost.
- A missing BodySetup returns collision count 0 and mode `UNKNOWN`; this triggers an invalid collision mode warning under the current sample policy.
- This script performs **read-only validation** on UE assets. The only writes are to `reports/UE5_MeshReport.csv`.

## Reproduction checklist

1. Enable Python Editor Script Plugin in a local UE5 project.
2. Put test static meshes in `/Game` and optional category folders.
3. Run the file from the editor's `Cmd` console.
4. Confirm asset count, PASS/WARNING counts, and report output path.
5. Compare CSV values with Static Mesh Editor for a sample of assets.
6. Test different budgets, one warning and multiple warnings, and the zero-mesh case.

## Future work

- Include inspection errors in the CSV with `ERROR` status.
- Add material assignment validity, collision policy per category and Nanite-aware LOD handling.
- Allow configurable path prefixes and rule profiles per target platform.
- Create an Editor Utility Widget and HTML/visual dashboard.
