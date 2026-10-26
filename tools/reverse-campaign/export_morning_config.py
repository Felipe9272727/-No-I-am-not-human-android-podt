#!/usr/bin/env python3
"""Export selected Unity serialized morning configuration without executing game code."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "restore-v10/unity-data"
DEFAULT_JSON = ROOT / "reconstruction/reverse-campaign/morning_config.json"
DEFAULT_HEADER = ROOT / "reconstruction/native-game/generated/morning_config.hpp"
TARGETS = {"OtherGameSOData", "EndingsSOData", "DayNightControllerSOData", "ObjectRoomObjectView"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def serializable(value):
    if isinstance(value, dict): return {str(k): serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [serializable(v) for v in value]
    if isinstance(value, bytes): return {"hex": value.hex(), "length": len(value)}
    if hasattr(value, "__dict__"):
        return {k: serializable(v) for k, v in value.__dict__.items() if not k.startswith("_")}
    if value is None or isinstance(value, (str, int, float, bool)): return value
    return str(value)


def parse_ptr(data, offset):
    file_id = struct.unpack_from("<i", data, offset)[0]
    path_id = struct.unpack_from("<q", data, offset + 4)[0]
    return {"file_id": file_id, "path_id": path_id}


def script_identity(environment, owner_file, data):
    ref = parse_ptr(data, 16)
    if ref["file_id"] == 0:
        target_file = owner_file
    else:
        external = owner_file.externals[ref["file_id"] - 1]
        target_file = next((f for f in environment.files.values() if f.name == Path(external.path).name), None)
    if target_file is None: return None
    obj = target_file.objects.get(ref["path_id"])
    if obj is None or obj.type.name != "MonoScript": return None
    tree = obj.read_typetree()
    return {"class": tree.get("m_ClassName", ""), "namespace": tree.get("m_Namespace", ""),
            "assembly": tree.get("m_AssemblyName", "")}


def component_header(data):
    if len(data) < 32: raise ValueError("MonoBehaviour header shorter than 32 bytes")
    string_length = struct.unpack_from("<i", data, 28)[0]
    if string_length < 0 or 32 + string_length > len(data): raise ValueError("invalid MonoBehaviour m_Name length")
    name = data[32:32 + string_length].decode("utf-8", "replace")
    custom = (32 + string_length + 3) & ~3
    return name, custom


def resolve_ref(environment, owner_file, pointer, type_name=None):
    if pointer["file_id"] == 0: target_file = owner_file
    else:
        external = owner_file.externals[pointer["file_id"] - 1]
        target_file = next((f for f in environment.files.values() if f.name == Path(external.path).name), None)
    target = target_file.objects.get(pointer["path_id"]) if target_file else None
    if not target: return {**pointer, "resolved": None}
    result = {**pointer, "asset_file": target_file.name, "asset_type": target.type.name}
    if target.type.name in ("Sprite", "Texture2D", "Material"):
        try: result["asset_name"] = target.peek_name()
        except Exception: pass
    if type_name and target.type.name != type_name: raise ValueError(f"reference expected {type_name}, found {target.type.name}")
    return result


def load_assets(paths):
    import UnityPy
    found = []
    env = UnityPy.load(str(paths[0].parent))
    file_paths = {f.name: Path(k) for k, f in env.files.items()}
    for owner_file in env.files.values():
        path = file_paths[owner_file.name]
        for obj in owner_file.objects.values():
            if obj.type.name != "MonoBehaviour": continue
            try:
                raw = obj.get_raw_data()
                script = script_identity(env, owner_file, raw)
                cls = script and script["class"]
                if cls not in TARGETS: continue
                name, custom = component_header(raw)
                record = {"source_file": str(path.relative_to(ROOT)), "source_sha256": digest(path.read_bytes()),
                          "path_id": obj.path_id, "class": cls, "namespace": script["namespace"],
                          "assembly": script["assembly"], "serialized_object_name": name,
                          "raw_object_sha256": digest(raw), "raw_object_bytes": len(raw),
                          "custom_payload_offset": custom, "raw_object_hex": raw.hex()}
                if cls == "OtherGameSOData":
                    count = struct.unpack_from("<i", raw, custom)[0]
                    array_end = custom + 4 + count * 4
                    if count < 0 or array_end > len(raw): raise ValueError("invalid _tvReportageCountByDay array length")
                    tv = list(struct.unpack_from(f"<{count}i", raw, custom + 4))
                    increment_offset = custom + 4 + count*4 + 8 + 8 + 4*5 + 8 + 52 + 24
                    # The 52-byte SerializedDictionary payload is retained verbatim; the next six fields are floats.
                    if increment_offset + 4 > len(raw): raise ValueError("_everyDayIncrement outside object")
                    record["decoded_fields"] = {"_tvReportageCountByDay": {"offset": custom, "values": tv},
                        "_deficitConsumables": {"offset": custom + 4 + count*4 + 8 + 8 + 4*5 + 8,
                                                  "raw_hex": raw[custom + 4 + count*4 + 8 + 8 + 4*5 + 8:increment_offset - 24].hex()},
                        "_badFemaRatingChance": {"offset": increment_offset - 24, "value": struct.unpack_from("<f", raw, increment_offset - 24)[0]},
                        "_takeGunAfterCheck": {"offset": increment_offset - 20, "value": struct.unpack_from("<f", raw, increment_offset - 20)[0]},
                        "_notTakeGunAfterCheck": {"offset": increment_offset - 16, "value": struct.unpack_from("<f", raw, increment_offset - 16)[0]},
                        "_isHuman": {"offset": increment_offset - 12, "value": struct.unpack_from("<f", raw, increment_offset - 12)[0]},
                        "_listenDialogFirstTime": {"offset": increment_offset - 8, "value": struct.unpack_from("<f", raw, increment_offset - 8)[0]},
                        "_listenDialogRepeat": {"offset": increment_offset - 4, "value": struct.unpack_from("<f", raw, increment_offset - 4)[0]},
                        "_everyDayIncrement": {"offset": increment_offset, "value": struct.unpack_from("<f", raw, increment_offset)[0]},
                        "parsed_prefix_bytes_end": increment_offset + 4}
                    # Fixed fields through Vector2Int are decoded to prove the byte boundary before the opaque dictionary.
                    record["decoded_fields"]["preceding_fixed_fields"] = {"_startKnockTime": struct.unpack_from("<2f", raw, array_end),
                        "_endKnockTime": struct.unpack_from("<2f", raw, array_end+8),
                        "_knockTimeProgressDuration": struct.unpack_from("<f", raw, array_end+16)[0],
                        "_radioDelta": struct.unpack_from("<f", raw, array_end+20)[0],
                        "_radioThresholdStart": struct.unpack_from("<f", raw, array_end+24)[0],
                        "_wrongStateMultiplier": struct.unpack_from("<f", raw, array_end+28)[0],
                        "_screamerOnImposterChance": struct.unpack_from("<f", raw, array_end+32)[0],
                        "_daysRange": struct.unpack_from("<2i", raw, array_end+36)}
                elif cls == "EndingsSOData":
                    fields = ["_killsCount", "_bodyEaterCount", "_prophetDontCheckSignsDaysNeeded", "_povistkasUsedCount", "_femaCallsCount"]
                    values = struct.unpack_from("<5i", raw, custom)
                    record["decoded_fields"] = {field: {"offset": custom + index*4, "value": values[index]} for index, field in enumerate(fields)}
                    if custom + 20 != len(raw): raise ValueError("EndingsSOData bytes not fully consumed")
                elif cls == "DayNightControllerSOData":
                    cursor = custom
                    n = struct.unpack_from("<i", raw, cursor)[0]; cursor += 4
                    if n < 0 or n > 32 or cursor + n*24 > len(raw): raise ValueError("invalid _volumeProfiles length")
                    profiles = []
                    for _ in range(n):
                        tod = struct.unpack_from("<i", raw, cursor)[0]; cursor += 4
                        profile = resolve_ref(env, owner_file, parse_ptr(raw, cursor)); cursor += 12
                        has_light = bool(raw[cursor]); cursor = (cursor + 4) & ~3
                        has_actions = bool(raw[cursor]); cursor = (cursor + 4) & ~3
                        profiles.append({"time_of_day": tod, "profile": profile, "has_light": has_light, "has_actions_count": has_actions})
                    materials = []
                    for _ in range(4): materials.append(resolve_ref(env, owner_file, parse_ptr(raw, cursor))); cursor += 12
                    arrays = []
                    for kind, fmt in (("int", "i"), ("float", "f"), ("int", "i")):
                        size = struct.unpack_from("<i", raw, cursor)[0]; cursor += 4
                        if size < 0 or size > (len(raw)-cursor)//4: raise ValueError("invalid DayNightControllerSOData array")
                        values = struct.unpack_from(f"<{size}{fmt}", raw, cursor) if size else ()
                        arrays.append({"offset": cursor-4, "values": list(values)}); cursor += size*4
                    fields = ["_lastDay", "_babyEndingDay", "_killerEndingDay", "_femaEndingDay", "_coffeeBoostDays"]
                    values = struct.unpack_from("<5i", raw, cursor)
                    decoded = {field: {"offset": cursor+i*4, "value": values[i]} for i, field in enumerate(fields)}
                    cursor += 20
                    if cursor != len(raw): raise ValueError(f"DayNightControllerSOData bytes consumed {cursor} of {len(raw)}")
                    record["decoded_fields"] = {"_volumeProfiles": profiles, "_materialRefs": materials,
                        "_maxDayActionsByDays": arrays[0], "_lensDistortionByDays": arrays[1],
                        "_colorsCountByDays": arrays[2], **decoded, "parsed_bytes_end": cursor, "unparsed_tail_bytes": len(raw)-cursor}
                else:
                    # MonoBehaviour base stores two serialized PPtrs before ObjectRoomObjectView fields.
                    arr_off = custom + 24
                    count = struct.unpack_from("<i", raw, arr_off)[0]
                    if count < 0 or count > 64: raise ValueError("invalid ObjectRoomObjectView state count")
                    states, cursor = [], arr_off + 4
                    for _ in range(count):
                        start = cursor
                        enum_value = struct.unpack_from("<i", raw, cursor)[0]; cursor += 4
                        sprite = parse_ptr(raw, cursor); cursor += 12
                        position = struct.unpack_from("<2f", raw, cursor); cursor += 8
                        scale = struct.unpack_from("<2f", raw, cursor); cursor += 8
                        cannot = bool(raw[cursor]); cursor += 1
                        cursor = (cursor + 3) & ~3
                        states.append({"offset": start, "enum_value": enum_value, "sprite": sprite, "position_shift": position, "scale_shift": scale, "cannot_interact": cannot})
                        states[-1]["enum_name"] = {0: "Bed", 1: "TV", 2: "Fridge"}.get(enum_value, f"Unknown({enum_value})")
                        states[-1]["sprite"] = resolve_ref(env, owner_file, sprite, "Sprite")
                    start_state_offset = cursor
                    start_state = struct.unpack_from("<i", raw, cursor)[0]; cursor += 4
                    if cursor != len(raw): raise ValueError(f"ObjectRoomObjectView bytes consumed {cursor} of {len(raw)}")
                    record["decoded_fields"] = {"_button_ptr": parse_ptr(raw, custom), "_image_ptr": parse_ptr(raw, custom+12),
                        "_states": {"offset": arr_off, "values": states}, "_startState": {"offset": start_state_offset, "value": start_state}, "bytes_consumed": cursor}
                found.append(record)
            except Exception as error:
                print(f"warning: {path}:{obj.path_id} skipped: {error}")
    return found


def int_field(record, name):
    value = record["serialized_fields"].get(name)
    if isinstance(value, bool) or not isinstance(value, int): raise ValueError(f"{record['class']}.{name}: expected serialized integer, got {value!r}")
    return value


def float_field(record, name):
    value = record["serialized_fields"].get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)): raise ValueError(f"{record['class']}.{name}: expected serialized number, got {value!r}")
    return float(value)


def make_header(by_class):
    other = by_class["OtherGameSOData"]
    end = by_class["EndingsSOData"]
    daynight = by_class["DayNightControllerSOData"]
    increment = float(other["decoded_fields"]["_everyDayIncrement"]["value"])
    prophet = int(end["decoded_fields"]["_prophetDontCheckSignsDaysNeeded"]["value"])
    coffee = int(daynight["decoded_fields"]["_coffeeBoostDays"]["value"])
    # Struct packing proves generated literals derive from IEEE-754 serialized value.
    bits = struct.unpack("<I", struct.pack("<f", increment))[0]
    return f'''#pragma once
// Generated by tools/reverse-campaign/export_morning_config.py from serialized Unity fields.
// Source object SHA256s are recorded in reconstruction/reverse-campaign/morning_config.json.
#include <cstdint>
namespace ninah::production::morning {{
inline constexpr float every_day_fema_increment = {increment:.9g}f; // IEEE-754 bits 0x{bits:08x}; OtherGameSOData._everyDayIncrement
inline constexpr std::int32_t prophet_no_signs_days = {prophet}; // EndingsSOData._prophetDontCheckSignsDaysNeeded
inline constexpr std::int32_t coffee_boost_days = {coffee}; // DayNightControllerSOData._coffeeBoostDays; serialized byte offset {daynight["decoded_fields"]["_coffeeBoostDays"]["offset"]}
}} // namespace ninah::production::morning
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--json", type=Path, default=DEFAULT_JSON)
    ap.add_argument("--header", type=Path, default=DEFAULT_HEADER)
    ns = ap.parse_args()
    paths = sorted(p for p in ns.input.rglob("*") if p.is_file() and p.suffix.lower() in (".assets", ""))
    if not paths: raise SystemExit(f"no Unity asset files found under {ns.input}")
    records = load_assets(paths)
    selected = {}
    for cls in ("OtherGameSOData", "EndingsSOData", "DayNightControllerSOData"):
        matches = [r for r in records if r["class"] == cls]
        if len(matches) != 1: raise SystemExit(f"expected exactly one {cls} object, found {len(matches)}")
        selected[cls] = matches[0]
    bed = [r for r in records if r["class"] == "ObjectRoomObjectView" and r["path_id"] == 4801]
    result = {"provenance": "Unity serialized raw fields parsed with UnityPy asset references plus Cpp2IL declarations; no original game executable/library run",
              "UnityPy": "1.25.4", "schema_sources": [
                  "restore-v10/checkpoint/reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/OtherGameData/OtherGameSOData.cs",
                  "restore-v10/checkpoint/reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/Endings/Data/EndingsSOData.cs",
                  "restore-v10/checkpoint/reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/DayNightControllerSOData.cs",
                  "restore-v10/checkpoint/reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Rooms/ObjectRoomObjectView.cs",
                  "restore-v10/checkpoint/reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Rooms/RoomObjectState`1.cs",
                  "restore-v10/checkpoint/reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Rooms/EObjectsRoomObject.cs"], "records": records,
              "constants": {"every_day_fema_increment": {"class": "OtherGameSOData", "serialized_field": "_everyDayIncrement", "value": selected["OtherGameSOData"]["decoded_fields"]["_everyDayIncrement"]["value"], "serialized_byte_offset": selected["OtherGameSOData"]["decoded_fields"]["_everyDayIncrement"]["offset"], "declared_field_offset": "0x70", "declared_type": "float"},
                            "prophet_no_signs_days": {"class": "EndingsSOData", "serialized_field": "_prophetDontCheckSignsDaysNeeded", "value": selected["EndingsSOData"]["decoded_fields"]["_prophetDontCheckSignsDaysNeeded"]["value"], "serialized_byte_offset": selected["EndingsSOData"]["decoded_fields"]["_prophetDontCheckSignsDaysNeeded"]["offset"], "declared_field_offset": "0x20", "declared_type": "int"},
                            "coffee_boost_days": {"class": "DayNightControllerSOData", "serialized_field": "_coffeeBoostDays", "value": selected["DayNightControllerSOData"]["decoded_fields"]["_coffeeBoostDays"]["value"], "serialized_byte_offset": selected["DayNightControllerSOData"]["decoded_fields"]["_coffeeBoostDays"]["offset"], "declared_field_offset": "0x68", "declared_type": "int", "raw_object_sha256": selected["DayNightControllerSOData"]["raw_object_sha256"]}},
              "bed_object_room_object_views": bed,
              "bed_render_application": {"source": "restore-v10/checkpoint/reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/Rooms/ARoomObjectView`1.txt, SelectState(T state)",
                  "evidence": [{"isil_instruction": 71, "call": "Image.set_sprite", "meaning": "Image receives selected state's Sprite reference."},
                              {"isil_instructions": [75, 90], "call": "Transform.set_localPosition", "meaning": "selected PositionShift components are assembled directly into the localPosition Vector3 and assigned."},
                              {"isil_instructions": [94, 108], "call": "Transform.set_localScale", "meaning": "selected ScaleShift components are assembled directly into localScale and assigned."}],
                  "equations": {"final_local_position_xy": "state.PositionShift", "final_local_scale_xy": "state.ScaleShift"},
                  "not_in_method": ["No additive-to-home-position operation appears in SelectState.", "No SetNativeSize, Image.rectTransform.sizeDelta, or sprite-size setter appears in SelectState."],
                  "bed_component_4801_result": {"state": "Bed", "local_position": [132.0, -323.0], "local_scale": [2.0999999046325684, 2.0999999046325684], "sprite": "Livingroom2_obj1"}},
              "tv_reportage_count_by_day": {"serialized_field": "_tvReportageCountByDay", "serialized_byte_offset": selected["OtherGameSOData"]["decoded_fields"]["_tvReportageCountByDay"]["offset"], "array_values": selected["OtherGameSOData"]["decoded_fields"]["_tvReportageCountByDay"]["values"], "index_1_value": selected["OtherGameSOData"]["decoded_fields"]["_tvReportageCountByDay"]["values"][1], "indexing_note": "The serialized array has value 1 at index 1. This is consistent with a day-1 slot, but no managed consumer was recovered to prove the index convention."},
              "notes": ["All serialized fields and raw object hashes are retained in records.", "Unknown or public-status-related fields are left as serialized and are not assigned inferred semantics."]}
    ns.json.parent.mkdir(parents=True, exist_ok=True); ns.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ns.header.parent.mkdir(parents=True, exist_ok=True); ns.header.write_text(make_header(selected), encoding="utf-8")
    print(f"wrote {ns.json} and {ns.header}; exported {len(records)} matching objects; bed object view 4801={len(bed)}")


if __name__ == "__main__": main()
