#!/usr/bin/env python3
"""Static room-scene exporter for No, I'm not a Human.

Reads only level1, sharedassets0/1 and globalgamemanagers.assets. No original
EXE/DLL is executed. Custom MonoBehaviour fields are decoded from the serialized
layout documented by the retained C# declarations and checked against IL2CPP
MonoScript bindings; all references keep their source file/path IDs.
"""
from __future__ import annotations
import argparse, json, math, struct
from collections import Counter
from pathlib import Path
import UnityPy

ROOMS = [
    (0, "Kitchen", "kitchen"), (1, "Office", "office"),
    (2, "BigRoom", "bigRoom"), (3, "Bathroom", "bathroom"),
    (4, "Pantry", "pantry"), (5, "Entrance", "entrance"),
    (6, "Bedroom", "bedroom"),
]
VIEW_CLASSES = {"KitchenView", "OfficeView", "BigRoomView", "BathroomView", "PantryView", "EntranceRoomView", "BedroomView"}
NARRATIVE_CLASS = "_Code.Rooms.NarrativeRoomObject"
BUTTON_CLASS = "_Code.Rooms.UIButton"
IMAGE_CLASS = "UnityEngine.UI.Image"


def read_ptr(data: bytes, pos: int):
    return struct.unpack_from("<iq", data, pos), pos + 12


def read_array_ptrs(data: bytes, pos: int):
    count = struct.unpack_from("<i", data, pos)[0]
    pos += 4
    if count < 0 or count > 10000:
        raise ValueError(f"invalid PPtr array count {count} at offset {pos-4}")
    vals = []
    for _ in range(count):
        item, pos = read_ptr(data, pos)
        vals.append(item)
    return vals, pos


def read_string(data: bytes, pos: int):
    size = struct.unpack_from("<i", data, pos)[0]
    pos += 4
    if size < 0 or size > len(data) - pos:
        raise ValueError(f"invalid string length {size} at offset {pos-4}")
    text = data[pos:pos+size].decode("utf-8", errors="replace")
    pos += size
    pos = (pos + 3) & ~3
    return text, pos


EXTERNAL_FILES = {}


def ptr_json(ptr, file_name):
    target_file = file_name if ptr[0] == 0 else EXTERNAL_FILES.get(int(ptr[0]), f"external_file_id_{ptr[0]}")
    return {"file_id": int(ptr[0]), "path_id": int(ptr[1]), "file": target_file if ptr[1] else None}


def clean_float(x):
    if not math.isfinite(x):
        return None
    return round(float(x), 6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="NoImNotAHuman_Data directory")
    ap.add_argument("--out", type=Path, required=True, help="output room_manifest.json")
    args = ap.parse_args()
    data_dir = args.data.resolve()
    required = [data_dir / x for x in ("level1", "sharedassets0.assets", "sharedassets1.assets", "globalgamemanagers.assets")]
    for f in required:
        if not f.is_file():
            raise SystemExit(f"required Unity asset missing: {f}")
    env = UnityPy.Environment()
    for f in required:
        env.load_file(str(f))
    by_name = {Path(af.name).name: af for af in env.files.values()}
    scene = by_name["level1"]
    global EXTERNAL_FILES
    EXTERNAL_FILES = {index: Path(ref.path).name for index, ref in enumerate(scene.externals, start=1)}
    gm = by_name["globalgamemanagers.assets"]
    shared0, shared1 = by_name["sharedassets0.assets"], by_name["sharedassets1.assets"]
    objects = {"level1": scene.objects, "sharedassets0.assets": shared0.objects, "sharedassets1.assets": shared1.objects, "globalgamemanagers.assets": gm.objects}

    scripts = {}
    for o in gm.objects.values():
        if o.type.name == "MonoScript":
            d = o.read()
            fullname = f"{d.m_Namespace}.{d.m_ClassName}" if d.m_Namespace else str(d.m_ClassName)
            scripts[o.path_id] = {"name": fullname, "namespace": str(d.m_Namespace), "class_name": str(d.m_ClassName), "assembly": str(d.m_AssemblyName), "path_id": int(o.path_id)}

    go_by_id = {}
    comp_to_go = {}
    component_refs = {}
    transforms = {}
    for o in scene.objects.values():
        if o.type.name == "GameObject":
            t = o.read_typetree()
            go_by_id[o.path_id] = {"path_id": int(o.path_id), "name": t["m_Name"], "active_self": bool(t["m_IsActive"]), "layer": int(t["m_Layer"]), "component_ids": [int(c["component"]["m_PathID"]) for c in t["m_Component"]]}
            for c in t["m_Component"]:
                cid = int(c["component"]["m_PathID"])
                comp_to_go[cid] = int(o.path_id)
        elif o.type.name in ("Transform", "RectTransform"):
            transforms[o.path_id] = o.read_typetree()

    for cid, gid in comp_to_go.items():
        component_refs.setdefault(gid, []).append(cid)

    def object_ref(file_name, path_id):
        if not path_id:
            return None
        obj = objects.get(file_name, {}).get(path_id)
        if obj is None:
            return {"file": file_name, "path_id": int(path_id), "unresolved": True}
        return obj

    def go_ref(ptr):
        return int(ptr[1]) if ptr[0] == 0 and ptr[1] in go_by_id else None

    def go_name(gid):
        return go_by_id.get(gid, {}).get("name") if gid is not None else None

    def component_script(component):
        if component.type.name != "MonoBehaviour":
            return None
        raw = component.get_raw_data()
        script_id = struct.unpack_from("<q", raw, 20)[0]
        return scripts.get(script_id)

    # Build exact script binding and serialized MonoBehaviour index. The 32-byte
    # Unity MonoBehaviour prefix was verified against UnityPy's head typetree.
    mono = {}
    by_script = {}
    for o in scene.objects.values():
        if o.type.name != "MonoBehaviour":
            continue
        raw = o.get_raw_data()
        script_id = struct.unpack_from("<q", raw, 20)[0]
        binding = scripts.get(script_id)
        if not binding:
            continue
        head = o.read_typetree(check_read=False)
        gid = int(head.get("m_GameObject", {}).get("m_PathID", 0))
        rec = {"path_id": int(o.path_id), "game_object_path_id": gid, "type": binding["name"], "script_path_id": int(script_id), "enabled": bool(raw[12]), "raw_size": len(raw), "raw": raw}
        mono[o.path_id] = rec
        by_script.setdefault(binding["name"], []).append(o.path_id)

    # Provider's serialized fields are declared in this order in RoomsViewProvider.cs.
    provider_script = "_Code.Infrastructure.Rooms.RoomsViewProvider"
    provider_ids = by_script.get(provider_script, [])
    if len(provider_ids) != 1:
        raise ValueError(f"expected exactly one RoomsViewProvider, found {len(provider_ids)}")
    provider_id = provider_ids[0]
    provider_raw = mono[provider_id]["raw"]
    provider_fields = ["roomDisplayerCanvas", "roomDisplayerOverlay", "kitchen", "office", "bedroom", "bigRoom", "bathroom", "pantry", "entrance"]
    provider_ptrs, pos = [], 32
    for field in provider_fields:
        pp, pos = read_ptr(provider_raw, pos)
        provider_ptrs.append((field, pp))
    if pos != len(provider_raw):
        raise ValueError(f"RoomsViewProvider schema consumed {pos}, raw size {len(provider_raw)}")
    provider_by_field = dict(provider_ptrs)

    # Scene cameras and sprite names are exact Unity references.
    cameras = {}
    for o in scene.objects.values():
        if o.type.name == "Camera":
            d = o.read_typetree()
            gid = int(d["m_GameObject"]["m_PathID"])
            tid = next((tid for tid, t in transforms.items() if int(t["m_GameObject"]["m_PathID"]) == gid), None)
            t = transforms.get(tid, {})
            cameras[o.path_id] = {"path_id": int(o.path_id), "game_object_path_id": gid, "name": go_name(gid), "transform_path_id": tid, "local_position": t.get("m_LocalPosition"), "local_rotation": t.get("m_LocalRotation"), "local_scale": t.get("m_LocalScale"), "enabled": bool(d["m_Enabled"]), "orthographic": bool(d["orthographic"]), "orthographic_size": clean_float(d["orthographic size"]), "field_of_view": clean_float(d["field of view"]), "near": clean_float(d["near clip plane"]), "far": clean_float(d["far clip plane"]), "normalized_viewport": d["m_NormalizedViewPortRect"]}
    sprites = {}
    for asset_name, asset_objects in (("sharedassets0.assets", shared0.objects), ("sharedassets1.assets", shared1.objects)):
        for o in asset_objects.values():
            if o.type.name == "Sprite":
                d = o.read()
                sprites[(asset_name, o.path_id)] = {"file": asset_name, "path_id": int(o.path_id), "name": str(d.m_Name)}

    # Determine UIImage sprite pointers from the Image MonoBehaviour's serialized
    # m_Sprite slot (offset 88 in Unity 6.0's Image payload); retain raw byte evidence.
    image_info = {}
    sprite_ptrs_by_image = {}
    for mid in by_script.get(IMAGE_CLASS, []):
        rec = mono[mid]
        raw = rec["raw"]
        candidates = []
        for off in range(32, len(raw) - 11, 4):
            fid, pid = struct.unpack_from("<iq", raw, off)
            # fileID 2 is sharedassets1 in level1's external-reference table;
            # fileID 3 is sharedassets0. Keep both evidence links if present.
            target = None
            if fid == 2:
                target = sprites.get(("sharedassets1.assets", pid))
            elif fid == 3:
                target = sprites.get(("sharedassets0.assets", pid))
            if target:
                candidates.append({"offset": off, "pointer": {"file_id": int(fid), "path_id": int(pid), "file": target["file"]}, "sprite": target})
        # The UI Image schema serializes m_Sprite at offset 88. Do not promote
        # any incidental pointer-shaped bytes elsewhere as a sprite assignment.
        chosen = [c for c in candidates if c["offset"] == 88]
        sprite_ptrs_by_image[mid] = chosen
        image_info[mid] = {"component_path_id": int(mid), "game_object_path_id": rec["game_object_path_id"], "sprite_reference_offset": 88, "sprite": chosen[0] if len(chosen) == 1 else None, "sprite_state": "resolved" if len(chosen) == 1 else ("null" if len(chosen) == 0 else "ambiguous"), "sprite_candidate_count_at_slot": len(chosen)}

    def mono_ptr(file_name, mid, offset):
        raw = mono[mid]["raw"]
        pp = struct.unpack_from("<iq", raw, offset)
        return ptr_json(pp, file_name)

    def roomview_parse(mid):
        raw = mono[mid]["raw"]
        p = 32
        camera_distance, dialog_camera_distance = struct.unpack_from("<ff", raw, p)
        p += 8
        character_refs, p = read_array_ptrs(raw, p)
        object_refs, p = read_array_ptrs(raw, p)
        narrative_refs, p = read_array_ptrs(raw, p)
        whisper, p = read_ptr(raw, p)
        camera, p = read_ptr(raw, p)
        button_refs, p = read_array_ptrs(raw, p)
        door, p = read_ptr(raw, p)
        broken_door, p = read_ptr(raw, p)
        door_trigger, p = read_ptr(raw, p)
        if p > len(raw):
            raise ValueError(f"base ARoomView fields exceed serialized size for {mid}: {p}>{len(raw)}")
        arr = lambda refs: [{"file_id": int(fid), "path_id": int(pid), "component_type": mono.get(pid, {}).get("type"), "game_object_path_id": comp_to_go.get(pid), "game_object_name": go_name(comp_to_go.get(pid))} for fid, pid in refs]
        view = {"component_path_id": int(mid), "class": mono[mid]["type"], "game_object_path_id": mono[mid]["game_object_path_id"], "camera_distance": clean_float(camera_distance), "dialog_camera_distance": clean_float(dialog_camera_distance), "character_views": arr(character_refs), "object_views": arr(object_refs), "narrative_objects": arr(narrative_refs), "whispers_audio_source": ptr_json(whisper, "level1"), "linked_camera": {**ptr_json(camera, "level1"), "game_object_name": go_name(camera[1]) if camera[0] == 0 else None, "camera": cameras.get(camera[1]) if camera[0] == 0 else None}, "ui_buttons": arr(button_refs), "door": ptr_json(door, "level1"), "broken_door": ptr_json(broken_door, "level1"), "door_trigger": ptr_json(door_trigger, "level1"), "serialized_base_fields_end_offset": p}
        return view, p

    # Export hierarchy under room-view GameObjects, keeping every local transform.
    children = {}
    transform_to_go = {}
    for tid, t in transforms.items():
        gid = int(t["m_GameObject"]["m_PathID"])
        transform_to_go[tid] = gid
    for tid, t in transforms.items():
        parent_tid = int(t["m_Father"]["m_PathID"])
        if parent_tid:
            children.setdefault(parent_tid, []).append(tid)
    def hierarchy(root_gid):
        root_t = next((tid for tid, gid in transform_to_go.items() if gid == root_gid), None)
        if root_t is None:
            return []
        out = []
        stack = [(root_t, 0, [])]
        while stack:
            tid, depth, ancestors = stack.pop()
            gid = transform_to_go[tid]
            if gid in ancestors:
                continue
            go = go_by_id[gid]
            t = transforms[tid]
            components = []
            for cid in go["component_ids"]:
                obj = scene.objects.get(cid)
                if not obj:
                    continue
                if obj.type.name == "MonoBehaviour":
                    m = mono.get(cid)
                    type_name = m["type"] if m else "MonoBehaviour"
                    script_id = m["script_path_id"] if m else None
                else:
                    type_name, script_id = obj.type.name, None
                components.append({"path_id": cid, "type": type_name, "script_path_id": script_id, "enabled": bool(mono[cid]["enabled"]) if cid in mono else None})
            rect = None
            if "m_AnchoredPosition" in t:
                rect = {"anchored_position": {"x": clean_float(t["m_AnchoredPosition"]["x"]), "y": clean_float(t["m_AnchoredPosition"]["y"])}, "size_delta": {"x": clean_float(t["m_SizeDelta"]["x"]), "y": clean_float(t["m_SizeDelta"]["y"])}, "anchor_min": {"x": clean_float(t["m_AnchorMin"]["x"]), "y": clean_float(t["m_AnchorMin"]["y"])}, "anchor_max": {"x": clean_float(t["m_AnchorMax"]["x"]), "y": clean_float(t["m_AnchorMax"]["y"])}, "pivot": {"x": clean_float(t["m_Pivot"]["x"]), "y": clean_float(t["m_Pivot"]["y"])}}
            chain = ancestors + [gid]
            active_in_hierarchy = all(go_by_id[x]["active_self"] for x in chain)
            node = {"game_object_path_id": gid, "name": go["name"], "active_self": go["active_self"], "active_in_hierarchy_from_serialized_ancestors": active_in_hierarchy, "transform_path_id": tid, "transform_type": "RectTransform" if rect else "Transform", "local_position": {k: clean_float(v) for k,v in t["m_LocalPosition"].items()}, "local_scale": {k: clean_float(v) for k,v in t["m_LocalScale"].items()}, "rect_transform": rect, "components": components, "depth_from_room_root": depth}
            for comp in components:
                if comp["path_id"] in image_info:
                    node.setdefault("images", []).append(image_info[comp["path_id"]])
            out.append(node)
            nxt_anc = ancestors + [gid]
            for child in reversed(children.get(tid, [])):
                stack.append((child, depth+1, nxt_anc))
        return out

    room_entries = []
    for enum_value, room_name, provider_field in ROOMS:
        view_pp = provider_by_field[provider_field]
        view_id = int(view_pp[1]) if view_pp[0] == 0 else 0
        view_record = mono.get(view_id)
        if not view_record:
            raise ValueError(f"provider field {provider_field} target {view_pp} not a local MonoBehaviour")
        v, end_offset = roomview_parse(view_id)
        root_gid = view_record["game_object_path_id"]
        view_root_name = go_name(root_gid)
        nodes = hierarchy(root_gid)
        node_ids = {n["game_object_path_id"] for n in nodes}
        # Find Sprite/Image assignments on descendants with byte-level PPtr evidence.
        room_images = []
        for node in nodes:
            for image in node.get("images", []):
                room_images.append({"game_object_path_id": node["game_object_path_id"], "game_object_name": node["name"], **image})
        # Derived serialized fields that support specialized room buttons/background variants.
        p = end_offset
        derived = {}
        extra_fields = {
            "KitchenView": [("_fridgeButton", "ptr")],
            "OfficeView": [("_baby", "ptr"), ("_cultistsSheets", "ptr")],
            "BigRoomView": [("_appleButton", "ptr"), ("_roomBlood", "ptr")],
            "BathroomView": [("_donorForPlayerSigns", "ptr"), ("_sink", "ptr"), ("_baby", "ptr")],
            "EntranceRoomView": [("_background", "ptr"), ("_burningBackground", "ptr"), ("_destroyedBackground", "ptr")],
            "BedroomView": [("_tv", "ptr"), ("_tvUiButton", "ptr"), ("_sexy", "ptr"), ("_bed", "ptr"), ("_videoPlayer", "ptr"), ("_screen", "ptr"), ("_babyCurtain", "ptr"), ("_babyCurtainButton", "ptr"), ("_mushroomlistButton", "ptr"), ("_clock", "ptr")],
            "PantryView": [],
        }
        short_class = view_record["type"].split(".")[-1]
        for fname, ftype in extra_fields.get(short_class, []):
            pp, p = read_ptr(view_record["raw"], p)
            dest_file = "level1"
            derived[fname] = ptr_json(pp, dest_file)
        derived["bytes_remaining_after_known_fields"] = len(view_record["raw"]) - p
        derived["raw_size"] = len(view_record["raw"])
        view_root = {"game_object_path_id": root_gid, "name": view_root_name, "active_self": go_by_id[root_gid]["active_self"], "transform_path_id": next((tid for tid,gid in transform_to_go.items() if gid==root_gid), None)}
        background_images = [x for x in room_images if x["sprite"] and go_by_id[x["game_object_path_id"]]["name"] in ("RoomTest", "Background", "BG")]
        room_entries.append({"enum_value": enum_value, "room": room_name, "provider_field": provider_field, "provider_reference": ptr_json(view_pp,"level1"), "view_component": {k:v0 for k,v0 in view_record.items() if k!="raw"}, "view": v, "derived_view_fields": derived, "room_root": view_root, "hierarchy_game_object_count": len(nodes), "hierarchy": nodes, "background_images": background_images, "image_components": room_images, "ui_button_order": [{"order": i, **b} for i,b in enumerate(v["ui_buttons"])], "narrative_component_order": [{"order": i, **n} for i,n in enumerate(v["narrative_objects"])]})

    # Decode NarrativeRoomObject's serialized enum, button pointer, node string and Vector2.
    narrative = []
    for mid in by_script.get(NARRATIVE_CLASS, []):
        rec = mono[mid]; raw = rec["raw"]
        p = 32
        enum_value = struct.unpack_from("<i", raw, p)[0]; p += 4
        button, p = read_ptr(raw, p)
        node_name, p = read_string(raw, p)
        position = struct.unpack_from("<ff", raw, p); p += 8
        narrative.append({"component_path_id": int(mid), "script_path_id": rec["script_path_id"], "game_object_path_id": rec["game_object_path_id"], "game_object_name": go_name(rec["game_object_path_id"]), "enabled": rec["enabled"], "enum_value": int(enum_value), "button_reference": ptr_json(button,"level1"), "button_game_object_path_id": comp_to_go.get(button[1]), "button_game_object_name": go_name(comp_to_go.get(button[1])), "node_name": node_name, "position": {"x": clean_float(position[0]), "y": clean_float(position[1])}, "serialized_bytes_consumed": p, "raw_size": len(raw)})
        if p != len(raw):
            narrative[-1]["trailing_bytes"] = len(raw) - p
    narrative.sort(key=lambda x:(x["enum_value"],x["component_path_id"]))
    narrative_by_component = {n["component_path_id"]: n for n in narrative}
    narrative_enum_names = ["Bedroom_Curtain", "Bedroom_Nightstand", "Bathroom_Window", "BigRoom_Cross", "BigRoom_Toy", "Kitchen_Cupboards", "Office_Pictures", "Office_Magazine", "Pantry_Box"]
    for room in room_entries:
        for entry in room["narrative_component_order"]:
            node = narrative_by_component.get(entry["path_id"])
            if node:
                entry["enum_value"] = node["enum_value"]
                entry["enum_name"] = narrative_enum_names[node["enum_value"]] if node["enum_value"] in range(len(narrative_enum_names)) else None
                entry["node_name"] = node["node_name"]
                entry["position"] = node["position"]
                entry["button_reference"] = node["button_reference"]

    # Every button component and the single unassigned scene button are auditable.
    all_buttons = []
    assigned_order = {}
    for r in room_entries:
        for b in r["ui_button_order"]:
            assigned_order[b["path_id"]] = {"room": r["room"], "order": b["order"]}
    for mid in by_script.get(BUTTON_CLASS, []):
        rec = mono[mid]; raw = rec["raw"]
        image_ptr = struct.unpack_from("<iq", raw, 32)
        image_target = image_ptr[1]
        image = image_info.get(image_target)
        gid = rec["game_object_path_id"]
        transform_id = next((tid for tid,g in transform_to_go.items() if g==gid), None)
        t = transforms.get(transform_id, {})
        all_buttons.append({"component_path_id": int(mid), "script_path_id": rec["script_path_id"], "game_object_path_id": gid, "game_object_name": go_name(gid), "enabled": rec["enabled"], "image_reference": ptr_json(image_ptr,"level1"), "image_component": image, "assignment": assigned_order.get(mid), "rect_transform": ({"anchored_position": t.get("m_AnchoredPosition"), "size_delta": t.get("m_SizeDelta"), "anchor_min": t.get("m_AnchorMin"), "anchor_max": t.get("m_AnchorMax"), "pivot": t.get("m_Pivot")} if "m_AnchoredPosition" in t else None), "interaction_region": {"implementation": "UIButton.IsMousePosInSpriteArea(position, camera)", "method": "camera-aware RectTransform conversion followed by sprite alpha sampling", "alpha_threshold": 0.1, "fixed_rectangle_asserted": False}, "source": {"component_file": "level1", "component_path_id": int(mid), "serialized_image_pointer_offset": 32}})

    # Attach actual camera records to room-linked camera refs (PPtr points to Camera component).
    for r in room_entries:
        pp = r["view"]["linked_camera"]
        r["view"]["linked_camera"]["camera"] = cameras.get(pp["path_id"]) if pp["file_id"] == 0 else None
        r["view"]["linked_camera"]["game_object_name"] = r["view"]["linked_camera"]["camera"]["name"] if r["view"]["linked_camera"]["camera"] else None

    source = {"unity_data_files_loaded": [str(x.relative_to(data_dir)) for x in required], "scene": {"file": "level1", "unity_version": scene.unity_version, "unity_serialization_version": scene.header.version, "path_id_scope": "file-local"}, "mono_scripts": {"file": "globalgamemanagers.assets", "bindings": ["Unity MonoScript path ID and class/namespace/assembly read statically"], "relevant_bindings": [scripts[x] for x in sorted(scripts) if scripts[x]["name"] in (provider_script, NARRATIVE_CLASS, BUTTON_CLASS) or scripts[x]["name"].split(".")[-1] in VIEW_CLASSES or scripts[x]["name"] == IMAGE_CLASS]}}
    manifest = {"schema_version": 1, "provenance": {"method": "UnityPy static scene/asset parsing plus manual serialized MonoBehaviour field decoding using retained class declarations; no bundled executable or DLL executed", "source": source, "field_decoding": {"unity_monobehaviour_header_bytes": 32, "provider_fields": "serialized PPtrs in field declaration order; validated against raw object size 140 and retained RoomsViewProvider field offsets", "room_view_fields": "ARoomView float/array/PPtr fields decoded in declaration order; derived fields decoded from each concrete class's serialized declarations", "narrative_fields": "enum, UIButton PPtr, UTF-8 string, Vector2 in retained field order", "button_fields": "UIButton._image PPtr at byte offset 32", "image_sprite_field": "UnityEngine.UI.Image m_Sprite PPtr at byte offset 88, matched only when PPtr resolves to a Sprite in sharedassets0/1"}, "interaction_bounds": "Unity UIButton checks sprite alpha after camera-aware RectTransform conversion; exported rect data is source geometry only and is not asserted as the click mask"}, "counts": {"rooms": len(room_entries), "room_views": len(room_entries), "room_hierarchy_game_objects": sum(r["hierarchy_game_object_count"] for r in room_entries), "room_array_buttons": sum(len(r["ui_button_order"]) for r in room_entries), "scene_ui_button_components": len(all_buttons), "unassigned_scene_ui_button_components": sum(1 for b in all_buttons if b["assignment"] is None), "narrative_components": len(narrative), "resolved_room_image_sprite_refs": sum(1 for r in room_entries for i in r["image_components"] if i["sprite"]), "camera_components": len(cameras)}, "room_enum": [{"value": e, "name": n} for e,n,_ in ROOMS], "provider": {"component_path_id": int(provider_id), "game_object_path_id": mono[provider_id]["game_object_path_id"], "game_object_name": go_name(mono[provider_id]["game_object_path_id"]), "field_order": provider_fields, "serialized_fields": [{"field": f, "reference": ptr_json(pp,"level1"), "target_component_type": mono.get(pp[1],{}).get("type") or (scene.objects.get(pp[1]).type.name if scene.objects.get(pp[1]) else None), "target_game_object_path_id": comp_to_go.get(pp[1]), "target_game_object_name": go_name(comp_to_go.get(pp[1]))} for f,pp in provider_ptrs]}, "cameras": list(cameras.values()), "rooms": room_entries, "narrative_interactables": narrative, "ui_buttons": sorted(all_buttons,key=lambda x:x["component_path_id"])}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest["counts"], ensure_ascii=False))

if __name__ == "__main__":
    main()
