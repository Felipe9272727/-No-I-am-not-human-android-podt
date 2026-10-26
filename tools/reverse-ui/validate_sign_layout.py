#!/usr/bin/env python3
"""Validate exported source sign layers against the Unity UI manifest."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAYOUT = ROOT / "reconstruction/reverse-ui/sign_layout.json"
UI = ROOT / "reconstruction/android-current/app/src/main/assets/presentation/ui/ui_manifest.json"

def require(condition, message):
    if not condition: raise SystemExit(message)

layout = json.loads(LAYOUT.read_text()); ui = json.loads(UI.read_text())
require(layout.get("schema_version") == 1, "unexpected sign layout schema")
expected = {"eye":0,"hands":1,"teeth":2,"photo":3,"armpit":4,"ear":5}
signs = {x["name"]:x for x in layout.get("signs",[])}
require({k:v["enum_value"] for k,v in signs.items()} == expected, "sign enum map mismatch")
items = {int(x["path_id"]):x for x in ui["scenes"]["dialogue"]}
for sign in signs.values():
    layers = sign["layers_back_to_front"]
    require(layers and [x["hierarchy_order"] for x in layers] == sorted(x["hierarchy_order"] for x in layers),
            f"{sign['name']} layers are not in source child order")
    ids = [x["image_id"] for x in layers]
    require(len(ids) == len(set(ids)), f"{sign['name']} has duplicate Image components")
    for layer in layers:
        source = items.get(layer["image_id"])
        require(source is not None and source.get("class") == "UnityEngine.UI.Image",
                f"missing source Image {layer['image_id']}")
        require(source.get("image",{}).get("sprite_source") == layer.get("source_image"),
                f"sprite PPtr mismatch for Image {layer['image_id']}")
        require(source["rect_transform"]["screen_rect_1920x1080"] == layer["screen_rect_1920x1080"],
                f"source rect mismatch for Image {layer['image_id']}")
        require(layer["mask_image_id"] == -1 or layer["mask_image_id"] in items,
                f"unresolved mask Image for {layer['image_id']}")

hands = signs["hands"]
hand_content = next(x for x in hands["layers_back_to_front"] if x["role"] == "content")
require(hand_content["mask_image_id"] == 4527, "HandsContent lost its source Mask Image")
require(hand_content["mask_component_path_id"] == 4664, "HandsContent lost its source Mask component")
for name in ("hands", "photo"):
    movement=signs[name]["movement"]
    require(movement["coordinate_space"] == "Transform.localPosition"
            and movement["canvas_path_id"] == 3101, f"{name} tween coordinate space changed")
    require(movement["parent_local_scale"] == [1.0,1.0,1.0]
            and movement["content_local_position"] == [0.0,0.0,0.0],
            f"{name} local movement no longer matches unscaled source canvas coordinates")
require(hands["movement"]["start_position"] == [0.0,-400.0,0.0]
        and hands["movement"]["end_position"] == [0.0,0.0,0.0], "Hands tween fields are misaligned")
photo = signs["photo"]["movement"]
require(photo["start_position"] == [0.0,-1100.0,0.0] and photo["duration_seconds"] == 1.0
        and photo["before_delay_seconds"] == 2.0, "Photo tween fields are misaligned")
eye = signs["eye"]["eye"]
require(eye["white_image"] == {"file_id":0,"path_id":4518}
        and eye["iris_image"] == {"file_id":0,"path_id":4760}, "Eye PPtr fields are misaligned")
require(layout["view"]["text_container"]["path_id"] == 4637
        and layout["view"]["text_container"]["hide_during_sign"], "DialogContent hide state not recorded")
require(layout["view"]["normal_text"]["path_id"] == 4784
        and signs["photo"]["hide_dialogue_text"]
        and all(not signs[name]["hide_dialogue_text"] for name in ("eye","hands","teeth","armpit","ear")),
        "normal-text clearing must be scoped to the source Photo branch")
print("validate_sign_layout: PASS (6 signs, source layers, masks, and corrected raw movement PPtrs)")
