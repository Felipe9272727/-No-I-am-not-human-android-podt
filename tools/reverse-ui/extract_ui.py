#!/usr/bin/env python3
"""Recover the original level-one gameplay UI from Unity serialized assets.

This reads only Unity data files through UnityPy. It never loads or executes the
original application binary or native libraries.
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
IMAGE_SPRITE = 88
IMAGE_TYPE = 100
IMAGE_PRESERVE_ASPECT = 104
IMAGE_COLOR = 44


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def pptr(raw: bytes, off: int):
    f, p = struct.unpack_from("<iq", raw, off)
    return {"file_id": int(f), "path_id": int(p)}


def floats(raw: bytes, off: int, count: int):
    return [round(float(v), 6) if math.isfinite(v) else None for v in struct.unpack_from("<" + "f" * count, raw, off)]


def safe(text: str):
    return (re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._") or "asset")[:90]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="Original NoImNotAHuman_Data directory")
    ap.add_argument("--out", type=Path, default=ROOT / "reconstruction/reverse-ui")
    args = ap.parse_args()
    data, out = args.data.resolve(), args.out.resolve()
    required = ("level1", "globalgamemanagers.assets", "sharedassets0.assets", "sharedassets1.assets", "resources.assets")
    for name in required:
        if not (data / name).is_file():
            raise SystemExit(f"missing Unity file {data / name}")
    env = UnityPy.Environment()
    for name in required:
        env.load_file(str(data / name))
    for name in ("sharedassets0.assets.resS", "sharedassets1.assets.resS", "resources.assets.resS"):
        if (data / name).is_file():
            env.load_file(str(data / name))
    files = {Path(f.name).name: f for f in env.files.values() if getattr(f, "name", None)}
    scene, gm = files["level1"], files["globalgamemanagers.assets"]
    external = {i: Path(x.path).name for i, x in enumerate(scene.externals, 1)}
    scripts = {}
    for obj in gm.objects.values():
        if obj.type.name == "MonoScript":
            d = obj.read_typetree()
            ns, cls = str(d.get("m_Namespace", "")), str(d.get("m_ClassName", ""))
            scripts[int(obj.path_id)] = f"{ns}.{cls}" if ns else cls

    gos, comp_go, transforms = {}, {}, {}
    for obj in scene.objects.values():
        if obj.type.name == "GameObject":
            d = obj.read_typetree()
            gid = int(obj.path_id)
            ids = [int(x["component"]["m_PathID"]) for x in d["m_Component"]]
            gos[gid] = {"path_id": gid, "name": str(d["m_Name"]), "active_self": bool(d["m_IsActive"]), "layer": int(d["m_Layer"]), "component_path_ids": ids}
            for cid in ids:
                comp_go[cid] = gid
        elif obj.type.name in ("Transform", "RectTransform"):
            transforms[int(obj.path_id)] = obj.read_typetree()
    by_go = {int(t["m_GameObject"]["m_PathID"]): (tid, t) for tid, t in transforms.items()}
    parent = {}
    for gid, (tid, t) in by_go.items():
        ftid = int(t.get("m_Father", {}).get("m_PathID", 0))
        parent[gid] = next((pg for pg, (ptid, _) in by_go.items() if ptid == ftid), None)
    canvas_mode = {}
    for obj in scene.objects.values():
        if obj.type.name == "Canvas":
            d = obj.read_typetree()
            canvas_mode[int(d["m_GameObject"]["m_PathID"])] = int(d.get("m_RenderMode", 0))

    def chain(gid):
        seen, values = set(), []
        while gid and gid in gos and gid not in seen:
            seen.add(gid)
            values.append(gid)
            gid = parent.get(gid)
        return list(reversed(values))

    def path_names(gid):
        return [gos[x]["name"] for x in chain(gid)]

    def active(gid):
        return all(gos[x]["active_self"] for x in chain(gid))

    rect_cache = {}
    def pixel_rect(gid, seen=None):
        if gid in rect_cache:
            return rect_cache[gid]
        seen = set() if seen is None else seen
        if gid in seen or gid not in by_go:
            return None
        seen.add(gid)
        tid, t = by_go[gid]
        if gid in canvas_mode and canvas_mode[gid] in (0, 1):
            result = [0.0, 0.0, 1920.0, 1080.0]
        elif "m_SizeDelta" not in t:
            result = pixel_rect(parent.get(gid), seen) if parent.get(gid) else [0.0, 0.0, 1920.0, 1080.0]
        else:
            pr = pixel_rect(parent.get(gid), seen) if parent.get(gid) else None
            if pr is None:
                pr = [0.0, 0.0, 1920.0, 1080.0]
            l, top, pw, ph = pr
            amin, amax = t.get("m_AnchorMin", {"x": .5, "y": .5}), t.get("m_AnchorMax", {"x": .5, "y": .5})
            pivot, delta = t.get("m_Pivot", {"x": .5, "y": .5}), t["m_SizeDelta"]
            pos = t.get("m_AnchoredPosition", {"x": 0, "y": 0})
            w = float(delta["x"]) + (float(amax["x"]) - float(amin["x"])) * pw
            h = float(delta["y"]) + (float(amax["y"]) - float(amin["y"])) * ph
            ax = float(amin["x"]) + (float(amax["x"]) - float(amin["x"])) * float(pivot["x"])
            ay = float(amin["y"]) + (float(amax["y"]) - float(amin["y"])) * float(pivot["y"])
            px, py = l + pw * ax + float(pos["x"]), top + ph * (1 - ay) - float(pos["y"])
            result = [px - w * float(pivot["x"]), py - h * (1 - float(pivot["y"])), w, h]
        rect_cache[gid] = result
        return result

    def rect(gid):
        found = by_go.get(gid)
        if not found:
            return None
        tid, t = found
        value = {"transform_path_id": tid, "type": "RectTransform" if "m_AnchorMin" in t else "Transform",
                 "local_position": t.get("m_LocalPosition"), "local_scale": t.get("m_LocalScale"),
                 "local_rotation": t.get("m_LocalRotation"), "parent_transform_path_id": int(t.get("m_Father", {}).get("m_PathID", 0))}
        for key, outkey in (("m_AnchoredPosition", "anchored_position"), ("m_SizeDelta", "size_delta"), ("m_AnchorMin", "anchor_min"), ("m_AnchorMax", "anchor_max"), ("m_Pivot", "pivot")):
            if key in t:
                value[outkey] = t[key]
        pr = pixel_rect(gid)
        if pr:
            value["screen_rect_1920x1080"] = [round(v, 4) for v in pr]
            value["normalized_rect_1920x1080"] = [round(pr[0] / 1920, 6), round(pr[1] / 1080, 6), round(pr[2] / 1920, 6), round(pr[3] / 1080, 6)]
            value["normalized_rect_semantics"] = "top-left origin; [left, top, width, height]"
        return value

    native = {}
    for obj in scene.objects.values():
        if obj.type.name in ("GameObject", "MonoBehaviour"):
            continue
        gid = comp_go.get(int(obj.path_id))
        row = {"path_id": int(obj.path_id), "class": obj.type.name, "game_object_path_id": gid, "game_object_name": gos.get(gid, {}).get("name"), "enabled": None}
        if obj.type.name == "Canvas":
            d = obj.read_typetree()
            row.update({"enabled": bool(d.get("m_Enabled", True)), "sorting_layer_id": d.get("m_SortingLayerID"), "sorting_order": d.get("m_SortingOrder"), "render_mode": int(d.get("m_RenderMode", 0))})
        native[int(obj.path_id)] = row
    comp_rows, monos = {}, {}
    for obj in scene.objects.values():
        if obj.type.name != "MonoBehaviour":
            continue
        raw = obj.get_raw_data()
        sid = struct.unpack_from("<q", raw, 20)[0]
        cls = scripts.get(sid, "MonoBehaviour")
        h = obj.read_typetree(check_read=False)
        gid = int(h.get("m_GameObject", {}).get("m_PathID", 0))
        row = {"path_id": int(obj.path_id), "class": cls, "game_object_path_id": gid, "game_object_name": gos.get(gid, {}).get("name"), "enabled": bool(raw[12]), "raw_size": len(raw)}
        monos[int(obj.path_id)] = (row, raw)
        comp_rows[int(obj.path_id)] = row

    canvas_by_go = {r["game_object_path_id"]: r for r in native.values() if r["class"] == "Canvas"}
    def canvas_for(gid):
        for g in reversed(chain(gid)):
            if g in canvas_by_go:
                return canvas_by_go[g]
        return None

    image_types = {0: "Simple", 1: "Sliced", 2: "Tiled", 3: "Filled"}
    sprite_refs, font_assets, components = {}, set(), []
    for obj in scene.objects.values():
        if obj.type.name != "MonoBehaviour":
            continue
        base, raw = monos[int(obj.path_id)]
        cls, gid = base["class"], base["game_object_path_id"]
        if not gid:
            continue
        row = {**base, "hierarchy": path_names(gid), "active_in_hierarchy": active(gid), "visible": active(gid) and base["enabled"], "rect_transform": rect(gid), "canvas": canvas_for(gid)}
        if cls == "UnityEngine.UI.Image" and len(raw) >= 136:
            spr = pptr(raw, IMAGE_SPRITE)
            fname = external.get(spr["file_id"]) if spr["file_id"] else "level1"
            key = f"{fname}:{spr['path_id']}" if spr["path_id"] else None
            typ = struct.unpack_from("<i", raw, IMAGE_TYPE)[0]
            row["image"] = {"sprite_source": {**spr, "file": fname}, "sprite_key": key, "type_value": typ, "type": image_types.get(typ, "Unknown"), "preserve_aspect": bool(raw[IMAGE_PRESERVE_ASPECT]), "preserve_aspect_byte_offset": IMAGE_PRESERVE_ASPECT, "color_rgba": floats(raw, IMAGE_COLOR, 4), "raycast_target": bool(raw[36])}
            if key and fname in files:
                sprite_refs.setdefault(key, {"file": fname, "path_id": spr["path_id"], "roles": []})["roles"].append({"game_object": gos[gid]["name"], "hierarchy": row["hierarchy"]})
        if "TextMeshPro" in cls:
            # The first valid UTF-8 length-prefixed string is TMP's authored m_text.
            candidates = []
            for off in range(32, len(raw) - 4, 4):
                n = struct.unpack_from("<i", raw, off)[0]
                if 0 < n <= min(2048, len(raw) - off - 4):
                    try:
                        text = raw[off + 4:off + 4 + n].decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    if text and all(ch.isprintable() or ch in "\r\n\t" for ch in text):
                        candidates.append((off, text))
            if candidates:
                off, text = max(candidates, key=lambda x: (len(x[1]), -x[0]))
                row["text"] = {"value": text, "serialized_length_prefixed_string_offset": off}
            font_refs = []
            for off in range(32, len(raw) - 12, 4):
                ref = pptr(raw, off)
                fname = external.get(ref["file_id"]) if ref["file_id"] else "level1"
                if not ref["path_id"] or fname not in files:
                    continue
                target = files[fname].objects.get(ref["path_id"])
                if target and target.type.name == "MonoBehaviour":
                    try:
                        tid = struct.unpack_from("<q", target.get_raw_data(), 20)[0]
                        if scripts.get(tid, "").endswith("TMP_FontAsset"):
                            font_refs.append({**ref, "file": fname})
                            font_assets.add((fname, ref["path_id"]))
                    except Exception:
                        pass
            row["font_asset_candidates"] = font_refs
            fs = struct.unpack_from("<f", raw, 300)[0] if len(raw) >= 304 else float("nan")
            color = floats(raw, 160, 4) if len(raw) >= 176 else []
            row["font_size"] = round(fs, 4) if math.isfinite(fs) and 1 <= fs <= 512 else None
            row["font_size_serialized_byte_offset"] = 300 if row["font_size"] is not None else None
            row["text_color_rgba"] = color if len(color) == 4 and all(x is not None and 0 <= x <= 1 for x in color) else None
            row["text_color_serialized_byte_offset"] = 160 if row["text_color_rgba"] else None
            row["alignment"] = None
        components.append(row)

    out.mkdir(parents=True, exist_ok=True)
    images_dir, fonts_dir = out / "exported_images", out / "exported_fonts"
    images_dir.mkdir(exist_ok=True)
    fonts_dir.mkdir(exist_ok=True)
    sprite_table = {}
    for key, ref in sorted(sprite_refs.items()):
        target = files[ref["file"]].objects.get(ref["path_id"])
        if not target or target.type.name != "Sprite":
            continue
        sprite = target.read()
        png = sprite.image
        tree = target.read_typetree()
        name = str(tree.get("m_Name", f"sprite_{ref['path_id']}"))
        filename = safe(f"{Path(ref['file']).stem}_{ref['path_id']}_{name}.png")
        dest = images_dir / filename
        png.save(dest)
        sprite_table[key] = {"path": f"exported_images/{filename}", "width": png.width, "height": png.height, "sha256": sha(dest), "source_file": ref["file"], "source_path_id": ref["path_id"], "source_name": name, "source_border": tree.get("m_Border"), "source_rect": tree.get("m_Rect"), "source_pivot": tree.get("m_Pivot"), "roles": ref["roles"]}

    font_rows, font_path_map = [], {}
    for fname, pid in sorted(font_assets):
        obj = files[fname].objects[pid]
        raw = obj.get_raw_data()
        source_fonts, texture_refs = [], []
        for off in range(32, len(raw) - 12, 4):
            fid, tpid = struct.unpack_from("<iq", raw, off)
            target_file = external.get(fid) if fid else fname
            target = files.get(target_file).objects.get(tpid) if target_file in files and tpid else None
            if target and target.type.name == "Font":
                source_fonts.append((off, target_file, tpid, target))
            elif target and target.type.name == "Texture2D":
                texture_refs.append((off, target_file, tpid, target))
        row = {"source_file": fname, "path_id": pid, "class": "TMP_FontAsset", "atlas": None, "embedded_ttf": None}
        if source_fonts:
            font_off, font_file, font_id, font_obj = source_fonts[0]
            ftree = font_obj.read_typetree()
            binary = ftree.get("m_FontData", b"")
            if isinstance(binary, list):
                binary = bytes(binary)
            if binary:
                ttf_name = safe(f"{Path(font_file).stem}_{font_id}_{ftree.get('m_Name','font')}.ttf")
                ttf = fonts_dir / ttf_name
                ttf.write_bytes(binary)
                row["embedded_ttf"] = {"path": f"exported_fonts/{ttf_name}", "source_file": font_file, "path_id": font_id, "source_name": ftree.get("m_Name"), "size_bytes": len(binary), "sha256": sha(ttf), "format_signature": binary[:4].hex()}
                font_path_map[f"{fname}:{pid}"] = f"ui/exported_fonts/{ttf_name}"
        later_textures = [x for x in texture_refs if not source_fonts or x[0] > source_fonts[0][0]]
        if later_textures:
            _, afile, aid, texture = later_textures[0]
            try:
                image = texture.read().image
                if image.width > 1 and image.height > 1:
                    atlas_name = safe(f"atlas_{Path(afile).stem}_{aid}.png")
                    atlas = fonts_dir / atlas_name
                    image.save(atlas)
                    row["atlas"] = {"path": f"exported_fonts/{atlas_name}", "source_file": afile, "path_id": aid, "width": image.width, "height": image.height, "sha256": sha(atlas)}
            except Exception:
                pass
        font_rows.append(row)

    scenes = {"world": [], "room": [], "dialogue": [], "pause": []}
    for row in components:
        if not row.get("image") and not row.get("text"):
            continue
        names = [x.lower() for x in row["hierarchy"]]
        if any("pause" in x or "settings" in x for x in names):
            group = "pause"
        elif any(any(k in x for k in ("dialog", "subtitle", "answer", "choice")) for x in names):
            group = "dialogue"
        elif any(any(k in x for k in ("room", "interact", "door", "hint")) for x in names):
            group = "room"
        else:
            group = "world"
        row["name"] = row["game_object_name"]
        row["kind"] = "image" if row.get("image") else "text"
        row["normalized_rect_1920x1080"] = (row.get("rect_transform") or {}).get("normalized_rect_1920x1080")
        row["z"] = (row.get("canvas") or {}).get("sorting_order")
        if row.get("image"):
            a = sprite_table.get(row["image"].get("sprite_key"), {}).get("path")
            row["asset"] = f"ui/{a}" if a else None
            row["color"] = row["image"]["color_rgba"]
        else:
            row["asset"] = None
            row["color"] = row.get("text_color_rgba")
            row["font_asset"] = next((font_path_map.get(f"{r['file']}:{r['path_id']}") for r in row.get("font_asset_candidates", []) if font_path_map.get(f"{r['file']}:{r['path_id']}")), None)
        if group == "pause":
            row["runtime_visibility_condition"] = "settings_open" if any("settings" in x for x in names) else "pause_open"
        elif group == "dialogue":
            row["runtime_visibility_condition"] = "dialogue_open"
        scenes[group].append(row)

    canvas_rows = []
    for c in canvas_by_go.values():
        gid = c["game_object_path_id"]
        canvas_rows.append({**c, "hierarchy": path_names(gid), "active_in_hierarchy": active(gid), "rect_transform": rect(gid)})
    result = {"schema_version": 1, "source": {"method": "UnityPy static parsing of level1 and its referenced shared assets; no original EXE/DLL executed", "scene": "level1", "files": list(required), "level1_sha256": sha(data / "level1"), "Image_fields": {"sprite_pptr": 88, "color_rgba": 44, "type": 100, "preserve_aspect": 104}},
              "reference_resolution": [1920, 1080], "normalized_rect_semantics": "top-left [left, top, width, height] relative to 1920x1080; recursively calculated from anchors, pivots, positions and size deltas; screen-space Canvas roots use the reference viewport",
              "counts": {"game_objects_total": len(gos), "components": len(components), "images": sum(bool(c.get("image")) for c in components), "unique_sprite_refs": len(sprite_refs), "exported_sprites": len(sprite_table), "referenced_font_assets": len(font_assets), "exported_font_assets": len(font_rows)},
              "runtime_visibility_evidence": {"source_files": ["_Code/Menues/HUD/HUDView.cs", "_Code/DialogSystem/DialogView.cs", "_Code/DialogSystem/FakeDialogRunner.cs", "_Code/Infrastructure/Pause/PauseMenuView.cs"], "rules": [{"view": "HUDView", "methods": ["ShowHint", "HideHint", "SetupAndShowControlsView", "HideControlsView"], "condition": "Presenter-driven and runtime state-dependent."}, {"view": "FakeDialogRunner", "methods": ["ShowSubtitle", "HideSubtitle", "OnLineViewTextAppeared", "UpdateButtonsActivity"], "condition": "Line text and option-button activity are changed by separate Yarn line and options callbacks; serialized activeSelf is startup state."}, {"view": "PauseMenuView", "methods": ["Show", "Hide"], "condition": "Pause content appears when pause state opens; Settings subsection appears only while settings is open."}], "limits": "visible is serialized startup hierarchy and component enabled state; animation, localization, scrolling/clipping and runtime state may change it."},
              "canvases": canvas_rows, "components": components, "scenes": scenes, "sprites": sprite_table, "fonts": font_rows,
              "unresolved_sprites": sorted(set(sprite_refs) - set(sprite_table))}
    (out / "ui_manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
