#!/usr/bin/env python3
"""Export source-backed DoorTrigger fields and AnimatedImage frame lists.

Static UnityPy parsing only. This reads Unity serialized assets, C# enum/data
evidence, and retained JSON manifests; it never imports or runs game code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
from pathlib import Path

import UnityPy

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "reconstruction/reverse-animations/animation_manifest.json"
ROOMS = {0: "Kitchen", 1: "Office", 2: "BigRoom", 3: "Bathroom", 4: "Pantry", 5: "Entrance", 6: "Bedroom"}
CYCLES = {0: "PlayOnce", 1: "Cycle", 2: "FixLastFrame"}


def pp(raw: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<iq", raw, offset)


def f32(raw: bytes, offset: int) -> float:
    value = struct.unpack_from("<f", raw, offset)[0]
    if not math.isfinite(value):
        raise ValueError(f"non-finite float at offset {offset}")
    return round(value, 7)


def vec(v) -> list[float]:
    if isinstance(v, dict):
        return [round(float(v[k]), 7) for k in ("x", "y", "z")]
    return [round(float(v.x), 7), round(float(v.y), 7), round(float(v.z), 7)]


def quat(v) -> list[float]:
    if isinstance(v, dict):
        return [round(float(v[k]), 7) for k in ("x", "y", "z", "w")]
    return [round(float(v.x), 7), round(float(v.y), 7), round(float(v.z), 7), round(float(v.w), 7)]


def local_matrix(transform: dict) -> list[list[float]]:
    p, q, s = vec(transform["m_LocalPosition"]), quat(transform["m_LocalRotation"]), vec(transform["m_LocalScale"])
    x, y, z, w = q
    sx, sy, sz = s
    return [
        [(1 - 2 * (y * y + z * z)) * sx, 2 * (x * y - z * w) * sy, 2 * (x * z + y * w) * sz, p[0]],
        [2 * (x * y + z * w) * sx, (1 - 2 * (x * x + z * z)) * sy, 2 * (y * z - x * w) * sz, p[1]],
        [2 * (x * z - y * w) * sx, 2 * (y * z + x * w) * sy, (1 - 2 * (x * x + y * y)) * sz, p[2]],
        [0, 0, 0, 1],
    ]


def multiply(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="Extracted NoImNotAHuman_Data folder")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--emotion-registry", type=Path, default=ROOT / "reconstruction/reverse-characters/emotion_registry.json")
    ap.add_argument("--stage-extras", action="store_true", help="write missing scene AnimatedImage PNGs directly to app assets/ui/exported_images")
    args = ap.parse_args()
    level_files = [f"level{i}" for i in range(7) if (args.data / f"level{i}").is_file()]
    for filename in (*level_files, "globalgamemanagers", "globalgamemanagers.assets", "sharedassets0.assets", "sharedassets1.assets"):
        if not (args.data / filename).is_file():
            raise SystemExit(f"missing required static Unity file: {args.data / filename}")

    env = UnityPy.Environment()
    static_files = [*level_files, "globalgamemanagers", "globalgamemanagers.assets", "sharedassets0.assets", "sharedassets1.assets"]
    if args.stage_extras:
        # Sprite textures are commonly external streamed resources. Register
        # only available resource companions; the readers remain lazy.
        static_files.extend(filename for filename in (
            "sharedassets0.assets.resS", "sharedassets1.assets.resS", "sharedassets0.resource",
            "resources.assets", "resources.assets.resS", "sharedassets3.resource"
        ) if (args.data / filename).is_file())
    for filename in static_files:
        env.load_file(str(args.data / filename))
    files = {Path(asset.name).name: asset for asset in env.files.values() if hasattr(asset, "name")}
    scene = files["level1"]
    gm = files["globalgamemanagers.assets"]
    build_settings = next((o.read() for o in files["globalgamemanagers"].objects.values() if o.type.name == "BuildSettings"), None)
    build_scenes = list(getattr(build_settings, "scenes", []) or [])
    scene_asset_paths = {f"level{index}": path for index, path in enumerate(build_scenes)}
    externals = {index: Path(identifier.path).name for index, identifier in enumerate(scene.externals, start=1)}
    all_scene_transforms = {}
    all_scene_gameobjects = {}
    all_scene_components = {}
    for scene_filename in level_files:
        scene_file = files[scene_filename]
        scene_gameobjects = {int(o.path_id): o.read_typetree() for o in scene_file.objects.values() if o.type.name == "GameObject"}
        scene_transforms = {int(o.path_id): o.read_typetree() for o in scene_file.objects.values() if o.type.name in ("Transform", "RectTransform")}
        all_scene_gameobjects[scene_filename] = scene_gameobjects
        all_scene_transforms[scene_filename] = scene_transforms
        all_scene_components[scene_filename] = {int(o.path_id): o for o in scene_file.objects.values()}

    scripts = {}
    for obj in gm.objects.values():
        if obj.type.name != "MonoScript":
            continue
        data = obj.read()
        namespace = str(data.m_Namespace)
        scripts[int(obj.path_id)] = f"{namespace}.{data.m_ClassName}" if namespace else str(data.m_ClassName)

    gameobjects = {}
    transforms = {}
    for obj in scene.objects.values():
        if obj.type.name == "GameObject":
            data = obj.read_typetree()
            gameobjects[int(obj.path_id)] = data
        elif obj.type.name in ("Transform", "RectTransform"):
            transforms[int(obj.path_id)] = obj.read_typetree()

    go_for_transform = {int(data["m_GameObject"]["m_PathID"]): path_id for path_id, data in transforms.items()}

    def world_matrix(transform_id: int) -> list[list[float]]:
        transform = transforms[transform_id]
        local = local_matrix(transform)
        parent = int(transform["m_Father"]["m_PathID"])
        return multiply(world_matrix(parent), local) if parent else local
    sprite_names = {}
    for filename in ("sharedassets0.assets", "sharedassets1.assets"):
        asset = files[filename]
        for obj in asset.objects.values():
            if obj.type.name == "Sprite":
                try:
                    sprite_names[(filename, int(obj.path_id))] = str(obj.read().m_Name)
                except Exception:
                    pass

    def safe_filename_part(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")[:90] or "unnamed"

    def resolve_pp(ref: tuple[int, int]) -> dict:
        file_id, path_id = ref
        source = "level1" if file_id == 0 else externals.get(file_id)
        return {"file_id": file_id, "path_id": path_id, "file": source}

    def go_name(goid: int) -> str:
        return str(gameobjects.get(goid, {}).get("m_Name", ""))

    def scene_renderers(scene_name: str, game_object_id: int) -> list[dict]:
        source_scene = files[scene_name]
        go = all_scene_gameobjects[scene_name][game_object_id]
        component_ids = [int(c["component"]["m_PathID"]) for c in go["m_Component"]]
        output = []
        for component_id in component_ids:
            component = all_scene_components[scene_name].get(component_id)
            if not component or component.type.name != "MeshRenderer":
                continue
            filter_obj = next((all_scene_components[scene_name].get(cid) for cid in component_ids
                               if all_scene_components[scene_name].get(cid)
                               and all_scene_components[scene_name][cid].type.name == "MeshFilter"), None)
            mesh_ref = None
            mesh_name = None
            if filter_obj:
                filter_data = filter_obj.read_typetree()
                p = filter_data.get("m_Mesh", {})
                mesh_ref = {"file_id": int(p.get("m_FileID", 0)), "path_id": int(p.get("m_PathID", 0))}
                source_name = scene_name if mesh_ref["file_id"] == 0 else {i: Path(x.path).name for i, x in enumerate(source_scene.externals, start=1)}.get(mesh_ref["file_id"])
                mesh_name = getattr(files.get(source_name, object()).objects.get(mesh_ref["path_id"]) if source_name in files else None, "type", None)
                if mesh_name:
                    mesh_name = mesh_name.name
            output.append({"renderer_path_id": component_id, "mesh_filter_path_id": int(filter_obj.path_id) if filter_obj else None,
                           "mesh_ref": mesh_ref, "mesh_type": mesh_name})
        return output

    def subtree_renderers(scene_name: str, root_transform_id: int) -> list[dict]:
        transform_map = all_scene_transforms[scene_name]
        queue = [root_transform_id]
        records = []
        seen = set()
        while queue:
            transform_id = queue.pop(0)
            if transform_id in seen or transform_id not in transform_map:
                continue
            seen.add(transform_id)
            transform = transform_map[transform_id]
            game_object_id = int(transform["m_GameObject"]["m_PathID"])
            for record in scene_renderers(scene_name, game_object_id):
                records.append({"transform_path_id": transform_id, "game_object_path_id": game_object_id,
                                "game_object_name": str(all_scene_gameobjects[scene_name][game_object_id].get("m_Name", "")),
                                **record})
            queue.extend(int(child["m_PathID"]) for child in transform["m_Children"])
        return records

    def collider_details(scene_name: str, collider_ref: dict) -> dict:
        if collider_ref["file_id"] != 0:
            return {**collider_ref, "resolved": False}
        component = all_scene_components[scene_name].get(collider_ref["path_id"])
        if not component:
            return {**collider_ref, "resolved": False}
        try:
            data = component.read_typetree()
        except Exception:
            data = {}
        collider_go = int(data.get("m_GameObject", {}).get("m_PathID", 0))
        details = {**collider_ref, "resolved": True, "class": component.type.name,
                   "game_object_path_id": collider_go,
                   "game_object_name": go_name(collider_go) if scene_name == "level1" else str(all_scene_gameobjects[scene_name].get(collider_go, {}).get("m_Name", "")),
                   "enabled": bool(data.get("m_Enabled", True))}
        for key in ("m_IsTrigger", "m_Center", "m_Size", "m_Radius", "m_Height", "m_Direction"):
            if key in data:
                value = data[key]
                details[key[2:].lower()] = vec(value) if key in ("m_Center", "m_Size") else value
        return details

    doors = []
    animated_images = []
    for obj in scene.objects.values():
        if obj.type.name != "MonoBehaviour":
            continue
        raw = obj.get_raw_data()
        script_path = struct.unpack_from("<q", raw, 20)[0]
        cls = scripts.get(script_path)
        if cls not in {"DoorTrigger", "_Code.Utils.UI.ImageAnimating.AnimatedImage"}:
            continue
        header = obj.read(check_read=False)
        goid = int(header.m_GameObject.m_PathID)
        component_base = {
            "component_path_id": int(obj.path_id),
            "game_object_path_id": goid,
            "game_object_name": go_name(goid),
            "enabled": bool(raw[12]),
            "script_path_id": int(script_path),
            "class": cls,
            "raw_size": len(raw),
        }
        if cls == "DoorTrigger":
            # The managed fields are serialized after variable-length inherited
            # LocalizedString data. Locate the one PPtr to a Transform whose
            # GameObject is the authored door leaf. The following schema is from
            # DoorTrigger.cs; PPtr serial order is fileID (i32), pathID (i64).
            candidates = []
            for tid, tdata in transforms.items():
                target_go = int(tdata["m_GameObject"]["m_PathID"])
                target_name = go_name(target_go)
                if not target_name.startswith("Дверь"):
                    continue
                marker = struct.pack("<iq", 0, int(tid))
                pos = raw.rfind(marker)
                if pos >= 0:
                    candidates.append((pos, int(tid), target_name))
            if not candidates:
                raise ValueError(f"DoorTrigger {obj.path_id} has no serialized door-pivot Transform reference")
            pivot_offset, pivot_id, pivot_name = max(candidates)
            field_offset = pivot_offset + 12
            angle = f32(raw, field_offset)
            slight = f32(raw, field_offset + 4)
            duration = f32(raw, field_offset + 8)
            linked_value = struct.unpack_from("<i", raw, field_offset + 12)[0]
            collider_ref = pp(raw, field_offset + 16)
            close_speed = f32(raw, field_offset + 28)
            pivot = transforms[pivot_id]
            pivot_go = int(pivot["m_GameObject"]["m_PathID"])
            parent_id = int(pivot["m_Father"]["m_PathID"])
            pivot_world = world_matrix(pivot_id)
            collider_resolved = resolve_pp(collider_ref)
            renderers = subtree_renderers("level1", pivot_id)
            resolved_collider = collider_details("level1", {"file_id": collider_ref[0], "path_id": collider_ref[1], "file": "level1" if collider_ref[0] == 0 else externals.get(collider_ref[0])})
            raycast_ref = pp(raw, 56)
            raycast_obj = scene.objects.get(raycast_ref[1]) if raycast_ref[0] == 0 else None
            raycast_data = raycast_obj.read(check_read=False) if raycast_obj else None
            raycast_go = int(raycast_data.m_GameObject.m_PathID) if raycast_data else 0
            raycast_raw = raycast_obj.get_raw_data() if raycast_obj else b""
            raycast_script_id = struct.unpack_from("<q", raycast_raw, 20)[0] if len(raycast_raw) >= 28 else 0
            raycast_components = []
            if raycast_go in gameobjects:
                for component in gameobjects[raycast_go]["m_Component"]:
                    component_id = int(component["component"]["m_PathID"])
                    component_obj = scene.objects.get(component_id)
                    if component_obj and component_obj.type.name in ("BoxCollider", "SphereCollider", "CapsuleCollider", "MeshCollider"):
                        raycast_components.append(collider_details("level1", {"file_id": 0, "path_id": component_id, "file": "level1"}))
            doors.append({
                **component_base,
                "door_pivot": {
                    "transform_path_id": pivot_id,
                    "game_object_path_id": pivot_go,
                    "game_object_name": pivot_name,
                    "parent_transform_path_id": parent_id,
                    "local_position": vec(pivot["m_LocalPosition"]),
                    "local_rotation_xyzw": quat(pivot["m_LocalRotation"]),
                    "local_scale": vec(pivot["m_LocalScale"]),
                    "world_matrix_row_major": [[round(float(v), 7) for v in row] for row in pivot_world],
                    "world_position": [round(float(pivot_world[i][3]), 7) for i in range(3)],
                    "renderers_on_pivot": scene_renderers("level1", pivot_go),
                    "descendant_renderers": renderers,
                    "world_renderer_path_id": renderers[0]["renderer_path_id"] if renderers else None,
                    "rotation_property_captured_by_Awake": "Transform.rotation (world quaternion) converted to positive Euler degrees",
                },
                "serialized_fields": {
                    "pivot_pptr_raw_offset": pivot_offset,
                    "room_action_raycast_target_path_id": raycast_ref[1],
                    "room_action_raycast_target": {
                        "component_path_id": raycast_ref[1],
                        "class": scripts.get(raycast_script_id),
                        "game_object_path_id": raycast_go,
                        "game_object_name": go_name(raycast_go),
                        "attached_colliders": raycast_components,
                    },
                    "open_angle_degrees": angle,
                    "slight_open_angle_degrees": slight,
                    "duration_seconds": duration,
                    "linked_room_value": linked_value,
                    "linked_room": ROOMS.get(linked_value),
                    "door_collider": collider_details("level1", {"file_id": collider_ref[0], "path_id": collider_ref[1], "file": "level1" if collider_ref[0] == 0 else externals.get(collider_ref[0])}),
                    "close_speed_modifier": close_speed,
                    "source_collider": resolved_collider,
                },
                "runtime_actions": {
                    "open": {"target": "(startWorldEuler.x, startWorldEuler.y + _openAngle, startWorldEuler.z)", "duration_seconds": duration, "set_ease_numeric": 9, "set_ease_name": "OutCubic", "ease_name_basis": "numeric 9 in recovered IL; OutCubic mapping follows standard DOTween Ease enumeration, whose enum source is not retained in this repo"},
                    "close": {"target": "captured start world rotation", "duration_seconds": round(duration / close_speed, 7) if close_speed else None, "set_ease_numeric": 2, "set_ease_name": "InSine", "ease_name_basis": "numeric 2 in recovered IL; InSine mapping follows standard DOTween Ease enumeration, whose enum source is not retained in this repo"},
                    "slight_open": {"target": "(startWorldEuler.x, startWorldEuler.y + _slightOpenAngle, startWorldEuler.z)", "duration_seconds": duration, "set_ease_numeric": 2, "set_ease_name": "InSine"},
                    "open_tween_awaited": True,
                    "source_order_limit": "The per-room extra-action coroutine awaits its door Tween before returning. The exact inherited base-view dispatch point relative to the Android 2D scene change is not proven in this manifest.",
                },
                "source_paths": {"open_action_isil": "DoorTrigger_NestedType___get_ExtraActionIn_b__23_0_d.txt", "close_action_isil": "DoorTrigger_NestedType___get_ExtraActionOut_b__25_0_d.txt"},
                "sound_rule": "Open/close sounds are selected from runtime ESound arrays; those arrays are initialized by code, not serialized AudioClip references on this component.",
            })
        else:
            image_ref = pp(raw, 32)
            cycling = struct.unpack_from("<i", raw, 48)[0]
            frame_count = struct.unpack_from("<i", raw, 52)[0]
            if not 0 <= frame_count <= 512:
                raise ValueError(f"implausible AnimatedImage frame count {frame_count} in {obj.path_id}")
            frames = []
            frame_offset = 56
            for index in range(frame_count):
                ref = pp(raw, frame_offset + index * 12)
                resolved = resolve_pp(ref)
                name = sprite_names.get((resolved["file"], ref[1]))
                android_asset = None
                if resolved["file"] in {"sharedassets0.assets", "sharedassets1.assets"}:
                    android_asset = f"ui/exported_images/{Path(resolved['file']).stem}_{ref[1]}_{safe_filename_part(name or f'Sprite_{ref[1]}')}.png"
                frames.append({"index": index, "sprite": {**resolved, "name": name, "android_asset": android_asset}})
            fps_offset = frame_offset + frame_count * 12
            fps = struct.unpack_from("<i", raw, fps_offset)[0]
            if fps <= 0 and frame_count:
                raise ValueError(f"invalid AnimatedImage FPS {fps} in {obj.path_id}")
            image = resolve_pp(image_ref)
            animated_images.append({
                **component_base,
                "image": image,
                "play_from_awake": bool(raw[44]),
                "cycling_type_value": cycling,
                "cycling_type": CYCLES.get(cycling, f"Unknown({cycling})"),
                "frames": frames,
                "frame_count": frame_count,
                "frames_per_second": fps,
                "duration_seconds": round(frame_count / fps, 7) if fps > 0 else None,
                "ignore_timescale": bool(raw[fps_offset + 4]) if len(raw) > fps_offset + 4 else None,
            })

    sound_enum_names = {
        679114904: "Dream_bodyeater_whisperdoor_01",
        275830377: "Dream_bodyeater_whisperdoor_02",
        1841914318: "Dream_bodyeater_whisperdoor_03",
        1438629791: "Dream_bodyeater_whisperdoor_04",
    }
    scene_actions = []
    for scene_name in level_files:
        source_scene = files[scene_name]
        scene_externals = {index: Path(identifier.path).name for index, identifier in enumerate(source_scene.externals, start=1)}
        for obj in source_scene.objects.values():
            if obj.type.name != "MonoBehaviour":
                continue
            raw = obj.get_raw_data()
            script_path = struct.unpack_from("<q", raw, 20)[0]
            if scripts.get(script_path) != "_Code.Infrastructure.TriggerObjects.Objects.TriggerObjectOpenDoor":
                continue
            header = obj.read(check_read=False)
            goid = int(header.m_GameObject.m_PathID)
            gameobjects_in_scene = all_scene_gameobjects[scene_name]
            name = str(gameobjects_in_scene.get(goid, {}).get("m_Name", ""))
            pivot_ref = pp(raw, 32)
            pivot_id = pivot_ref[1]
            transform_map = all_scene_transforms[scene_name]
            pivot = transform_map.get(pivot_id)
            if not pivot:
                raise ValueError(f"TriggerObjectOpenDoor {obj.path_id} in {scene_name} references missing Transform {pivot_id}")
            angle = [f32(raw, 44 + axis * 4) for axis in range(3)]
            duration = f32(raw, 56)
            count = struct.unpack_from("<i", raw, 60)[0]
            if count < 0 or count > 128 or 64 + count * 4 > len(raw):
                raise ValueError(f"invalid TriggerObjectOpenDoor ESound array count {count} in {obj.path_id}")
            sounds = list(struct.unpack_from("<" + "i" * count, raw, 64)) if count else []
            pivot_go = int(pivot["m_GameObject"]["m_PathID"])
            pworld = local_matrix(pivot)
            parent = int(pivot["m_Father"]["m_PathID"])
            while parent:
                pworld = multiply(local_matrix(transform_map[parent]), pworld)
                parent = int(transform_map[parent]["m_Father"]["m_PathID"])
            collider_ref = None
            # This trigger has no serialized collider field. Collision component
            # selection occurs in the inherited ATriggerObject implementation.
            scene_actions.append({
                "scene_file": scene_name,
                "scene_asset_path": scene_asset_paths.get(scene_name),
                "component_path_id": int(obj.path_id),
                "game_object_path_id": goid,
                "game_object_name": name,
                "class": scripts[script_path],
                "door_transform": {
                    "file_id": pivot_ref[0], "path_id": pivot_id,
                    "file": scene_name if pivot_ref[0] == 0 else scene_externals.get(pivot_ref[0]),
                    "game_object_path_id": pivot_go,
                    "game_object_name": str(gameobjects_in_scene.get(pivot_go, {}).get("m_Name", "")),
                    "parent_transform_path_id": int(pivot["m_Father"]["m_PathID"]),
                    "local_position": vec(pivot["m_LocalPosition"]),
                    "local_rotation_xyzw": quat(pivot["m_LocalRotation"]),
                    "world_position": [round(float(pworld[i][3]), 7) for i in range(3)],
                    "renderers_on_pivot": scene_renderers(scene_name, pivot_go),
                    "descendant_renderers": subtree_renderers(scene_name, pivot_id),
                    "world_renderer_path_id": (subtree_renderers(scene_name, pivot_id)[0]["renderer_path_id"] if subtree_renderers(scene_name, pivot_id) else None),
                },
                "serialized_fields": {"rotate_angle_degrees_xyz": angle, "duration_seconds": duration,
                                      "sound_enum_values": sounds,
                                      "sound_enum_names": [sound_enum_names.get(value) for value in sounds]},
                "trigger_field_offsets": {"door_transform": 32, "rotate_angle": 44, "duration": 56, "sounds_count": 60, "sounds_values": 64},
                "source_collider": {"status": "no explicit collider field in TriggerObjectOpenDoor; ATriggerObject requires a Collider component on the same GameObject", "attached_colliders": [
                    {"path_id": cid, "class": all_scene_components[scene_name][cid].type.name,
                     "enabled": bool(all_scene_components[scene_name][cid].read_typetree().get("m_Enabled", True)),
                     "is_trigger": bool(all_scene_components[scene_name][cid].read_typetree().get("m_IsTrigger", False))}
                    for cid in [int(c["component"]["m_PathID"]) for c in gameobjects_in_scene[goid]["m_Component"]]
                    if cid in all_scene_components[scene_name] and all_scene_components[scene_name][cid].type.name in ("BoxCollider", "SphereCollider", "CapsuleCollider", "MeshCollider")
                ]},
                "runtime_rule": "First OnEnterInner call runs DORotate on the referenced Transform toward the serialized Euler Vector3 over duration seconds; a random serialized ESound is emitted once; repeated triggers return early.",
            })

    char_animations = []
    if args.emotion_registry.is_file():
        entries = json.loads(args.emotion_registry.read_text())["records"]
        for entry in entries:
            if entry.get("class") != "CharacterAnimatedSpriteByEmotion":
                continue
            fields = entry["fields"]
            fps = int(fields["frames_per_second"])
            frames = fields["frame_sprites"]
            source_file = str(entry.get("source_file", "sharedassets0.assets"))
            char_animations.append({
                "character": entry["character"],
                "emotion": entry["emotion_name"],
                "cycling_type_value": int(fields["cycling_type_value"]),
                "cycling_type": CYCLES.get(int(fields["cycling_type_value"]), f"Unknown({fields['cycling_type_value']})"),
                "frames": [{
                    "index": i,
                    "file_id": int(frame["file_id"]),
                    "path_id": int(frame["path_id"]),
                    "file": source_file if int(frame["file_id"]) == 0 else externals.get(int(frame["file_id"])),
                    "name": sprite_names.get((source_file, int(frame["path_id"]))) if int(frame["file_id"]) == 0 else None,
                    "android_asset": f"sprites/{Path(source_file).stem}_{int(frame['path_id'])}.png" if int(frame["file_id"]) == 0 else None,
                } for i, frame in enumerate(frames)],
                "frame_count": len(frames),
                "frames_per_second": fps,
                "duration_seconds": round(len(frames) / fps, 7) if fps > 0 else None,
                "source_character_record": entry["raw_dump"],
                "runtime_use_limit": "Source emotion animation data; whether/when this emotion is selected remains runtime state.",
            })

    asset_staging = {"requested": bool(args.stage_extras), "directory": "reconstruction/android-current/app/src/main/assets/ui/exported_images", "new_exports": [], "already_present": [], "errors": []}
    if args.stage_extras:
        stage_dir = ROOT / "reconstruction/android-current/app/src/main/assets/ui/exported_images"
        stage_dir.mkdir(parents=True, exist_ok=True)
        for animation in animated_images:
            for frame in animation["frames"]:
                sprite = frame["sprite"]
                if not sprite.get("android_asset"):
                    continue
                target = ROOT / "reconstruction/android-current/app/src/main/assets" / sprite["android_asset"]
                if target.is_file():
                    asset_staging["already_present"].append({"path": str(target.relative_to(ROOT)), "sprite": sprite})
                    continue
                source_file = sprite.get("file")
                source_asset = files.get(source_file)
                source_obj = source_asset.objects.get(int(sprite["path_id"])) if source_asset else None
                if source_obj is None or source_obj.type.name != "Sprite":
                    asset_staging["errors"].append({"sprite": sprite, "error": "source Sprite object unresolved"})
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                image = source_obj.read().image
                image.save(target, format="PNG")
                payload = target.read_bytes()
                if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
                    target.unlink(missing_ok=True)
                    asset_staging["errors"].append({"sprite": sprite, "error": "output did not decode as PNG"})
                    continue
                record = {"path": str(target.relative_to(ROOT)), "sprite": sprite, "width": image.width, "height": image.height,
                          "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
                asset_staging["new_exports"].append(record)
        if asset_staging["errors"]:
            raise SystemExit("one or more scene animation sprites could not be staged; see error records in manifest")

    result = {
        "schema_version": 1,
        "provenance": {
            "method": "UnityPy static parsing of level1 plus globalgamemanagers.assets, sharedassets0.assets, and sharedassets1.assets; raw MonoBehaviour field layouts cross-checked against retained Cpp2IL declarations; no original PE/DLL executed",
            "data_directory": str(args.data),
            "files_read": static_files,
            "scene_asset_paths": scene_asset_paths,
            "level1_external_file_ids": {str(k): v for k, v in externals.items()},
            "source_code": [
                "reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/DoorTrigger.cs",
                "reconstruction/logic/recovered_isil/Assembly-CSharp/DoorTrigger.txt",
                "reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Utils/UI/ImageAnimating/AnimatedImage.cs",
                "reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Utils/UI/ImageAnimating/AnimationData.cs",
            ],
            "frame_timing_rule": "AnimationData.Duration = Frames.Length / (float)FramesPerSecond",
            "cycling_type_values": CYCLES,
        },
        "counts": {"room_door_triggers": len(doors), "generic_open_door_actions_across_scenes": len(scene_actions), "animated_image_components": len(animated_images), "character_emotion_animations": len(char_animations)},
        "door_triggers": sorted(doors, key=lambda d: d["serialized_fields"]["linked_room_value"]),
        "open_door_scene_actions": sorted(scene_actions, key=lambda d: (d["scene_file"], d["component_path_id"])),
        "animated_image_components": sorted(animated_images, key=lambda d: (d["game_object_name"], d["component_path_id"])),
        "character_emotion_animations": char_animations,
        "asset_staging": asset_staging,
        "runtime_semantics": {
            "PlayOnce": "Play the sequence once and disable the Image after the final-frame delay.",
            "Cycle": "Loop the sequence indefinitely.",
            "FixLastFrame": "Play once and retain the last frame.",
            "source_note": "Cycle=1 uses an effectively unbounded play count; PlayOnce=0 takes the terminal path that disables the Image; FixLastFrame=2 is the non-looping terminal path that leaves the last assigned frame visible.",
            "host_boundary": "A frame clock driven by Android elapsed time is a host scheduler adaptation. Preserve source order/FPS/cycle type; do not claim coroutine scheduling is bit-identical to Unity.",
        },
        "limits": [
            "Scene AnimatedImage components include UI/sign content; they do not establish that every room NPC animates.",
            "Character emotion frame lists do not establish which character or emotion is active at a particular gameplay moment.",
            "Door sound choices are ESound runtime values; this export does not resolve the service's enum-to-clip route.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
