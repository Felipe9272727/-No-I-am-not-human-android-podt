#!/usr/bin/env python3
"""Stage the source-posed active level-1 skinned renderer beside v12 world assets."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSETS = ROOT / "reconstruction/android-current/app/src/main/assets"
DEFAULT_METADATA = ROOT / "reconstruction/reverse-world/skinned_baseline.json"
DEFAULT_MESH = ROOT / "reconstruction/reverse-world/skinned_level1_f2_p310_renderer2558.bin"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n", encoding="ascii")
    temporary.replace(path)


def refresh_from_source_export(source_manifest_path: Path, metadata_path: Path, mesh_path: Path) -> dict:
    """Regenerate the small staged-pose metadata and mesh from export_world.py output."""
    source_manifest_path = source_manifest_path.resolve()
    source_root = source_manifest_path.parent
    source = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    renderer = next((row for row in source.get("skinned_renderers", [])
                     if int(row.get("renderer_path_id", -1)) == 2558), None)
    if renderer is None or not renderer.get("active_in_hierarchy") or not renderer.get("enabled"):
        raise RuntimeError("source export does not contain active+enabled SkinnedMeshRenderer PathID 2558")
    if renderer.get("mesh_index") is None:
        raise RuntimeError("source export did not bake SkinnedMeshRenderer PathID 2558")
    mesh = source["meshes"][int(renderer["mesh_index"])]
    input_mesh = source_root / mesh["mesh_asset"]
    if not input_mesh.is_file() or sha256(input_mesh) != mesh.get("sha256"):
        raise RuntimeError("source export skinned mesh is missing or has the wrong hash")
    material_index = int(renderer["material_indices"][0])
    material = source["materials"][material_index]
    refs = material.get("texture_refs", [])
    texture_ref = next((row for row in refs if row.get("property") == "_BaseMap"), refs[0] if refs else None)
    if texture_ref is None:
        raise RuntimeError("source miner material has no source texture reference")
    texture = source["textures"][int(texture_ref["texture_index"])]
    old = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
    mesh_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(input_mesh, mesh_path)
    stable_mesh = dict(mesh)
    stable_mesh["mesh_asset"] = mesh_path.name
    old.update({
        "schema_version": 1,
        "source_scene_sha256": source.get("provenance", {}).get("source_scene_sha256", ""),
        "renderer": renderer,
        "source_renderers": source.get("skinned_renderers", []),
        "mesh": stable_mesh,
        "material_source_ref": material["source_ref"],
        "material_name": material.get("name", ""),
        "material_index_in_staged_v12": int(old.get("material_index_in_staged_v12", 35)),
        "texture_source_ref": texture["source_ref"],
        "texture_index_in_staged_v12": int(old.get("texture_index_in_staged_v12", 28)),
        "texture_sha256": texture["sha256"],
        "provenance": {
            "method": "weighted source skin bake using serialized Unity bone transforms, bind poses, normals, vertices, UV0 and triangle indices",
            "animator_evaluated": False,
            "source_renderer_path_id": 2558,
            "source_mesh_path_id": int(mesh["source_ref"]["path_id"]),
            "active_in_hierarchy": True,
            "enabled": True,
        },
    })
    atomic_json(metadata_path, old)
    return {"source_scene_sha256": old["source_scene_sha256"], "renderer_path_id": 2558,
            "mesh_sha256": sha256(mesh_path), "mesh_bytes": mesh_path.stat().st_size,
            "material_source_ref": material["source_ref"], "texture_source_ref": texture["source_ref"]}


def stage_skinned_world(assets_root: Path = DEFAULT_ASSETS, metadata_path: Path = DEFAULT_METADATA,
                        mesh_path: Path = DEFAULT_MESH) -> dict:
    world_root = assets_root / "world"
    manifest_path = world_root / "world_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"staged world manifest is missing: {manifest_path}")
    if not metadata_path.is_file() or not mesh_path.is_file():
        raise FileNotFoundError("source skinned-renderer metadata or baked mesh is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    renderer_id = int(metadata["renderer"]["renderer_path_id"])
    previous = [int(row["renderer_path_id"]) for row in manifest.get("skinned_renderers", [])]
    existing_index = None
    if renderer_id in previous:
        row = next(row for row in manifest["skinned_renderers"] if int(row["renderer_path_id"]) == renderer_id)
        if row.get("mesh_index") is None:
            raise RuntimeError(f"skinned renderer PathID {renderer_id} is present without its source mesh")
        existing_index = int(row["mesh_index"])
        mesh_row = manifest["meshes"][existing_index]
        asset = assets_root / mesh_row.get("android_asset", "")
        if (asset.is_file() and mesh_row.get("sha256") == metadata["mesh"]["sha256"]
                and sha256(asset) == mesh_row.get("android_sha256")):
            return {"renderer_path_id": renderer_id, "mesh_index": existing_index,
                    "mesh_count": len(manifest["meshes"]), "skinned_renderer_count": len(manifest["skinned_renderers"]),
                    "already_staged": True, "mesh_bytes": asset.stat().st_size,
                    "mesh_sha256": sha256(asset), "manifest": str(manifest_path)}
    base_count = len(manifest.get("meshes", [])) - (1 if existing_index is not None else 0)
    if base_count != 100:
        raise RuntimeError(f"expected the unchanged v12 base of 100 meshes; got {base_count}")

    material_ref = metadata["material_source_ref"]
    material_index = next((i for i, row in enumerate(manifest.get("materials", []))
                           if row.get("source_ref") == material_ref), None)
    if material_index is None:
        raise RuntimeError(f"source material {material_ref} is absent from the staged v12 manifest")
    if material_index != int(metadata["material_index_in_staged_v12"]):
        raise RuntimeError(f"staged material index drifted: expected {metadata['material_index_in_staged_v12']}, got {material_index}")
    texture_ref = metadata["texture_source_ref"]
    texture_index = next((i for i, row in enumerate(manifest.get("textures", []))
                          if row.get("source_ref") == texture_ref), None)
    if texture_index is None or texture_index != int(metadata["texture_index_in_staged_v12"]):
        raise RuntimeError(f"source texture {texture_ref} is absent or its index changed")
    texture_row = manifest["textures"][texture_index]
    if texture_row.get("sha256") != metadata["texture_sha256"]:
        raise RuntimeError("source texture hash differs from the previously verified staged source")
    texture_asset = texture_row.get("android_asset", "")
    if not texture_asset or not (assets_root / texture_asset).is_file():
        raise RuntimeError(f"staged source material texture is missing: {texture_asset}")

    mesh = metadata["mesh"]
    mesh_hash = sha256(mesh_path)
    if mesh_hash != mesh["sha256"]:
        raise RuntimeError("baked skinned mesh hash mismatch")
    expected_bytes = int(mesh["vertex_count"]) * int(mesh["vertex_stride_bytes"]) + int(mesh["index_count"]) * 4
    if mesh_path.stat().st_size != expected_bytes:
        raise RuntimeError(f"baked mesh byte length mismatch: expected {expected_bytes}, got {mesh_path.stat().st_size}")
    with mesh_path.open("rb") as source:
        import struct
        source.seek(int(mesh["vertex_count"]) * int(mesh["vertex_stride_bytes"]))
        indices = struct.unpack("<" + "I" * int(mesh["index_count"]), source.read(int(mesh["index_count"]) * 4))
    if not indices or max(indices) >= int(mesh["vertex_count"]):
        raise RuntimeError("baked skinned mesh contains an invalid index")

    relative = Path("models") / mesh_path.name
    target = world_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    shutil.copyfile(mesh_path, temporary)
    if sha256(temporary) != mesh_hash:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("staged mesh hash mismatch after copy")
    temporary.replace(target)

    new_mesh = dict(mesh)
    new_mesh.update({
        "mesh_asset": relative.as_posix(),
        "source_sha256": mesh_hash,
        "android_asset": f"world/{relative.as_posix()}",
        "android_vertex_count": int(mesh["vertex_count"]),
        "android_index_count": int(mesh["index_count"]),
        "android_sha256": mesh_hash,
    })
    mesh_index = existing_index if existing_index is not None else len(manifest["meshes"])
    if existing_index is None:
        manifest["meshes"].append(new_mesh)
    else:
        manifest["meshes"][mesh_index] = new_mesh

    source_renderers = metadata.get("source_renderers", [metadata["renderer"]])
    staged_renderers = []
    for row in source_renderers:
        value = dict(row)
        if int(value["renderer_path_id"]) == renderer_id:
            value.update({"mesh_index": mesh_index, "material_indices": [material_index],
                          "pose_mode": "serialized_bone_pose_baked_without_animator"})
        else:
            value.update({"mesh_index": None, "material_indices": [],
                          "pose_mode": "source_mesh_not_baked_inactive"})
        staged_renderers.append(value)
    manifest["skinned_renderers"] = staged_renderers
    counts = manifest.setdefault("counts", {})
    counts["skinned_mesh_renderers"] = len(staged_renderers)
    counts["skinned_renderers_active"] = sum(bool(row["active_in_hierarchy"] and row["enabled"]) for row in staged_renderers)
    counts["renderers_active_total"] = int(counts.get("renderers_active", 0)) + counts["skinned_renderers_active"]
    manifest.setdefault("exclusions", [])
    manifest["exclusions"] = [item for item in manifest["exclusions"] if "SkinnedMeshRenderer" not in item]
    manifest["exclusions"].append("SkinnedMeshRenderer geometry is baked at serialized bone transforms; Animator playback is not evaluated.")
    atomic_json(manifest_path, manifest)
    return {"renderer_path_id": renderer_id, "mesh_index": mesh_index, "base_mesh_count": mesh_index,
            "mesh_count": len(manifest["meshes"]), "skinned_renderer_count": len(staged_renderers),
            "active_skinned_renderers": counts["skinned_renderers_active"], "material_index": material_index,
            "texture_index": texture_index, "mesh_bytes": target.stat().st_size, "mesh_sha256": mesh_hash,
            "manifest": str(manifest_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-root", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--mesh", type=Path, default=DEFAULT_MESH)
    parser.add_argument("--source-export", type=Path,
                        help="fresh export_world.py manifest; refreshes the tracked pose mesh and metadata before staging")
    args = parser.parse_args()
    if args.source_export:
        print(json.dumps({"refreshed_source_pose": refresh_from_source_export(args.source_export, args.metadata, args.mesh)}, indent=2))
    print(json.dumps(stage_skinned_world(args.assets_root, args.metadata, args.mesh), indent=2))


if __name__ == "__main__":
    main()
