#!/usr/bin/env python3
"""Export the authored Naperdysh cat as a statically skinned preview mesh.

This reads Unity serialized assets only. It never runs the original game or
loads its executable assemblies. The preview uses CatViewProvider.DayPositions
entry zero and the source bone transforms at the serialized rest pose; it does
not pretend to reproduce the Animator's Sit/Lay clips.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import struct
import tempfile
import zipfile
from pathlib import Path

import UnityPy
import numpy as np
from PIL import Image
from UnityPy.helpers.MeshHelper import MeshHandler

ROOT = Path(__file__).resolve().parents[2]
LEVEL_FILE = "level1"
SHARED_FILE = "sharedassets1.assets"
RESS_MEMBER = (
    "No.Im.not.a.Human.v1.3.18/No.Im.not.a.Human.v1.3.18/"
    "NoImNotAHuman_Data/sharedassets1.assets.resS"
)
CAT_GAME_OBJECT = 477
CAT_ROOT_TRANSFORM = 1679
CAT_PROVIDER_COMPONENT = 3832
CAT_SKINNED_RENDERER = 2557
CAT_MESH = 304
CAT_MATERIAL = 30
CAT_BASE_TEXTURE = 92


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def vector(value, names: str) -> np.ndarray:
    return np.array([float(getattr(value, name)) for name in names], dtype=np.float64)


def unity_matrix(value) -> np.ndarray:
    return np.array(
        [[float(getattr(value, f"e{row}{col}")) for col in range(4)] for row in range(4)],
        dtype=np.float64,
    )


def local_matrix(transform) -> np.ndarray:
    p = vector(transform.m_LocalPosition, "xyz")
    x, y, z, w = vector(transform.m_LocalRotation, "xyzw")
    scale = vector(transform.m_LocalScale, "xyz")
    rotation = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )
    result = np.eye(4, dtype=np.float64)
    result[:3, :3] = rotation @ np.diag(scale)
    result[:3, 3] = p
    return result


def parse_cat_positions(raw: bytes) -> dict:
    # MonoBehaviour serialized prefix: CatViewProvider's Cat PPtr is at 32,
    # DayPositions begins at 44, and NightPositions follows the 20-byte rows.
    cat_file_id = struct.unpack_from("<i", raw, 32)[0]
    cat_path_id = struct.unpack_from("<q", raw, 36)[0]
    if cat_file_id != 0 or cat_path_id != 5254:
        raise ValueError(f"unexpected CatViewProvider Cat reference: {cat_file_id}/{cat_path_id}")
    cursor = 44
    result = {"day": [], "night": []}
    for key in ("day", "night"):
        count = struct.unpack_from("<I", raw, cursor)[0]
        cursor += 4
        if count > 64 or cursor + count * 20 > len(raw):
            raise ValueError(f"invalid CatPosition array {key}: count={count}")
        for _ in range(count):
            position = struct.unpack_from("<3f", raw, cursor)
            rotation = struct.unpack_from("<f", raw, cursor + 12)[0]
            animation = struct.unpack_from("<i", raw, cursor + 16)[0]
            result[key].append({
                "position": [round(x, 6) for x in position],
                "rotation_y_degrees": round(rotation, 6),
                "animation_enum": animation,
                "animation_name": {0: "Sit", 1: "Lay", 2: "Stand", 3: "Walk", 4: "Play"}.get(animation),
            })
            cursor += 20
    if cursor != len(raw):
        raise ValueError(f"unexpected trailing CatViewProvider bytes: consumed {cursor}, raw {len(raw)}")
    return result


def export(data: Path, out: Path, original_archive: Path | None) -> None:
    data = data.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ninah-cat3d-") as scratch:
        scratch_path = Path(scratch)
        for filename in (LEVEL_FILE, "globalgamemanagers.assets", "sharedassets0.assets"):
            source = data / filename
            if not source.is_file():
                raise FileNotFoundError(source)
            (scratch_path / filename).symlink_to(source)
        shared_source = data / SHARED_FILE
        if not shared_source.is_file():
            raise FileNotFoundError(shared_source)
        # Copy the container beside its .resS because UnityPy resolves streamed
        # data relative to the real asset-file path, not the symlink location.
        shutil.copyfile(shared_source, scratch_path / SHARED_FILE)
        resource = data / f"{SHARED_FILE}.resS"
        if resource.is_file():
            (scratch_path / resource.name).symlink_to(resource)
            resource_source = str(resource)
        elif original_archive:
            with zipfile.ZipFile(original_archive) as archive:
                try:
                    member = archive.getinfo(RESS_MEMBER)
                except KeyError as error:
                    raise FileNotFoundError(f"original archive lacks {RESS_MEMBER}") from error
                resource = scratch_path / f"{SHARED_FILE}.resS"
                with archive.open(member) as source, resource.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                resource_source = f"{original_archive}:{RESS_MEMBER}"
        else:
            raise FileNotFoundError(
                f"missing {data / (SHARED_FILE + '.resS')}; provide --original-archive to read the source texture"
            )

        env = UnityPy.Environment()
        env.load_file(str(scratch_path / LEVEL_FILE))
        env.load_file(str(scratch_path / SHARED_FILE))
        env.load_file(str(scratch_path / "sharedassets0.assets"))
        env.load_file(str(scratch_path / f"{SHARED_FILE}.resS"))
        scene = next(asset for asset in env.files.values() if Path(asset.name).name == LEVEL_FILE)
        shared = next(asset for asset in env.files.values() if Path(asset.name).name == SHARED_FILE)
        scene_by_id = {int(obj.path_id): obj for obj in scene.objects.values()}
        shared_by_id = {int(obj.path_id): obj for obj in shared.objects.values()}

        provider = scene_by_id[CAT_PROVIDER_COMPONENT]
        positions = parse_cat_positions(provider.get_raw_data())
        renderer = scene_by_id[CAT_SKINNED_RENDERER].read()
        mesh_obj = shared_by_id[CAT_MESH]
        mesh = mesh_obj.read()
        handler = MeshHandler(mesh)
        handler.process()
        if len(renderer.m_Bones) != len(mesh.m_BindPose):
            raise ValueError("cat bone and bind-pose counts do not match")
        if len(handler.m_BoneWeights or []) != len(handler.m_Vertices or []):
            raise ValueError("UnityPy did not decode all Cat bone weights")
        if len(handler.m_BoneIndices or []) != len(handler.m_Vertices or []):
            raise ValueError("UnityPy did not decode all Cat bone indices")

        transforms = {
            int(obj.path_id): obj.read()
            for obj in scene.objects.values()
            if obj.type.name == "Transform"
        }
        cache: dict[int, np.ndarray] = {}

        def world_matrix(path_id: int) -> np.ndarray:
            if path_id in cache:
                return cache[path_id]
            transform = transforms[path_id]
            matrix = local_matrix(transform)
            parent = int(transform.m_Father.path_id) if transform.m_Father else 0
            if parent in transforms:
                matrix = world_matrix(parent) @ matrix
            cache[path_id] = matrix
            return matrix

        cat_world = world_matrix(CAT_ROOT_TRANSFORM)
        cat_world_inverse = np.linalg.inv(cat_world)
        bone_matrices = []
        for bone, bind_pose in zip(renderer.m_Bones, mesh.m_BindPose):
            if int(bone.path_id) not in transforms:
                raise ValueError(f"missing cat bone transform {bone.path_id}")
            bone_matrices.append(cat_world_inverse @ world_matrix(int(bone.path_id)) @ unity_matrix(bind_pose))

        vertices = np.asarray(handler.m_Vertices, dtype=np.float64)
        normals = np.asarray(handler.m_Normals, dtype=np.float64)
        weights = np.asarray(handler.m_BoneWeights, dtype=np.float64)
        bone_indices = np.asarray(handler.m_BoneIndices, dtype=np.int64)
        uvs = np.asarray(handler.m_UV0, dtype=np.float64)
        if len(normals) != len(vertices) or len(uvs) != len(vertices):
            raise ValueError("cat mesh is missing normals or UV0")
        if not all(np.isfinite(values).all() for values in (vertices, normals, weights, uvs)):
            raise ValueError("cat mesh contains non-finite source vertex data")
        if not np.allclose(weights.sum(axis=1), 1.0, atol=1e-4):
            raise ValueError("cat vertex skin weights do not sum to one")
        if np.any(bone_indices < 0) or np.any(bone_indices >= len(renderer.m_Bones)):
            raise ValueError("cat mesh references an invalid source bone")
        positions_out = np.zeros((len(vertices), 3), dtype=np.float64)
        normals_out = np.zeros((len(vertices), 3), dtype=np.float64)
        for index, (vertex, normal, vertex_weights, vertex_bones) in enumerate(
            zip(vertices, normals, weights, bone_indices)
        ):
            p = np.r_[vertex[:3], 1.0]
            for weight, bone_index in zip(vertex_weights, vertex_bones):
                if weight <= 0:
                    continue
                matrix = bone_matrices[int(bone_index)]
                positions_out[index] += weight * (matrix @ p)[:3]
                normals_out[index] += weight * (matrix[:3, :3] @ normal[:3])
            length = float(np.linalg.norm(normals_out[index]))
            if length:
                normals_out[index] /= length

        triangles: list[int] = []
        for submesh in handler.get_triangles():
            for triangle in submesh:
                if len(triangle) == 3:
                    triangles.extend(int(value) for value in triangle)
        if not triangles or len(triangles) % 3:
            raise ValueError("cat mesh has no valid triangle list")
        if max(triangles) >= len(vertices):
            raise ValueError("cat mesh triangle refers to an invalid vertex")
        if not np.isfinite(positions_out).all() or not np.isfinite(normals_out).all():
            raise ValueError("baked cat mesh contains non-finite positions or normals")

        model = bytearray()
        for position, normal, uv in zip(positions_out, normals_out, uvs):
            model.extend(struct.pack("<8f", *position, *normal, *uv[:2]))
        for triangle_index in triangles:
            model.extend(struct.pack("<I", triangle_index))
        model_path = out / "cat3d.bin"
        model_path.write_bytes(model)

        material = shared_by_id[CAT_MATERIAL].read()
        texture = shared_by_id[CAT_BASE_TEXTURE].read()
        image = texture.image.convert("RGBA")
        texture_path = out / "cat_koshka.png"
        image.save(texture_path, format="PNG", optimize=False, compress_level=9)
        saved = material.m_SavedProperties
        colors = {
            str(name): [float(value.r), float(value.g), float(value.b), float(value.a)]
            for name, value in saved.m_Colors
        }
        floats = {str(name): float(value) for name, value in (saved.m_Floats or [])}
        textures = []
        for name, env_texture in saved.m_TexEnvs:
            ref = env_texture.m_Texture
            if ref and int(ref.m_PathID):
                textures.append({
                    "property": str(name),
                    "path_id": int(ref.m_PathID),
                    "name": str(getattr(ref.read(), "m_Name", "")),
                    "scale": [float(env_texture.m_Scale.x), float(env_texture.m_Scale.y)],
                    "offset": [float(env_texture.m_Offset.x), float(env_texture.m_Offset.y)],
                })
        preview = positions["day"][0]
        preview_yaw = math.radians(preview["rotation_y_degrees"])
        cosine, sine = math.cos(preview_yaw), math.sin(preview_yaw)
        preview_matrix = [
            [cosine, 0.0, sine, preview["position"][0]],
            [0.0, 1.0, 0.0, preview["position"][1]],
            [-sine, 0.0, cosine, preview["position"][2]],
            [0.0, 0.0, 0.0, 1.0],
        ]
        box = {
            "min": [round(float(x), 6) for x in positions_out.min(axis=0)],
            "max": [round(float(x), 6) for x in positions_out.max(axis=0)],
        }
        result = {
            "schema_version": 1,
            "provenance": {
                "method": "UnityPy static extraction and weighted source bone-matrix bake",
                "executed_original_binaries": False,
                "scene_file": LEVEL_FILE,
                "mesh_file": SHARED_FILE,
                "resource_file": resource_source,
                "source_objects": {
                    "cat_game_object": {"path_id": CAT_GAME_OBJECT, "name": "Naperdysh_idle"},
                    "cat_instance_component": {"path_id": 5254, "class": "CatInstance"},
                    "cat_provider_component": {"path_id": CAT_PROVIDER_COMPONENT, "class": "CatViewProvider"},
                    "skinned_mesh_renderer": {"path_id": CAT_SKINNED_RENDERER, "game_object_path_id": 439},
                    "mesh": {"path_id": CAT_MESH, "name": str(mesh.m_Name)},
                    "material": {"path_id": CAT_MATERIAL, "name": str(material.m_Name)},
                    "albedo_texture": {"path_id": CAT_BASE_TEXTURE, "name": str(texture.m_Name)},
                },
                "source_sha256": {
                    "level1": sha256(data / LEVEL_FILE),
                    "sharedassets1.assets": sha256(data / SHARED_FILE),
                    "mesh_asset": hashlib.sha256(model).hexdigest(),
                    "albedo_png": sha256(texture_path),
                },
            },
            "visibility": {
                "scene_active_self": False,
                "source_gate": "CatSaveData.IsActive; ActivateCat enables the CatInstance GameObject",
                "purpose": "explicit debug preview only; the native first-morning campaign does not activate the cat",
            },
            "preview_pose": {
                "source_position_array": "CatViewProvider.DayPositions[0]",
                "source_position_array_offset": 44,
                **preview,
                "world_matrix_row_major": [[round(value, 8) for value in row] for row in preview_matrix],
                "pose_bake": "serialized source bone transforms with mesh bind poses and vertex weights",
                "animation_playback": "not evaluated; source CatPosition animation is Sit",
                "controller_clips": ["SIT", "LAY"],
            },
            "positions": positions,
            "mesh": {
                "asset": model_path.name,
                "vertex_count": int(len(vertices)),
                "index_count": int(len(triangles)),
                "triangle_count": int(len(triangles) // 3),
                "vertex_stride_bytes": 32,
                "vertex_layout": ["position_f32x3", "normal_f32x3", "uv0_f32x2"],
                "index_type": "uint32_le",
                "local_bounds": box,
                "sha256": hashlib.sha256(model).hexdigest(),
                "source_mesh_vertex_count": int(mesh.m_VertexData.m_VertexCount),
                "source_bones": int(len(renderer.m_Bones)),
                "source_bindposes": int(len(mesh.m_BindPose)),
                "source_skin_weights": int(len(handler.m_BoneWeights)),
            },
            "material": {
                "name": str(material.m_Name),
                "shader": str(material.m_Shader.read().m_ParsedForm.m_Name),
                "source_ref": {"file_id": 2, "path_id": CAT_MATERIAL},
                "color": colors.get("_BaseColor", [1, 1, 1, 1]),
                "colors": colors,
                "float_properties": floats,
                "custom_render_queue": int(material.m_CustomRenderQueue),
                "string_tags": {str(k): str(v) for k, v in material.stringTagMap},
                "texture_refs": textures,
                "texture_asset": texture_path.name,
                "texture_dimensions": list(image.size),
                "texture_mode": image.mode,
                "texture_sha256": sha256(texture_path),
                "sampler": {
                    "filter_mode": int(texture.m_TextureSettings.m_FilterMode),
                    "wrap_u": int(texture.m_TextureSettings.m_WrapU),
                    "wrap_v": int(texture.m_TextureSettings.m_WrapV),
                    "aniso": int(texture.m_TextureSettings.m_Aniso),
                },
                "alpha_clip": floats.get("_AlphaClip", 0.0) > 0.5,
                "alpha_cutoff": floats.get("_Cutoff", 0.5),
                "cull": int(floats.get("_Cull", 2)),
                "z_write": floats.get("_ZWrite", 1.0) > 0.5,
            },
        }
        result["mesh"]["android_asset"] = f"world/{model_path.name}"
        result["material"]["android_asset"] = f"world/{texture_path.name}"
        result["source"] = {
            "manifest": "cat3d_manifest.json",
            "mesh_asset": f"world/{model_path.name}",
            "texture_asset": f"world/{texture_path.name}",
        }
        manifest_path = out / "cat3d_manifest.json"
        manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({
            "manifest": str(manifest_path),
            "vertex_count": len(vertices),
            "triangles": len(triangles) // 3,
            "positions": positions,
            "preview": preview,
            "mesh_bytes": len(model),
            "texture_bytes": texture_path.stat().st_size,
            "mesh_sha256": hashlib.sha256(model).hexdigest(),
            "texture_sha256": sha256(texture_path),
        }, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="static Unity data directory containing level1 and sharedassets1.assets")
    parser.add_argument("--out", type=Path, default=ROOT / "reconstruction/reverse-world/cat3d")
    parser.add_argument("--original-archive", type=Path, help="original.zip, used only to read sharedassets1.assets.resS texture bytes")
    args = parser.parse_args()
    export(args.data, args.out, args.original_archive)


if __name__ == "__main__":
    main()
