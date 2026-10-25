#!/usr/bin/env python3
"""Report the retained Unity UI.Image preserveAspect bit for room imagery."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import UnityPy


PRESERVE_ASPECT_OFFSET = 104


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("game_data", type=Path)
    ap.add_argument("scene_render_manifest", type=Path)
    ap.add_argument("room_manifest", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    data = args.game_data.resolve()
    scene_file = data / "level1"
    scene_render = json.loads(args.scene_render_manifest.read_text(encoding="utf-8"))
    room_manifest = json.loads(args.room_manifest.read_text(encoding="utf-8"))
    scene = UnityPy.load(str(scene_file))
    objects = {int(o.path_id): o for o in scene.objects}

    backgrounds = []
    for room in room_manifest["rooms"]:
        for image in room.get("background_images", []):
            sprite = image.get("sprite")
            if not sprite:
                continue
            component_id = int(image["component_path_id"])
            raw = objects[component_id].get_raw_data()
            if len(raw) <= PRESERVE_ASPECT_OFFSET:
                raise ValueError(f"Image component {component_id} is too short")
            backgrounds.append({
                "room": room["room"],
                "image_component_path_id": component_id,
                "game_object_name": image["game_object_name"],
                "sprite": sprite["sprite"],
                "raw_size": len(raw),
                "preserve_aspect_byte_offset": PRESERVE_ASPECT_OFFSET,
                "preserve_aspect": bool(raw[PRESERVE_ASPECT_OFFSET]),
                "serialized_bool_byte": int(raw[PRESERVE_ASPECT_OFFSET]),
            })

    characters = []
    for item in scene_render["room_character_instances"]:
        component_id = int(item["image_reference"]["path_id"])
        raw = objects[component_id].get_raw_data()
        if len(raw) <= PRESERVE_ASPECT_OFFSET:
            raise ValueError(f"Image component {component_id} is too short")
        characters.append({
            "room": item["room"],
            "order_in_room": item["order_in_room"],
            "character": item["character"]["name"],
            "image_component_path_id": component_id,
            "sprite_is_runtime_animated": True,
            "raw_size": len(raw),
            "preserve_aspect_byte_offset": PRESERVE_ASPECT_OFFSET,
            "preserve_aspect": bool(raw[PRESERVE_ASPECT_OFFSET]),
            "serialized_bool_byte": int(raw[PRESERVE_ASPECT_OFFSET]),
        })

    result = {
        "method": "UnityPy serialized level1 parsing; reads the UnityEngine.UI.Image preserveAspect serialized bool at raw MonoBehaviour byte offset 104; no game executable or native library executed",
        "source": {
            "scene_file": "level1",
            "scene_sha256": sha256_file(scene_file),
            "room_manifest": str(args.room_manifest),
            "scene_render_manifest": str(args.scene_render_manifest),
            "image_field_evidence": "m_Sprite is decoded at byte offset 88 by tools/reverse-rooms/export_room_manifest.py; Image serialized sequence places Image.Type at 100 and preserveAspect bool at 104.",
        },
        "room_backgrounds": backgrounds,
        "character_images": characters,
        "counts": {
            "backgrounds": len(backgrounds),
            "backgrounds_preserve_aspect": sum(x["preserve_aspect"] for x in backgrounds),
            "character_images": len(characters),
            "character_images_preserve_aspect": sum(x["preserve_aspect"] for x in characters),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
