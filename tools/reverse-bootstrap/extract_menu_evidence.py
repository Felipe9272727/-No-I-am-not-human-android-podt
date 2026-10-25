#!/usr/bin/env python3
"""Export retained Main Menu sprites and record serialized menu scene objects.

UnityPy reads serialized data only. This script never loads or executes game
code, the original EXE, or the original DLL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import UnityPy


SPRITES = {
    2048: "mainMenu_bg",
    1616: "mainMenu_House",
    1863: "No_im_not_a_human_logo",
    2213: "mainmenu_eyes_0",
    2309: "mainmenu_teeth_11",
    1769: "button_2",
    2367: "mainmenu_mask_0",
    1288: "mainmenu_mask_1",
    1380: "mainmenu_light_0",
    2455: "mainmenu_light_1",
    1986: "mainMenu_circle",
    1692: "trioskaz_banner_main",
    2228: "fake_wishlist_mainmenu_3",
    2016: "Fake_collection_background",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pid(ptr) -> int:
    return int(getattr(ptr, "m_PathID", 0))


def script_names(path: Path) -> dict[int, str]:
    env = UnityPy.load(str(path))
    names = {}
    for obj in env.objects:
        if obj.type.name == "MonoScript":
            try:
                d = obj.read(check_read=False)
                names[int(obj.path_id)] = ".".join(x for x in (d.m_Namespace, d.m_ClassName) if x)
            except Exception:
                pass
    return names


def component_script_id(obj) -> int:
    raw = obj.get_raw_data()
    try:
        file_id = struct.unpack_from("<i", raw, 16)[0]
        path_id = struct.unpack_from("<q", raw, 20)[0]
        return path_id if file_id == 1 else 0
    except Exception:
        return 0


def scene_inventory(scene: Path, scripts: dict[int, str]) -> list[dict]:
    env = UnityPy.load(str(scene))
    objs = {int(o.path_id): o for o in env.objects}
    classes = {pid: scripts.get(component_script_id(o), "") for pid, o in objs.items() if o.type.name == "MonoBehaviour"}
    selected = []
    terms = ("MainMenu", "mainMenu", "NewGame", "Continue", "Settings", "Collection", "Quit", "button")
    for obj in env.objects:
        if obj.type.name != "GameObject":
            continue
        try:
            go = obj.read(check_read=False)
            name = str(go.m_Name)
            components = []
            rect = None
            for ptr in go.m_Components:
                cid = pid(ptr)
                co = objs.get(cid)
                if co is None:
                    continue
                ctype = co.type.name
                component = {"path_id": cid, "type": ctype, "class": classes.get(cid, "")}
                if ctype == "RectTransform":
                    td = co.read(check_read=False)
                    component["rect_transform"] = {
                        "anchored_position": [float(td.m_AnchoredPosition.x), float(td.m_AnchoredPosition.y)],
                        "size_delta": [float(td.m_SizeDelta.x), float(td.m_SizeDelta.y)],
                        "anchor_min": [float(td.m_AnchorMin.x), float(td.m_AnchorMin.y)],
                        "anchor_max": [float(td.m_AnchorMax.x), float(td.m_AnchorMax.y)],
                        "pivot": [float(td.m_Pivot.x), float(td.m_Pivot.y)],
                        "local_position": [float(td.m_LocalPosition.x), float(td.m_LocalPosition.y), float(td.m_LocalPosition.z)],
                        "parent_path_id": pid(td.m_Father),
                    }
                    rect = component["rect_transform"]
                components.append(component)
            if any(term.lower() in name.lower() for term in terms) or any("MainMenu" in c["class"] for c in components):
                selected.append({"game_object_path_id": int(obj.path_id), "name": name, "rect_transform": rect, "components": components})
        except Exception:
            continue
    return selected


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("game_data", type=Path, help="Path to NoImNotAHuman_Data")
    ap.add_argument("output", type=Path, help="Evidence JSON output path")
    ap.add_argument("--sprite-dir", type=Path, help="Optional folder for selected PNG sprites")
    args = ap.parse_args()
    data = args.game_data.resolve()
    assets = data / "sharedassets0.assets"
    level0 = data / "level0"
    managers = data / "globalgamemanagers.assets"
    for f in (assets, level0, managers):
        if not f.is_file():
            raise SystemExit(f"expected {f}")
    env = UnityPy.load(str(assets))
    by_id = {int(o.path_id): o for o in env.objects}
    sprite_evidence = []
    for path_id, expected_name in SPRITES.items():
        obj = by_id[path_id]
        sprite = obj.read(check_read=False)
        if sprite.m_Name != expected_name:
            raise ValueError(f"sprite {path_id}: expected {expected_name!r}, got {sprite.m_Name!r}")
        entry = {"path_id": path_id, "name": sprite.m_Name,
                 "width": int(sprite.m_Rect.width), "height": int(sprite.m_Rect.height)}
        if args.sprite_dir:
            args.sprite_dir.mkdir(parents=True, exist_ok=True)
            filename = f"sharedassets0_{path_id}_{expected_name}.png"
            target = args.sprite_dir / filename
            sprite.image.save(target)
            entry["exported_path"] = str(target)
            entry["exported_sha256"] = sha256_file(target)
        sprite_evidence.append(entry)

    scripts = script_names(managers)
    scene_objects = scene_inventory(level0, scripts)
    evidence = {
        "method": "UnityPy serialized-file static parsing and Sprite texture export; no original executable or native library executed",
        "source_files": {
            assets.name: {"sha256": sha256_file(assets)},
            level0.name: {"sha256": sha256_file(level0)},
            managers.name: {"sha256": sha256_file(managers)},
        },
        "scene": {"build_index": 0, "scene_file": level0.name, "name": "s0_MainMenuScene",
                  "main_menu_view_path_id": 2273, "main_menu_view_provider_game_object_path_id": 112,
                  "selected_serialized_objects": scene_objects},
        "menu_art": sprite_evidence,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
