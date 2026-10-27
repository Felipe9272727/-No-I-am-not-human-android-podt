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
    for node in r["hierarchy"]:
        rotation = node.get("local_rotation")
        check(isinstance(rotation, dict) and all(axis in rotation for axis in ("x", "y", "z", "w")), f"missing local quaternion rotation for {r['room']} GameObject {node.get('game_object_path_id')}")
        if isinstance(rotation, dict) and all(isinstance(rotation.get(axis), (int, float)) for axis in ("x", "y", "z", "w")):
            norm = sum(float(rotation[axis]) ** 2 for axis in ("x", "y", "z", "w"))
            check(math.isfinite(norm) and abs(norm - 1.0) < 0.001, f"non-unit/nonfinite local quaternion for {r['room']} GameObject {node.get('game_object_path_id')}")
        scale = node.get("local_scale")
        check(isinstance(scale, dict) and all(isinstance(scale.get(axis), (int, float)) and math.isfinite(float(scale[axis])) for axis in ("x", "y", "z")), f"missing/nonfinite local scale for {r['room']} GameObject {node.get('game_object_path_id')}")
    for obj in r["view"]["object_views"]:
        table = obj.get("state_table")
        check(table is not None, f"object view {obj['path_id']} lacks decoded source states")
        if table:
            check(table["bytes_consumed"] == table["component_raw_size"], f"object view {obj['path_id']} state schema leaves trailing bytes")
            matches = [s for s in table["states"] if s["enum_value"] == table["start_state_value"]]
            check(len(matches) == 1, f"object view {obj['path_id']} start state does not uniquely select a serialized row")
for n in m["narrative_interactables"]:
    check(n["enum_value"] in range(9), f"narrative enum out of range on component {n['component_path_id']}")
    check(n["button_reference"]["path_id"] in button_ids, f"narrative component {n['component_path_id']} points to unknown UIButton")
    check(n["serialized_bytes_consumed"] == n["raw_size"], f"narrative component {n['component_path_id']} has trailing data")
    check(math.isfinite(n["position"]["x"]) and math.isfinite(n["position"]["y"]), f"narrative component {n['component_path_id']} has nonfinite position")
fridge = next((o for r in rooms for o in r["view"]["object_views"] if o.get("game_object_name") == "Fridge"), None)
check(fridge is not None, "Kitchen Fridge object view missing")
if fridge:
    state_table = fridge.get("state_table", {})
    fridge_state = next((s for s in state_table.get("states", []) if s["enum_value"] == state_table.get("start_state_value")), None)
    kitchen = next(r for r in rooms if r["room"] == "Kitchen")
    node = next((n for n in kitchen["hierarchy"] if n["game_object_path_id"] == fridge.get("game_object_path_id")), {})
    check(fridge["component_type"] == "_Code.Rooms.ObjectRoomObjectView", "Kitchen Fridge object view type changed")
    check(fridge.get("game_object_path_id") == 999 and node.get("active_self") is True, "Kitchen Fridge source GameObject is not activeSelf")
    check(state_table.get("state_type") == "EObjectsRoomObject" and state_table.get("start_state_name") == "Fridge", "Kitchen Fridge does not start at EObjectsRoomObject.Fridge")
    check(fridge_state is not None and fridge_state["sprite_reference"]["file"] == "sharedassets1.assets" and fridge_state["sprite_reference"]["path_id"] == 612, "Kitchen Fridge start Sprite differs from source Kitchen_obj1")
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
