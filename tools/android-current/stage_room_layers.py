#!/usr/bin/env python3
"""Stage source-backed room Image layers for the Android renderer.

Inputs are recovered Unity scene/UI manifests. This is a static metadata
transform only; it never loads original game code or executables.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


EXPECTED_ROOMS = {
    0: "Kitchen",
    1: "Office",
    2: "BigRoom",
    3: "Bathroom",
    4: "Pantry",
    5: "Entrance",
    6: "Bedroom",
}
CONDITIONAL_VIEW_TYPES = {
    "_Code.Rooms.ObjectRoomObjectView",
    "_Code.Rooms.TestRoomObjectView",
}
IMAGE_TYPE = "UnityEngine.UI.Image"
SOURCE_SIZE = [1920, 1080]


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc


def component_types(node: dict[str, Any]) -> set[str]:
    return {str(c.get("type", "")) for c in node.get("components", [])}


def hierarchy_ancestry(hierarchy: list[dict[str, Any]]) -> tuple[dict[int, list[int]], dict[int, int]]:
    """Return ancestors (root excluded by callers when desired) and DFS order."""
    ancestors: dict[int, list[int]] = {}
    order: dict[int, int] = {}
    stack: list[int] = []
    for index, node in enumerate(hierarchy):
        depth = node.get("depth_from_room_root")
        go_id = node.get("game_object_path_id")
        if not isinstance(depth, int) or not isinstance(go_id, int):
            raise ValueError("room hierarchy node lacks integer depth/path ID")
        if depth < 0 or depth > len(stack):
            raise ValueError(f"invalid DFS depth {depth} for GameObject {go_id}")
        stack = stack[:depth]
        if len(stack) != depth:
            raise ValueError(f"non-contiguous DFS hierarchy at GameObject {go_id}")
        ancestors[go_id] = list(stack)
        order[go_id] = index
        stack.append(go_id)
    return ancestors, order


def image_asset(
    image_source: dict[str, Any],
    ui_component: dict[str, Any],
    assets: dict[str, Any],
    assets_root: Path,
) -> tuple[str | None, str | None]:
    sprite = image_source.get("sprite") or {}
    sprite_data = sprite.get("sprite") or {}
    key = f"{sprite_data.get('file')}:{sprite_data.get('path_id')}" if sprite_data else None
    mapped = assets.get("images", {}).get(key) if key else None
    ui_fallback = ui_component.get("asset")
    for candidate, source in ((mapped, "presentation/assets.json"), (ui_fallback, "ui_manifest")):
        if isinstance(candidate, str) and candidate and (assets_root / candidate).is_file():
            return candidate, source
    return None, None


def unsupported_transform_reason(
    node_chain: list[int], nodes: dict[int, dict[str, Any]], transforms: dict[int, dict[str, Any]],
) -> str | None:
    """Check whether serialized axis-aligned pixel rects are safe to use."""
    for go_id in node_chain:
        transform_id = nodes[go_id].get("transform_path_id")
        transform = transforms.get(transform_id) if isinstance(transform_id, int) else None
        source_rotation = nodes[go_id].get("local_rotation")
        source_scale = nodes[go_id].get("local_scale")
        rotation = source_rotation or (transform or {}).get("local_rotation")
        scale = source_scale or (transform or {}).get("local_scale")
        if rotation is None or scale is None:
            return "unsupported_transform_metadata_missing"
        if not isinstance(rotation, dict) or not isinstance(scale, dict):
            return "unsupported_transform_metadata_incomplete"
        ui_rotation = (transform or {}).get("local_rotation")
        if source_rotation and ui_rotation and any(
            abs(float(source_rotation.get(axis, 0)) - float(ui_rotation.get(axis, 0))) > 1e-5
            for axis in ("x", "y", "z", "w")
        ):
            return "unsupported_transform_source_conflict"
        if any(not isinstance(rotation.get(axis), (int, float)) for axis in ("x", "y", "z", "w")):
            return "unsupported_transform_rotation_unknown"
        if any(abs(float(rotation[axis])) > 1e-5 for axis in ("x", "y", "z")) or abs(float(rotation["w"]) - 1.0) > 1e-5:
            return "unsupported_rotated_hierarchy"
        if any(not isinstance(scale.get(axis), (int, float)) for axis in ("x", "y")):
            return "unsupported_transform_scale_unknown"
        if float(scale["x"]) <= 0 or float(scale["y"]) <= 0:
            return "unsupported_nonpositive_scale_or_flip"
    return None


def make_output(
    room_manifest: dict[str, Any],
    ui_manifest: dict[str, Any],
    assets_manifest: dict[str, Any],
    assets_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rooms = room_manifest.get("rooms")
    if not isinstance(rooms, list) or len(rooms) != len(EXPECTED_ROOMS):
        raise ValueError("room manifest must contain exactly seven room entries")
    actual = {r.get("enum_value"): r.get("room") for r in rooms}
    if actual != EXPECTED_ROOMS:
        raise ValueError(f"unexpected room enum/name mapping: {actual!r}")

    ui_components: dict[int, dict[str, Any]] = {}
    ui_transforms: dict[int, dict[str, Any]] = {}
    for component in ui_manifest.get("components", []):
        path_id = component.get("path_id")
        if isinstance(path_id, int):
            ui_components[path_id] = component
        transform_id = (component.get("rect_transform") or {}).get("transform_path_id")
        if isinstance(transform_id, int):
            ui_transforms[transform_id] = component.get("rect_transform") or {}

    output_rooms: list[dict[str, Any]] = []
    audit_rooms: list[dict[str, Any]] = []
    totals = Counter()
    resolved_asset_keys: set[str] = set()
    asset_resolution_counts = Counter()
    missing_resolved_asset_refs = 0

    for room in sorted(rooms, key=lambda item: item["enum_value"]):
        rid = room["enum_value"]
        hierarchy = room.get("hierarchy", [])
        ancestors, dfs_order = hierarchy_ancestry(hierarchy)
        nodes = {node["game_object_path_id"]: node for node in hierarchy}
        if len(nodes) != len(hierarchy):
            raise ValueError(f"{room['room']}: duplicate GameObject path IDs")
        root_id = room.get("room_root", {}).get("game_object_path_id")
        if not isinstance(root_id, int) or root_id not in nodes:
            raise ValueError(f"{room['room']}: room root missing from hierarchy")

        character_roots = {
            ref.get("game_object_path_id") for ref in room.get("view", {}).get("character_views", [])
            if isinstance(ref.get("game_object_path_id"), int)
        }
        conditional_roots: dict[int, str] = {}
        for node in hierarchy:
            for comp_type in component_types(node):
                if comp_type in CONDITIONAL_VIEW_TYPES:
                    conditional_roots[node["game_object_path_id"]] = comp_type

        def chain(go_id: int) -> list[int]:
            return ancestors.get(go_id, []) + [go_id]

        char_descendants: set[int] = set()
        conditional_descendants: dict[int, str] = {}
        for go_id in nodes:
            node_chain = chain(go_id)
            if any(ancestor in character_roots for ancestor in node_chain):
                char_descendants.add(go_id)
            for ancestor in node_chain:
                if ancestor in conditional_roots:
                    conditional_descendants[go_id] = conditional_roots[ancestor]
                    break

        layers: list[dict[str, Any]] = []
        exclusions: list[dict[str, Any]] = []
        source_resolved = 0
        rendered = 0
        exclusion_counts = Counter()
        for image_source in room.get("image_components", []):
            component_id = image_source.get("component_path_id")
            go_id = image_source.get("game_object_path_id")
            if not isinstance(component_id, int) or not isinstance(go_id, int):
                raise ValueError(f"{room['room']}: malformed image component record")
            ui = ui_components.get(component_id)
            if ui is None or ui.get("class") != IMAGE_TYPE:
                raise ValueError(f"{room['room']}: Image {component_id} missing from UI manifest")

            sprite_data = ((image_source.get("sprite") or {}).get("sprite") or {})
            sprite_key = f"{sprite_data.get('file')}:{sprite_data.get('path_id')}" if sprite_data else None
            if image_source.get("sprite_state") == "resolved":
                source_resolved += 1
                totals["source_resolved_images"] += 1
                if sprite_key:
                    resolved_asset_keys.add(sprite_key)

            if go_id not in nodes:
                raise ValueError(f"{room['room']}: Image {component_id} GameObject absent from hierarchy")
            node = nodes[go_id]
            node_chain = chain(go_id)
            # The selected room root is serialized inactive because views are
            # activated by the game when entered. Only its own flag is ignored.
            inactive = [x for x in node_chain if x != root_id and not nodes[x].get("active_self", False)]
            asset, asset_source = image_asset(image_source, ui, assets_manifest, assets_root)
            if image_source.get("sprite_state") == "resolved" and asset_source:
                asset_resolution_counts[asset_source] += 1
            elif image_source.get("sprite_state") == "resolved":
                missing_resolved_asset_refs += 1
            reason = None
            if go_id in char_descendants:
                reason = "character_view_or_descendant"
            elif go_id in conditional_descendants:
                reason = "conditional_room_object_state:" + conditional_descendants[go_id]
            elif inactive:
                reason = "inactive_self_or_ancestor"
            elif not ui.get("enabled", False):
                reason = "image_component_disabled"
            elif image_source.get("sprite_state") != "resolved":
                reason = "sprite_unresolved_in_source"
            elif asset is None:
                reason = "resolved_sprite_missing_from_staged_assets"
            elif (ui.get("image") or {}).get("type") != "Simple":
                reason = "unsupported_image_type:" + str((ui.get("image") or {}).get("type"))
            else:
                reason = unsupported_transform_reason(node_chain, nodes, ui_transforms)

            if reason:
                exclusions.append({
                    "image_component_path_id": component_id,
                    "game_object_path_id": go_id,
                    "name": image_source.get("game_object_name", node.get("name", "")),
                    "reason": reason,
                    "asset": asset,
                    "draw_order": dfs_order[go_id],
                })
                exclusion_counts[reason] += 1
                totals["excluded_layers"] += 1
                continue

            rect = (ui.get("rect_transform") or {}).get("screen_rect_1920x1080")
            if not (isinstance(rect, list) and len(rect) == 4 and all(isinstance(v, (int, float)) for v in rect)):
                normalized = ui.get("normalized_rect_1920x1080")
                if isinstance(normalized, list) and len(normalized) == 4:
                    rect = [normalized[0] * 1920, normalized[1] * 1080,
                            normalized[2] * 1920, normalized[3] * 1080]
                else:
                    raise ValueError(f"{room['room']}: Image {component_id} lacks a source-size rect")
            image_info = ui.get("image") or {}
            color = image_info.get("color_rgba", ui.get("color"))
            if not (isinstance(color, list) and len(color) == 4):
                raise ValueError(f"{room['room']}: Image {component_id} lacks RGBA color")
            preserve = image_info.get("preserve_aspect")
            if not isinstance(preserve, bool):
                raise ValueError(f"{room['room']}: Image {component_id} lacks preserve_aspect")
            layers.append({
                "image_component_path_id": component_id,
                "name": image_source.get("game_object_name", node.get("name", "")),
                "asset": asset,
                "rect": [round(float(v), 6) for v in rect],
                "draw_order": dfs_order[go_id],
                "color": [round(float(v), 6) for v in color],
                "preserve_aspect": preserve,
            })
            rendered += 1
            totals["visible_layers"] += 1

        character_orders = []
        layout_room = assets_manifest.get("room_layout_by_room", {}).get(str(rid), {})
        layout_characters = layout_room.get("characters", {})
        character_refs = room.get("view", {}).get("character_views", [])
        for character_order, ref in enumerate(character_refs):
            name = ref.get("game_object_name")
            layout = layout_characters.get(name)
            if not isinstance(layout, dict) or not isinstance(layout.get("order"), int):
                raise ValueError(f"{room['room']}: missing room_layout order for character {name!r}")
            go_id = ref.get("game_object_path_id")
            if go_id not in dfs_order:
                raise ValueError(f"{room['room']}: character {name!r} missing from hierarchy")
            character_orders.append({
                "character_order": layout["order"],
                "draw_order": dfs_order[go_id],
                "game_object_path_id": go_id,
            })

        # Unity Image order follows the source hierarchy, never manifest's
        # separately collected image list or asset-map iteration order.
        if [layer["draw_order"] for layer in layers] != sorted(layer["draw_order"] for layer in layers):
            layers.sort(key=lambda layer: layer["draw_order"])
        character_orders.sort(key=lambda item: item["draw_order"])
        output_rooms.append({
            "id": rid,
            "name": room["room"],
            "layers": layers,
            "character_orders": character_orders,
            "excluded_layers": exclusions,
        })
        audit_rooms.append({
            "id": rid,
            "name": room["room"],
            "source_image_components": len(room.get("image_components", [])),
            "resolved_sprite_references": source_resolved,
            "visible_layers": rendered,
            "excluded_layers": len(exclusions),
            "exclusion_reasons": dict(sorted(exclusion_counts.items())),
            "character_orders": len(character_orders),
        })

    if totals["source_resolved_images"] != 35:
        raise ValueError(f"expected 35 resolved room sprite references, got {totals['source_resolved_images']}")
    if sum(asset_resolution_counts.values()) != totals["source_resolved_images"] or missing_resolved_asset_refs:
        raise ValueError("not every resolved room Sprite has a staged APK asset path")
    entrance = next(row for row in output_rooms if row["id"] == 5)
    if len(entrance["layers"]) < 2:
        raise ValueError("Entrance must retain its two resolved active source layers")
    for room in output_rooms:
        component_ids = [layer["image_component_path_id"] for layer in room["layers"]]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError(f"{room['name']}: duplicate staged Image component")
        orders = [layer["draw_order"] for layer in room["layers"]]
        if orders != sorted(orders):
            raise ValueError(f"{room['name']}: layer draw_order is not source hierarchy order")
        for layer in room["layers"]:
            rect = layer["rect"]
            if len(rect) != 4 or not all(map(lambda v: isinstance(v, (int, float)), rect)) or rect[2] <= 0 or rect[3] <= 0:
                raise ValueError(f"{room['name']}: invalid source rect on {layer['name']}")
            if not (assets_root / layer["asset"]).is_file():
                raise ValueError(f"{room['name']}: staged asset vanished: {layer['asset']}")
        if any(not item.get("reason") for item in room["excluded_layers"]):
            raise ValueError(f"{room['name']}: excluded layer lacks a reason")
    missing_keys = sorted(key for key in resolved_asset_keys if key not in assets_manifest.get("images", {}))
    audit = {
        "schema_version": 1,
        "source_size": SOURCE_SIZE,
        "source_manifest": "reconstruction/reverse-rooms/room_manifest.json",
        "ui_manifest": "presentation/ui/ui_manifest.json",
        "assets_manifest": "presentation/assets.json",
        "evidence": {
            "room_root_active_self_ignored": True,
            "other_active_self_required": True,
            "character_roots_and_descendants_excluded": True,
            "conditional_room_object_types_excluded": sorted(CONDITIONAL_VIEW_TYPES),
            "conditional_room_object_policy": "ObjectRoomObjectView and TestRoomObjectView own serialized state arrays with Sprite/position/scale variation; their image subtrees are omitted rather than choosing a runtime state.",
            "layer_policy": "Only Image.type=Simple layers with available transforms, identity local rotations through all room ancestors, and positive x/y scale are emitted. Positive axis-aligned scale is represented by the recovered 1920x1080 screen rect; rotations/flips/unknown transforms are excluded explicitly.",
            "hierarchy_transform_source": "local_position/local_rotation/local_scale were re-exported from recovered level1 Transform/RectTransform UnityPy typetrees; rect/color/preserve_aspect are read from the UI manifest.",
            "sprite_keys_without_assets_manifest_mapping_use_ui_fallback": missing_keys,
        },
        "asset_resolution": dict(sorted(asset_resolution_counts.items())),
        "resolved_sprite_asset_refs_missing_from_staged_assets": missing_resolved_asset_refs,
        "totals": {
            "rooms": len(output_rooms),
            "source_image_components": sum(row["source_image_components"] for row in audit_rooms),
            "resolved_sprite_references": totals["source_resolved_images"],
            "unique_resolved_sprite_keys": len(resolved_asset_keys),
            "visible_layers": totals["visible_layers"],
            "excluded_layers": totals["excluded_layers"],
            "character_orders": sum(row["character_orders"] for row in audit_rooms),
        },
        "rooms": audit_rooms,
    }
    runtime = {"schema_version": 1, "rooms": output_rooms}
    add_verified_bed(runtime, audit, room_manifest, ui_components, assets_manifest, assets_root)
    return runtime, audit


def add_verified_bed(runtime, audit, room_manifest, ui_components, assets_manifest, assets_root):
    """Use the decoded ObjectRoomObjectState rather than its inactive editor pose."""
    evidence_path = Path(__file__).resolve().parents[2] / "reconstruction/reverse-campaign/morning_config.json"
    evidence = read_json(evidence_path)
    records = evidence["bed_object_room_object_views"]
    if len(records) != 1 or records[0]["path_id"] != 4801:
        raise ValueError("Expected source bed component 4801")
    record = records[0]
    fields = record["decoded_fields"]
    if fields["bytes_consumed"] != record["raw_object_bytes"]:
        raise ValueError("Bed state payload is not fully decoded")
    states = fields["_states"]["values"]
    if len(states) != 1 or states[0]["enum_value"] != fields["_startState"]["value"]:
        raise ValueError("Bed runtime state needs an explicit selector")
    state = states[0]
    image = ui_components[fields["_image_ptr"]["path_id"]]
    if image["path_id"] != 4843 or state["sprite"]["asset_file"] != "sharedassets1.assets" or state["sprite"]["path_id"] != 640:
        raise ValueError("Unexpected bed sprite evidence")
    room = next(r for r in room_manifest["rooms"] if r["enum_value"] == 6)
    sprite_source = next(r for r in room["image_components"] if r["component_path_id"] == 4843)
    asset, _ = image_asset(sprite_source, image, assets_manifest, assets_root)
    if asset is None:
        raise ValueError("Verified bed sprite is absent from staged assets")
    transform = image["rect_transform"]
    if transform["anchor_min"] != {"x": 0.5, "y": 0.5} or transform["anchor_max"] != {"x": 0.5, "y": 0.5}:
        raise ValueError("Bed anchor layout needs a different transform adapter")
    left, top, width, height = transform["screen_rect_1920x1080"]
    px, py = state["position_shift"]
    sx, sy = state["scale_shift"]
    pivot = transform["pivot"]
    dx = px - transform["anchored_position"]["x"]
    dy = py - transform["anchored_position"]["y"]
    rect = [left + dx - (width * sx - width) * pivot["x"],
            top - dy - (height * sy - height) * (1 - pivot["y"]), width * sx, height * sy]
    order = next(i for i, node in enumerate(room["hierarchy"]) if node["game_object_path_id"] == 398)
    target = next(r for r in runtime["rooms"] if r["id"] == 6)
    target["layers"].append({"image_component_path_id": 4843, "name": "Bed", "asset": asset,
        "rect": [round(v, 6) for v in rect], "draw_order": order,
        "color": image["image"]["color_rgba"], "preserve_aspect": image["image"]["preserve_aspect"],
        "condition": "bed_visible", "source_state_component": 4801, "source_state_enum": state["enum_value"]})
    target["layers"].sort(key=lambda layer: layer["draw_order"])
    target["excluded_layers"] = [r for r in target["excluded_layers"] if r["image_component_path_id"] != 4843]
    audit["totals"]["conditional_layers"] = 1
    audit["totals"]["excluded_layers"] -= 1
    audited_room = next(r for r in audit["rooms"] if r["id"] == 6)
    audited_room["conditional_layers"] = 1
    audited_room["excluded_layers"] -= 1
    reason = "conditional_room_object_state:_Code.Rooms.ObjectRoomObjectView"
    audited_room["exclusion_reasons"][reason] -= 1
    audit["evidence"]["verified_bed_state"] = {"source": str(evidence_path.relative_to(Path(__file__).resolve().parents[2])),
        "component_path_id": 4801, "activation": "bounded Android host bed_visible flag", "raw_object_sha256": record["raw_object_sha256"]}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def stage(
    destination_assets_root: Path | str,
    room_manifest_path: Path | str | None = None,
    ui_manifest_path: Path | str | None = None,
    assets_manifest_path: Path | str | None = None,
) -> dict[str, Any]:
    """Generate and return runtime room metadata for an Android assets root.

    Build pipelines may call ``stage(destination_assets_root)`` after staging
    ``presentation/ui/ui_manifest.json`` and ``presentation/assets.json``.
    The returned object is the runtime JSON document; the same bytes are
    written to ``presentation/room_layers.json``. The coverage audit is kept
    in the source tree beside the room manifest.
    """
    repo = Path(__file__).resolve().parents[2]
    destination = Path(destination_assets_root)
    room_path = Path(room_manifest_path) if room_manifest_path else repo / "reconstruction/reverse-rooms/room_manifest.json"
    ui_path = Path(ui_manifest_path) if ui_manifest_path else destination / "presentation/ui/ui_manifest.json"
    assets_path = Path(assets_manifest_path) if assets_manifest_path else destination / "presentation/assets.json"
    runtime, audit = make_output(read_json(room_path), read_json(ui_path), read_json(assets_path), destination)
    write_json(destination / "presentation/room_layers.json", runtime)
    write_json(repo / "reconstruction/reverse-rooms/room_layers_audit.json", audit)
    return runtime


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    assets_root_default = repo / "reconstruction/android-current/app/src/main/assets"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--room-manifest", type=Path, default=repo / "reconstruction/reverse-rooms/room_manifest.json")
    parser.add_argument("--ui-manifest", type=Path, default=assets_root_default / "presentation/ui/ui_manifest.json")
    parser.add_argument("--assets-manifest", type=Path, default=assets_root_default / "presentation/assets.json")
    parser.add_argument("--assets-root", type=Path, default=assets_root_default,
                        help="root containing the paths named by the presentation asset manifest")
    parser.add_argument("--output", type=Path, default=assets_root_default / "presentation/room_layers.json")
    parser.add_argument("--audit", type=Path, default=repo / "reconstruction/reverse-rooms/room_layers_audit.json")
    parser.add_argument("--check", action="store_true", help="validate staged metadata without writing it")
    args = parser.parse_args()
    try:
        staged, audit = make_output(read_json(args.room_manifest), read_json(args.ui_manifest),
                                    read_json(args.assets_manifest), args.assets_root)
        if args.check:
            if not args.output.is_file():
                raise ValueError(f"staged output does not exist: {args.output}")
            if read_json(args.output) != staged:
                raise ValueError(f"staged output is stale or differs from regenerated source: {args.output}")
            if not args.audit.is_file() or read_json(args.audit) != audit:
                raise ValueError(f"coverage audit is stale or missing: {args.audit}")
            print(f"validated {audit['totals']['rooms']} rooms, "
                  f"{audit['totals']['resolved_sprite_references']} resolved source sprite refs, "
                  f"{audit['totals']['visible_layers']} visible layers, "
                  f"{audit['totals']['excluded_layers']} excluded")
        else:
            write_json(args.output, staged)
            write_json(args.audit, audit)
            print(f"wrote {args.output} and {args.audit}")
            print(json.dumps(audit["totals"], sort_keys=True))
    except ValueError as exc:
        print(f"room layer staging failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
