#!/usr/bin/env python3
"""Extract a small, static inventory of scene components relevant to bootstrap.

This parses Unity serialized files with UnityPy; it never loads or executes game
code. The scene and global manager assets are loaded one at a time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import UnityPy


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ptr_id(ptr) -> int:
    return int(getattr(ptr, "m_PathID", 0))


def script_names(manager_path: Path) -> dict[int, str]:
    env = UnityPy.load(str(manager_path))
    result = {}
    for obj in env.objects:
        if obj.type.name != "MonoScript":
            continue
        try:
            data = obj.read()
            result[obj.path_id] = ".".join(
                x for x in (data.m_Namespace, data.m_ClassName) if x
            )
        except Exception:
            continue
    return result


def scene_inventory(scene_path: Path, scripts: dict[int, str]) -> list[dict]:
    env = UnityPy.load(str(scene_path))
    objects = {obj.path_id: obj for obj in env.objects}
    component_classes = {}
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            raw = obj.get_raw_data()
            script_file = struct.unpack_from("<i", raw, 16)[0]
            script_path = struct.unpack_from("<q", raw, 20)[0]
            component_classes[obj.path_id] = scripts.get(script_path, "") if script_file == 1 else ""
        except Exception:
            component_classes[obj.path_id] = ""

    selected = []
    needles = ("StartPoint", "PlayerInstance", "PlayerController", "Dialog", "SceneContext", "GameplaySceneInstaller", "FirstMarker", "Location", "SaveInteractable")
    for obj in env.objects:
        if obj.type.name != "GameObject":
            continue
        try:
            go = obj.read()
            name = str(go.m_Name)
            components = [
                {"path_id": ptr_id(p), "type": objects.get(ptr_id(p)).type.name if objects.get(ptr_id(p)) else "?",
                 "class": component_classes.get(ptr_id(p), "")}
                for p in go.m_Components
            ]
            if not any(n in name or n in c["class"] for n in needles for c in components):
                continue
            transform = next((objects[c["path_id"]] for c in components
                              if c["type"] in ("Transform", "RectTransform") and c["path_id"] in objects), None)
            pos = None
            parent_id = None
            if transform is not None:
                td = transform.read()
                pos = [float(td.m_LocalPosition.x), float(td.m_LocalPosition.y), float(td.m_LocalPosition.z)]
                parent_id = ptr_id(td.m_Father)
            selected.append({"game_object_path_id": obj.path_id, "name": name,
                             "local_position": pos, "parent_transform_path_id": parent_id,
                             "components": components})
        except Exception:
            continue
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("game_data", type=Path, help="Path to NoImNotAHuman_Data")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = args.game_data.resolve()
    manager = data / "globalgamemanagers.assets"
    build_settings_file = data / "globalgamemanagers"
    scene = data / "level1"
    if not manager.is_file() or not build_settings_file.is_file() or not scene.is_file():
        raise SystemExit(f"expected {manager}, {build_settings_file}, and {scene}")
    names = script_names(manager)
    build_env = UnityPy.load(str(build_settings_file))
    build_settings = next(obj.read() for obj in build_env.objects if obj.type.name == "BuildSettings")
    evidence = {
        "method": "UnityPy serialized-file static parsing; no original executable or native library executed",
        "files": {
            manager.name: {"sha256": sha256(manager)},
            build_settings_file.name: {"sha256": sha256(build_settings_file)},
            scene.name: {"sha256": sha256(scene)},
        },
        "build_settings": {
            "unity_version": str(build_settings.m_Version),
            "scenes_in_build_order": list(build_settings.scenes),
        },
        "script_names_source": manager.name,
        "scene_objects": scene_inventory(scene, names),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.output}: {len(evidence['scene_objects'])} selected GameObjects")


if __name__ == "__main__":
    main()
