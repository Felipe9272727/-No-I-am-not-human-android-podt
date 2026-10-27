#!/usr/bin/env python3
"""Read-only regression audit for exported level-1 transforms and renderer bounds."""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "reconstruction/android-current/app/src/main/assets/world/world_manifest.json"


def close(a, b, tol=2e-5):
    return math.isfinite(a) and abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def vector(v):
    try:
        return [float(x) for x in v]
    except TypeError:
        return [float(getattr(v, key)) for key in ("x", "y", "z", "w") if hasattr(v, key)]


def local_matrix(tr):
    x, y, z, w = vector(tr.m_LocalRotation)
    sx, sy, sz = vector(tr.m_LocalScale)
    px, py, pz = vector(tr.m_LocalPosition)
    return [[(1-2*(y*y+z*z))*sx, (2*(x*y-z*w))*sy, (2*(x*z+y*w))*sz, px],
            [(2*(x*y+z*w))*sx, (1-2*(x*x+z*z))*sy, (2*(y*z-x*w))*sz, py],
            [(2*(x*z-y*w))*sx, (2*(y*z+x*w))*sy, (1-2*(x*x+y*y))*sz, pz],
            [0.0, 0.0, 0.0, 1.0]]


def multiply(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def audit_raw(data_dir, manifest):
    """Re-read Unity serialized objects and independently rebuild hierarchy TRS."""
    import UnityPy

    scene = data_dir if data_dir.is_file() else data_dir / "level1"
    env = UnityPy.load(str(scene))
    objects = list(env.objects)
    gameobjects, transforms, component_go, components_by_go, renderers, skinned_renderers = {}, {}, {}, {}, {}, {}
    for obj in objects:
        try:
            parsed = obj.read()
        except Exception:
            continue
        kind = obj.type.name
        if kind == "GameObject":
            gameobjects[int(obj.path_id)] = parsed
            components_by_go[int(obj.path_id)] = [int(c.component.m_PathID) for c in parsed.m_Component]
        elif kind in ("Transform", "RectTransform"):
            transforms[int(obj.path_id)] = parsed
            component_go[int(obj.path_id)] = int(parsed.m_GameObject.m_PathID)
        elif kind == "MeshRenderer":
            renderers[int(obj.path_id)] = parsed
        elif kind == "SkinnedMeshRenderer":
            skinned_renderers[int(obj.path_id)] = parsed

    matrix_cache, active_cache = {}, {}

    def world(tid, visiting=None):
        if tid in matrix_cache:
            return matrix_cache[tid]
        visiting = set() if visiting is None else visiting
        assert tid not in visiting, f"Transform cycle at PathID {tid}"
        visiting.add(tid)
        tr = transforms[tid]
        parent = int(tr.m_Father.m_PathID)
        local = local_matrix(tr)
        result = multiply(world(parent, visiting), local) if parent else local
        visiting.remove(tid)
        matrix_cache[tid] = result
        return result

    def active(goid, visiting=None):
        if goid in active_cache:
            return active_cache[goid]
        visiting = set() if visiting is None else visiting
        assert goid not in visiting, f"GameObject cycle at PathID {goid}"
        visiting.add(goid)
        go = gameobjects.get(goid)
        result = bool(go and go.m_IsActive)
        tid = next((cid for cid in components_by_go.get(goid, []) if cid in transforms), None)
        if result and tid is not None:
            parent = int(transforms[tid].m_Father.m_PathID)
            if parent and parent in transforms:
                result = active(component_go[parent], visiting)
        visiting.remove(goid)
        active_cache[goid] = result
        return result

    staged_transforms = {int(t["path_id"]): t for t in manifest["transforms"]}
    assert set(staged_transforms) == set(transforms), "raw/staged Transform PathID sets differ"
    max_error, checked_transform_fields = 0.0, 0
    for tid, tr in transforms.items():
        staged = staged_transforms[tid]
        goid = component_go[tid]
        assert staged["gameobject_path_id"] == goid, f"Transform {tid} GameObject ref"
        assert staged["parent_path_id"] == int(tr.m_Father.m_PathID), f"Transform {tid} parent ref"
        assert staged["name"] == getattr(gameobjects[goid], "m_Name", ""), f"Transform {tid} name"
        raw_local = [vector(tr.m_LocalPosition), vector(tr.m_LocalRotation), vector(tr.m_LocalScale)]
        staged_local = [staged["local_position"], staged["local_rotation_xyzw"], staged["local_scale"]]
        for a, b in zip((v for row in raw_local for v in row), (v for row in staged_local for v in row)):
            max_error = max(max_error, abs(a-b)); checked_transform_fields += 1
            assert close(a, b), f"Transform {tid} local TRS mismatch: {a} vs {b}"
        raw_world, staged_world = world(tid), staged["world_matrix_row_major"]
        for i in range(4):
            for j in range(4):
                max_error = max(max_error, abs(raw_world[i][j]-staged_world[i][j])); checked_transform_fields += 1
                assert close(raw_world[i][j], staged_world[i][j]), f"Transform {tid} world matrix [{i},{j}]"

    staged_renderers = {int(r["renderer_path_id"]): r for r in manifest["renderers"]}
    assert set(staged_renderers) == set(renderers), "raw/staged MeshRenderer PathID sets differ"
    renderer_fields = 0
    for rid, renderer in renderers.items():
        staged = staged_renderers[rid]
        goid = int(renderer.m_GameObject.m_PathID)
        tid = next((cid for cid in components_by_go.get(goid, []) if cid in transforms), None)
        assert staged["gameobject_path_id"] == goid, f"MeshRenderer {rid} GameObject ref"
        assert staged["transform_path_id"] == tid, f"MeshRenderer {rid} Transform ref"
        assert bool(staged["active_in_hierarchy"]) == active(goid), f"MeshRenderer {rid} activeInHierarchy"
        assert bool(staged["enabled"]) == bool(renderer.m_Enabled), f"MeshRenderer {rid} enabled"
        if tid is not None:
            raw_world, staged_world = world(tid), staged["world_matrix_row_major"]
            for i in range(4):
                for j in range(4):
                    max_error = max(max_error, abs(raw_world[i][j]-staged_world[i][j])); renderer_fields += 1
                    assert close(raw_world[i][j], staged_world[i][j]), f"MeshRenderer {rid} matrix [{i},{j}]"
    staged_skinned = {int(r["renderer_path_id"]): r for r in manifest.get("skinned_renderers", [])}
    assert set(staged_skinned) == set(skinned_renderers), "raw/staged SkinnedMeshRenderer PathID sets differ"
    skinned_fields = 0
    for rid, renderer in skinned_renderers.items():
        staged = staged_skinned[rid]
        goid = int(renderer.m_GameObject.m_PathID)
        tid = next((cid for cid in components_by_go.get(goid, []) if cid in transforms), None)
        assert staged["gameobject_path_id"] == goid, f"SkinnedMeshRenderer {rid} GameObject ref"
        assert staged["transform_path_id"] == tid, f"SkinnedMeshRenderer {rid} Transform ref"
        assert bool(staged["active_in_hierarchy"]) == active(goid), f"SkinnedMeshRenderer {rid} activeInHierarchy"
        assert bool(staged["enabled"]) == bool(renderer.m_Enabled), f"SkinnedMeshRenderer {rid} enabled"
        if active(goid) and bool(renderer.m_Enabled):
            assert staged["mesh_index"] is not None, f"active SkinnedMeshRenderer {rid} lacks baked mesh"
            assert staged["pose_mode"] == "serialized_bone_pose_baked_without_animator", f"SkinnedMeshRenderer {rid} pose provenance"
            assert len(staged["material_indices"]) == len(renderer.m_Materials), f"SkinnedMeshRenderer {rid} materials"
        else:
            assert staged["mesh_index"] is None, f"inactive SkinnedMeshRenderer {rid} was baked"
        if tid is not None:
            raw_world, staged_world = world(tid), staged["world_matrix_row_major"]
            for i in range(4):
                for j in range(4):
                    max_error = max(max_error, abs(raw_world[i][j]-staged_world[i][j])); skinned_fields += 1
                    assert close(raw_world[i][j], staged_world[i][j]), f"SkinnedMeshRenderer {rid} matrix [{i},{j}]"
    digest = hashlib.sha256(scene.read_bytes()).hexdigest()
    return digest, len(transforms), len(renderers), len(skinned_renderers), checked_transform_fields, renderer_fields, skinned_fields, max_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, help="raw Unity data directory containing level1, or the level1 file")
    parser.add_argument("--manifest", type=Path, default=MANIFEST, help="world manifest to compare; defaults to the Android staged manifest")
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text())
    transforms = {t["path_id"]: t for t in data["transforms"]}
    renderers = data["renderers"]
    assert len(transforms) == data["counts"]["transforms"]
    assert all(not t["parent_path_id"] or t["parent_path_id"] in transforms for t in transforms.values())

    camera = next(c for c in data["cameras"] if c["name"] == "Main Camera")
    assert camera["path_id"] == 2060 and camera["transform_path_id"] == 1935
    assert camera["active_in_hierarchy"] and camera["enabled"] and not camera["orthographic"]
    assert (camera["field_of_view"], camera["near_clip"], camera["far_clip"]) == (60.0, 0.10000000149011612, 1000.0)
    cam_transform = transforms[1935]
    controller = transforms[1660]
    player = transforms[1541]
    assert cam_transform["parent_path_id"] == 1660 and controller["parent_path_id"] == 1541
    assert close(cam_transform["local_position"][1], 1.65)
    assert close(cam_transform["world_matrix_row_major"][1][3], 1.584)
    assert close(player["world_matrix_row_major"][1][3], -0.066)

    active = [r for r in renderers if r["active_in_hierarchy"] and r["enabled"]]
    assert len(active) == data["counts"]["renderers_active"]
    assert len(active) == 109
    # Verify the manifest's source-space AABBs map through the same reflected
    # source matrix convention used by WorldRenderer.matrix/transformBounds.
    checked = 0
    for renderer in renderers:
        if not renderer["active_in_hierarchy"] or renderer["mesh_index"] is None or renderer["mesh_index"] < 0:
            continue
        source_bounds = data["meshes"][renderer["mesh_index"]]["local_bounds"]
        world = renderer["world_matrix_row_major"]
        if not source_bounds or not renderer["world_bounds"]:
            continue
        lo, hi = source_bounds["min"], source_bounds["max"]
        points = []
        for mask in range(8):
            p = [hi[i] if mask & (1 << i) else lo[i] for i in range(3)]
            # GDX mesh Z is reflected and matrix() is S*M*S, so the resulting
            # world position is S*(source world position).
            q = [sum(world[row][col] * (p + [1])[col] for col in range(4)) for row in range(3)]
            points.append([q[0], q[1], -q[2]])
        expected = {"min": [min(p[i] for p in points) for i in range(3)],
                    "max": [max(p[i] for p in points) for i in range(3)]}
        source_bounds_world = renderer["world_bounds"]
        converted_bounds = {"min": [source_bounds_world["min"][0], source_bounds_world["min"][1], -source_bounds_world["max"][2]],
                            "max": [source_bounds_world["max"][0], source_bounds_world["max"][1], -source_bounds_world["min"][2]]}
        for side in ("min", "max"):
            assert all(close(a, b) for a, b in zip(expected[side], converted_bounds[side])), renderer["renderer_path_id"]
        checked += 1
    assert checked >= (80 if args.data else 100)
    if args.data:
        digest, transform_count, renderer_count, skinned_count, transform_fields, renderer_fields, skinned_fields, max_error = audit_raw(args.data, data)
        print(f"raw-source audit passed: scene_sha256={digest}; transforms={transform_count}; MeshRenderers={renderer_count}; SkinnedMeshRenderers={skinned_count}; transform_fields={transform_fields}; renderer_matrix_fields={renderer_fields}; skinned_matrix_fields={skinned_fields}; max_abs_error={max_error:.9g}")
    else:
        print("raw-source audit skipped: no --data supplied")
    print(f"manifest-consistency audit passed: camera PathID 2060; {len(active)} active renderers; {checked} source bounds")


if __name__ == "__main__":
    main()
