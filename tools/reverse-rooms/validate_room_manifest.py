#!/usr/bin/env python3
"""Validate structural invariants of the statically extracted room manifest."""
import json, math, re, sys
from pathlib import Path
p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reconstruction/reverse-rooms/room_manifest.json")
m = json.loads(p.read_text(encoding="utf-8"))
errors = []
def check(ok, message):
    if not ok: errors.append(message)
rooms = m["rooms"]
check(len(rooms) == 7, f"expected 7 rooms, got {len(rooms)}")
check([r["enum_value"] for r in rooms] == [0, 1, 2, 3, 4, 5, 6], "room enum ordering mismatch")
check(len(m["narrative_interactables"]) == 9, f"expected 9 narrative components, got {len(m['narrative_interactables'])}")
check(m["counts"]["room_array_buttons"] == 79, f"expected 79 room array button refs, got {m['counts']['room_array_buttons']}")
check(m["counts"]["scene_ui_button_components"] == 80, f"expected 80 scene UIButton components, got {m['counts']['scene_ui_button_components']}")
check(m["counts"]["unassigned_scene_ui_button_components"] == 1, "expected one scene UIButton outside room arrays")
check(all(r["background_images"] and r["background_images"][0]["sprite"] for r in rooms), "a room background Image/Sprite PPtr is unresolved")
check(all(r["derived_view_fields"]["bytes_remaining_after_known_fields"] == 0 for r in rooms), "room view decoder left unconsumed serialized bytes")
button_ids = {b["component_path_id"] for b in m["ui_buttons"]}
array_ids = [b["path_id"] for r in rooms for b in r["ui_button_order"]]
check(len(array_ids) == len(set(array_ids)), "a UIButton appears more than once in room arrays")
check(set(array_ids) <= button_ids, "room array contains a non-UIButton component")
check(all(b["image_reference"]["path_id"] for b in m["ui_buttons"]), "a UIButton has a null Image PPtr")
for r in rooms:
    check(r["room_root"]["active_self"] is False, f"unexpected serialized activeSelf for {r['room']} room root")
    check(r["view"]["linked_camera"]["camera"] is not None, f"missing linked Camera for {r['room']}")
for n in m["narrative_interactables"]:
    check(n["enum_value"] in range(9), f"narrative enum out of range on component {n['component_path_id']}")
    check(n["button_reference"]["path_id"] in button_ids, f"narrative component {n['component_path_id']} points to unknown UIButton")
    check(n["serialized_bytes_consumed"] == n["raw_size"], f"narrative component {n['component_path_id']} has trailing data")
    check(math.isfinite(n["position"]["x"]) and math.isfinite(n["position"]["y"]), f"narrative component {n['component_path_id']} has nonfinite position")
native_cpp = p.resolve().parents[1] / "native-game/src/rooms.cpp" if p.name == "room_manifest.json" else Path("reconstruction/native-game/src/rooms.cpp")
if native_cpp.is_file():
    source = native_cpp.read_text(encoding="utf-8")
    rows = re.findall(r'\{(\d+), RoomId::(\w+), "([^"]+)", "([^"]+)", \{([-\d.]+)f, ([-\d.]+)f\}\}', source)
    check(len(rows) == 9, f"expected nine native narrative source rows, got {len(rows)}")
    by_enum = {n["enum_value"]: n for n in m["narrative_interactables"]}
    for enum_value, room, name, node, x, y in rows:
        item = by_enum.get(int(enum_value))
        check(item is not None, f"manifest missing native narrative enum {enum_value}")
        if item:
            check(item["node_name"] == node, f"narrative enum {enum_value} node differs from native source")
            check(abs(item["position"]["x"] - float(x)) < 0.001 and abs(item["position"]["y"] - float(y)) < 0.001, f"narrative enum {enum_value} position differs from native source")
if errors:
    print("FAIL")
    for e in errors: print("-", e)
    raise SystemExit(1)
print(f"PASS: {len(rooms)} rooms, {len(button_ids)} UIButton components ({len(array_ids)} room-array refs), 9 narrative components, {m['counts']['resolved_room_image_sprite_refs']} resolved room Image/Sprite links")
