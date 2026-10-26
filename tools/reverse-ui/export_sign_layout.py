#!/usr/bin/env python3
"""Export authored Unity sign containers and their source image layout."""
from __future__ import annotations
import argparse, json, math, struct
from pathlib import Path
import UnityPy

ROOT = Path(__file__).resolve().parents[2]
SIGNS = [("eye", "eyes", 0), ("hands", "hands", 1), ("teeth", "teeth", 2),
         ("photo", "photo", 3), ("armpit", "armpit", 4), ("ear", "ear", 5)]
VIEW_OFFSETS = {"normal_text": 32, "text_container": 44, "eye": 56,
                "hands": 68, "teeth": 80, "ear": 92, "armpit": 104, "photo": 116}

def pptr(raw, off):
    file_id, path_id = struct.unpack_from("<iq", raw, off)
    return {"file_id": file_id, "path_id": path_id}

def vec(raw, off, n):
    out = struct.unpack_from("<" + "f" * n, raw, off)
    return [round(float(x), 6) if math.isfinite(x) else None for x in out]

def clean(v): return round(float(v), 6) if math.isfinite(float(v)) else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--ui-manifest", type=Path, default=ROOT / "reconstruction/android-current/app/src/main/assets/presentation/ui/ui_manifest.json")
    ap.add_argument("--out", type=Path, default=ROOT / "reconstruction/reverse-ui/sign_layout.json")
    args = ap.parse_args()
    for name in ("level1", "globalgamemanagers.assets"):
        if not (args.data / name).is_file(): raise SystemExit(f"missing Unity file: {args.data/name}")
    ui = json.loads(args.ui_manifest.read_text())
    env = UnityPy.Environment()
    env.load_file(str(args.data / "level1")); env.load_file(str(args.data / "globalgamemanagers.assets"))
    files = {Path(f.name).name: f for f in env.files.values()}
    scene = files["level1"]
    scripts = {}
    for o in env.objects:
        if o.type.name == "MonoScript":
            d = o.read(); ns = str(d.m_Namespace)
            scripts[int(o.path_id)] = (ns + "." if ns else "") + str(d.m_ClassName)
    monos = {}
    for o in scene.objects.values():
        if o.type.name != "MonoBehaviour": continue
        raw = o.get_raw_data(); script_id = struct.unpack_from("<q", raw, 20)[0]
        cls = scripts.get(script_id, "")
        if not cls.startswith("_Code.DialogSystem."): continue
        tree = o.read_typetree(check_read=False)
        go = int(tree.get("m_GameObject", {}).get("m_PathID", 0))
        monos[int(o.path_id)] = {"path_id": int(o.path_id), "class": cls, "game_object_path_id": go,
                                  "raw": raw, "raw_size": len(raw)}
    views = [m for m in monos.values() if m["class"].endswith(".DialogSignsView")]
    if len(views) != 1: raise ValueError(f"expected exactly one DialogSignsView, found {len(views)}")
    view = views[0]; vr = view["raw"]
    if len(vr) != 228: raise ValueError(f"DialogSignsView raw schema changed: {len(vr)} bytes")
    view_refs = {name: pptr(vr, off) for name, off in VIEW_OFFSETS.items()}

    # Unity Transform children retain serialized sibling order. This is the
    # draw order basis for overlapping Images inside each source container.
    transforms = {}
    for o in scene.objects.values():
        if o.type.name in ("Transform", "RectTransform"):
            transforms[int(o.path_id)] = o.read_typetree()
    go_to_transform = {int(d["m_GameObject"]["m_PathID"]): tid for tid, d in transforms.items()}
    transform_to_go = {tid: go for go, tid in go_to_transform.items()}
    children = {tid: [int(c["m_PathID"]) for c in d.get("m_Children", [])] for tid, d in transforms.items()}
    ui_items = {int(x["path_id"]): x for x in ui.get("scenes", {}).get("dialogue", [])}
    ui_by_go = {}
    for x in ui_items.values(): ui_by_go.setdefault(int(x.get("game_object_path_id", 0)), []).append(x)
    scene_objects = {int(o.path_id): o for o in scene.objects.values()}
    game_objects = {}
    for o in scene.objects.values():
        if o.type.name == "GameObject":
            t = o.read_typetree(); game_objects[int(o.path_id)] = str(t.get("m_Name", ""))
    masks_by_go = {}
    for go_obj in (o for o in scene.objects.values() if o.type.name == "GameObject"):
        tree = go_obj.read_typetree(); go = int(go_obj.path_id)
        mask_ids = []
        for entry in tree.get("m_Component", []):
            cid = int(entry["component"]["m_PathID"]); component = scene_objects.get(cid)
            if component is None or component.type.name != "MonoBehaviour": continue
            script_id = struct.unpack_from("<q", component.get_raw_data(), 20)[0]
            if scripts.get(script_id, "").endswith(".Mask"): mask_ids.append(cid)
        if mask_ids: masks_by_go[go] = mask_ids

    # PPtr lists on the two component types are inherited serial fields. The
    # managed field annotations include the IL2CPP object header, so serialized
    # MonoBehaviour offsets are adjusted by the 8-byte header delta.
    moving_schema = {"content_image": 32, "start_position": 44, "end_position": 56,
                     "ease": 68, "duration_seconds": 72, "before_delay_seconds": 76}
    eye_schema = {"content_image": 32, "animated_cover": 44, "white_image": 56, "iris_image": 68}
    by_go = {}
    for m in monos.values(): by_go.setdefault(m["game_object_path_id"], []).append(m)

    sign_rows = []
    for key, field, enum in SIGNS:
        ref = view_refs["eye" if key == "eye" else field]
        comp = monos.get(ref["path_id"])
        if ref["file_id"] != 0 or comp is None: raise ValueError(f"unresolved {key} view ref {ref}")
        cr = comp["raw"]
        if key in ("hands", "photo"):
            if comp["class"].endswith("MovingContent"):
                move_content = pptr(cr, 32); move_image = ui_items.get(move_content["path_id"], {})
                move_rt = move_image.get("rect_transform", {})
                move_parent = int(move_rt.get("parent_transform_path_id", 0))
                parent_scale = transforms.get(move_parent, {}).get("m_LocalScale", {})
                content_transform = transforms.get(int(move_rt.get("transform_path_id", 0)), {})
                mover = {"component_path_id": comp["path_id"], "schema_offsets": moving_schema,
                         "content_image": move_content, "content_transform_path_id": move_rt.get("transform_path_id"),
                         "parent_transform_path_id": move_parent,
                         "parent_local_scale": [parent_scale.get("x"), parent_scale.get("y"), parent_scale.get("z")],
                         "content_local_position": [content_transform.get("m_LocalPosition", {}).get(k) for k in ("x","y","z")],
                         "canvas_path_id": move_image.get("canvas", {}).get("path_id"),
                         "coordinate_space": "Transform.localPosition",
                         "start_position": vec(cr, 44, 3),
                         "end_position": vec(cr, 56, 3), "ease_value": struct.unpack_from("<i", cr, 68)[0],
                         "duration_seconds": clean(struct.unpack_from("<f", cr, 72)[0]),
                         "before_delay_seconds": clean(struct.unpack_from("<f", cr, 76)[0])}
            else: mover = None
        else: mover = None
        eye = None
        if key == "eye":
            if not comp["class"].endswith("DialogSignElementViewEye"): raise ValueError(f"wrong eye class {comp['class']}")
            eye = {"component_path_id": comp["path_id"], "schema_offsets": eye_schema,
                   "content_image": pptr(cr, 32), "animated_cover": pptr(cr, 44),
                   "white_image": pptr(cr, 56), "iris_image": pptr(cr, 68)}
        go = comp["game_object_path_id"]; root_tid = go_to_transform.get(go)
        order = {}
        def walk(tid, n):
            order[tid] = n
            nxt = n + 1
            for child in children.get(tid, []): nxt = walk(child, nxt)
            return nxt
        if root_tid is not None: walk(root_tid, 0)
        layers = []
        for item in ui_items.values():
            h = item.get("hierarchy", [])
            if "Line View" not in h or ("EyeContainer" if key == "eye" else {"hands":"HandsContainer","teeth":"TeethContainer","photo":"PhotoContainer","armpit":"ArmpitContainer","ear":"EarContainer"}[key]) not in h:
                continue
            if item.get("kind") != "image": continue
            rt = item.get("rect_transform", {}); tid = int(rt.get("transform_path_id", -1))
            if tid not in order: continue
            image = item.get("image", {}); sprite = image.get("sprite_source", {})
            n = item.get("game_object_name", "")
            role = "content"
            if key == "eye": role = {"White":"white", "Iris":"iris", "EyeFront":"static"}.get(n, "static")
            elif key == "hands": role = {"HandsBack":"static", "HandsFront":"static", "HandsContent":"content"}.get(n, "static")
            elif key == "teeth": role = {"TeethFront":"static", "TeethContent":"content"}.get(n, "static")
            elif key == "photo": role = "content"
            elif key == "armpit": role = {"Front":"static", "Content":"content"}.get(n, "static")
            elif key == "ear": role = {"Front":"static", "Content":"content"}.get(n, "static")
            mask_component_id = None; mask_image_id = -1; cursor = tid
            while cursor in transforms:
                mask_go = transform_to_go.get(cursor)
                if mask_go in masks_by_go:
                    mask_component_id = masks_by_go[mask_go][0]
                    mask_image_id = next((int(candidate["path_id"]) for candidate in ui_by_go.get(mask_go, [])
                                          if candidate.get("class") == "UnityEngine.UI.Image"), -1)
                    break
                cursor = int(transforms[cursor].get("m_Father", {}).get("m_PathID", 0))
            r = rt.get("screen_rect_1920x1080", [0,0,0,0])
            layers.append({"role": role, "image_id": int(item["path_id"]), "component_path_id": int(item["path_id"]), "game_object_path_id": int(item["game_object_path_id"]),
                           "game_object_name": n, "transform_path_id": tid, "parent_transform_path_id": rt.get("parent_transform_path_id"),
                           "hierarchy_order": order[tid], "source_image": sprite, "asset": item.get("asset", ""),
                           "mask_component_path_id": mask_component_id, "mask_image_id": mask_image_id,
                           "preserve_aspect": bool(image.get("preserve_aspect", False)),
                           "screen_rect_1920x1080": r, "anchored_position": rt.get("anchored_position"),
                           "size_delta": rt.get("size_delta"), "anchor_min": rt.get("anchor_min"), "anchor_max": rt.get("anchor_max"),
                           "pivot": rt.get("pivot"), "visible_at_startup": bool(item.get("visible", False))})
        layers.sort(key=lambda x: x["hierarchy_order"])
        component_item = ui_items.get(comp["path_id"], {})
        comp_rect = component_item.get("rect_transform", {})
        rects = [layer["screen_rect_1920x1080"] for layer in layers]
        bounds = None if not rects else [min(r[0] for r in rects), min(r[1] for r in rects),
                                         max(r[0]+r[2] for r in rects)-min(r[0] for r in rects),
                                         max(r[1]+r[3] for r in rects)-min(r[1] for r in rects)]
        sign_rows.append({"name": key, "enum_value": enum, "view_component_path_id": comp["path_id"],
                          "view_class": comp["class"], "container_game_object_path_id": go,
                          "container_name": game_objects.get(go, key), "bounds": bounds,
                          "activation": "ShowSign disables every sign container, then activates the selected container and assigns its character-specific image or animation data.",
                          "hide_dialogue_text": key == "photo",
                          "hide_dialogue_text_evidence": "Only the AuraPhoto branch clears DialogSignsView._normalText color; the other five branches do not reference _normalText.",
                          "movement": mover, "eye": eye, "layers_back_to_front": layers})

    text_ref = view_refs["text_container"]
    text_item = ui_items.get(text_ref["path_id"], {})
    normal_item = ui_items.get(view_refs["normal_text"]["path_id"], {})
    output = {"schema_version": 1,
      "provenance": {"method": "UnityPy static parsing of level1; image transforms/assets joined to ui_manifest; DialogSignsView and sign view refs decoded from MonoBehaviour raw bytes; no game PE executed",
                     "scene": "level1", "dialogue_canvas_reference_resolution": [1920,1080],
                     "source_files": ["level1", "globalgamemanagers.assets"],
                     "ui_manifest": str(args.ui_manifest.relative_to(ROOT) if args.ui_manifest.is_relative_to(ROOT) else args.ui_manifest),
                     "managed_offset_note": "IL2CPP managed field annotations include an 8-byte object header; serialized MonoBehaviour offsets for inherited fields are independently checked against raw sizes and PPtrs."},
      "view": {"component_path_id": view["path_id"], "raw_size": len(vr), "serialized_field_offsets": VIEW_OFFSETS,
               "normal_text": {**view_refs["normal_text"], "component_path_id": view_refs["normal_text"]["path_id"],
                 "game_object_name": normal_item.get("game_object_name"),
                 "screen_rect_1920x1080": normal_item.get("rect_transform", {}).get("screen_rect_1920x1080"),
                 "hidden_during_signs": ["photo"],
                 "evidence": "ShowSign only clears _normalText color in the AuraPhoto branch before activating PhotoContainer."},
               "text_container": {**view_refs["text_container"],
                 "component_path_id": text_ref["path_id"], "game_object_name": text_item.get("game_object_name"),
                 "transform_path_id": text_item.get("rect_transform", {}).get("transform_path_id"),
                 "screen_rect_1920x1080": text_item.get("rect_transform", {}).get("screen_rect_1920x1080"),
                 "hide_during_sign": True, "evidence": "DialogSignsView.ShowSign passes a zero 16-byte Color to the Graphic setter on _textContainer once at method entry, before branch selection."}},
      "signs": sign_rows,
      "source_runtime_rules": {"enum": {"Eye":0,"Hands":1,"Teeth":2,"AuraPhoto":3,"Armpit":4,"Ear":5},
        "show_sign": "Disable all sign containers; choose the requested container; assign human/imposter assets from CharacterSOData; activate the selected container.",
        "image_roles": "Layer order is depth-first Transform.m_Children order; source positions, scale, anchors and pivots are included alongside viewport rectangles.",
        "character_asset_selection": "Runtime IsImposter selects Human or Imposter CharacterSOData assets.",
        "eye": "Assign white and iris sprites, enable EyeFront AnimatedCover, and start MoveIris.",
        "hands": "Assign character hand sprite to HandsContent and run its authored StartPosition-to-EndPosition move.",
        "photo": "Assign character photo sprite and run its authored movement.",
        "movement_order": "MoveNext assigns Content.rectTransform.localPosition=StartPosition before awaiting BeforeDelay, then awaits the EndPosition tween for Duration seconds.",
        "movement_easing": {"2":{"name":"InSine","formula":"1 - cos(t*pi/2)"},"9":{"name":"OutCubic","formula":"1 + (t-1)^3"},"source":"DG.Tweening.Ease and EaseManager implementations; source hashes recorded in work audit."},
        "animated_signs": "Armpit and Ear assign CharacterSOData AnimationData; source frames/FPS/cycling are supplied by runtime state."}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"signs": len(sign_rows), "images": sum(len(s['layers_back_to_front']) for s in sign_rows),
                      "moving": sum(s['movement'] is not None for s in sign_rows), "out": str(args.out)}, indent=2))

if __name__ == "__main__": main()
