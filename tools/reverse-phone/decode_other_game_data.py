#!/usr/bin/env python3
"""Decode selected Unity MonoBehaviour records from sharedassets0.assets only.

Uses UnityPy only to locate objects and obtain their raw serialized bytes. All
field decoding below follows the retained Cpp2IL declarations and is bounded
by explicit schema and byte-consumption checks. Game binaries are never run.
"""

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

import UnityPy

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSET = (
    ROOT
    / "malware-review/No.Im.not.a.Human.v1.3.18/No.Im.not.a.Human.v1.3.18/"
    "NoImNotAHuman_Data/sharedassets0.assets"
)
OUT_DIR = ROOT / "reconstruction/reverse-phone"
EXPECTED_HASHES = {
    2715: "f6c54b961c02a810320592e3ceb28c329e62a0134193ae26f47f0cd994d73a2f",
    2713: "ef6c10b872d01dfbe0ea26a1fcbb6df7e175ca7cfce690a8d697043f88766d5c",
}
EXPECTED_ASSET_SHA256 = "99a6ae7df177512a9fb2c27bb7c89e6fb8e1c14227fdd7b12e9fa42e564fb1d9"
EXPECTED_FIELD_OFFSETS = {
    "_tvReportageCountByDay": 48,
    "_startKnockTime": 128,
    "_endKnockTime": 136,
    "_knockTimeProgressDuration": 144,
    "_radioDelta": 148,
    "_radioThresholdStart": 152,
    "_wrongStateMultiplier": 156,
    "_screamerOnImposterChance": 160,
    "_daysRange": 164,
    "_deficitConsumables": 172,
    "_badFemaRatingChance": 224,
    "_takeGunAfterCheck": 228,
    "_notTakeGunAfterCheck": 232,
    "_isHuman": 236,
    "_listenDialogFirstTime": 240,
    "_listenDialogRepeat": 244,
    "_everyDayIncrement": 248,
    "_dreams": 252,
    "_phoneNumbers": 304,
}
DECL = ROOT / "reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code"


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def take(self, size: int) -> bytes:
        if size < 0 or self.offset + size > len(self.data):
            raise ValueError(f"read outside raw object at offset {self.offset}, size {size}")
        start = self.offset
        self.offset += size
        return self.data[start:self.offset]

    def align4(self) -> None:
        self.offset = (self.offset + 3) & ~3
        if self.offset > len(self.data):
            raise ValueError("alignment exceeds raw object length")

    def i32(self) -> int:
        return struct.unpack("<i", self.take(4))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self.take(4))[0]

    def boolean(self) -> bool:
        value = self.take(1)[0]
        if value not in (0, 1):
            raise ValueError(f"invalid serialized bool {value} at offset {self.offset - 1}")
        self.align4()
        return bool(value)

    def int_array(self, maximum: int = 512) -> list[int]:
        count_at = self.offset
        count = self.i32()
        if count < 0 or count > maximum:
            raise ValueError(f"invalid array length {count} at offset {count_at}")
        return [self.i32() for _ in range(count)]

    def string(self) -> str:
        size_at = self.offset
        size = self.i32()
        if size < 0 or size > len(self.data) - self.offset:
            raise ValueError(f"invalid string length {size} at offset {size_at}")
        value = self.take(size).decode("utf-8", "strict")
        self.align4()
        return value

    def finish(self) -> None:
        if self.offset != len(self.data):
            raise ValueError(f"schema consumed {self.offset}/{len(self.data)} bytes")


def enum_values(path: Path) -> dict[int, str]:
    text = path.read_text(encoding="utf-8")
    pairs = re.findall(r"^\s*(\w+)\s*=\s*(-?\d+)\s*,?\s*$", text, re.M)
    if not pairs:
        raise ValueError(f"no enum values found in {path}")
    return {int(value): name for name, value in pairs}


def enum_name(mapping: dict[int, str], value: int) -> str:
    if value not in mapping:
        raise ValueError(f"unknown enum value {value}")
    return mapping[value]


def base_header(raw: bytes, expected_name: str) -> tuple[Reader, dict]:
    if len(raw) < 32:
        raise ValueError("truncated Unity MonoBehaviour header")
    file_id = struct.unpack_from("<i", raw, 16)[0]
    script_path_id = struct.unpack_from("<q", raw, 20)[0]
    name_size = struct.unpack_from("<I", raw, 28)[0]
    if name_size > len(raw) - 32:
        raise ValueError("invalid MonoBehaviour m_Name length")
    name = raw[32:32 + name_size].decode("utf-8", "strict")
    if name != expected_name:
        raise ValueError(f"expected m_Name {expected_name!r}, got {name!r}")
    data_offset = (32 + name_size + 3) & ~3
    return Reader(raw[data_offset:]), {
        "m_name": name,
        "script_ref": {"file_id": file_id, "path_id": script_path_id},
        "serialized_data_offset": data_offset,
    }


def find_raw(asset: Path, path_id: int) -> bytes:
    environment = UnityPy.load(str(asset))
    matches = [obj for obj in environment.objects if obj.path_id == path_id]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one object path_id {path_id}, found {len(matches)}")
    obj = matches[0]
    if obj.type.name != "MonoBehaviour":
        raise ValueError(f"path_id {path_id} is {obj.type.name}, expected MonoBehaviour")
    return obj.get_raw_data()


def decode_other_game_data(raw: bytes) -> dict:
    r, header = base_header(raw, "OtherGameData")
    consumables = enum_values(DECL / "Infrastructure/Consumables/EConsumable.cs")
    subscribers = enum_values(DECL / "Infrastructure/CloseUps/Views/Phone/EPhoneSubscriber.cs")
    dreams = enum_values(DECL / "Infrastructure/_NINAH__Dream/EDream.cs")
    sounds = enum_values(DECL / "Infrastructure/Sound/ESound.cs")

    field_offsets = {}
    field_offsets["_tvReportageCountByDay"] = header["serialized_data_offset"] + r.offset
    tv_counts = r.int_array(maximum=64)
    field_offsets["_startKnockTime"] = header["serialized_data_offset"] + r.offset
    start_knock_time = [r.f32(), r.f32()]
    field_offsets["_endKnockTime"] = header["serialized_data_offset"] + r.offset
    end_knock_time = [r.f32(), r.f32()]
    field_offsets["_knockTimeProgressDuration"] = header["serialized_data_offset"] + r.offset
    knock_time_progress_duration = r.f32()
    field_offsets["_radioDelta"] = header["serialized_data_offset"] + r.offset
    radio_delta = r.f32()
    field_offsets["_radioThresholdStart"] = header["serialized_data_offset"] + r.offset
    radio_threshold_start = r.f32()
    field_offsets["_wrongStateMultiplier"] = header["serialized_data_offset"] + r.offset
    wrong_state_multiplier = r.f32()
    field_offsets["_screamerOnImposterChance"] = header["serialized_data_offset"] + r.offset
    screamer_on_imposter_chance = r.f32()
    field_offsets["_daysRange"] = header["serialized_data_offset"] + r.offset
    days_range = [r.i32(), r.i32()]

    field_offsets["_deficitConsumables"] = header["serialized_data_offset"] + r.offset
    deficit_count = r.i32()
    if deficit_count < 0 or deficit_count > len(consumables):
        raise ValueError(f"invalid deficit dictionary entry count {deficit_count}")
    deficit_consumables = []
    for _ in range(deficit_count):
        key = r.i32()
        value = r.i32()
        deficit_consumables.append({
            "key_value": key,
            "key": enum_name(consumables, key),
            "value": value,
        })

    field_offsets["_badFemaRatingChance"] = header["serialized_data_offset"] + r.offset
    bad_fema_rating_chance = r.f32()
    field_offsets["_takeGunAfterCheck"] = header["serialized_data_offset"] + r.offset
    take_gun_after_check = r.f32()
    field_offsets["_notTakeGunAfterCheck"] = header["serialized_data_offset"] + r.offset
    not_take_gun_after_check = r.f32()
    field_offsets["_isHuman"] = header["serialized_data_offset"] + r.offset
    is_human = r.f32()
    field_offsets["_listenDialogFirstTime"] = header["serialized_data_offset"] + r.offset
    listen_dialog_first_time = r.f32()
    field_offsets["_listenDialogRepeat"] = header["serialized_data_offset"] + r.offset
    listen_dialog_repeat = r.f32()
    field_offsets["_everyDayIncrement"] = header["serialized_data_offset"] + r.offset
    every_day_increment = r.f32()

    field_offsets["_dreams"] = header["serialized_data_offset"] + r.offset
    dream_count = r.i32()
    if dream_count < 0 or dream_count > 128:
        raise ValueError(f"invalid dreams array length {dream_count}")
    dream_records = []
    for _ in range(dream_count):
        dream_value = r.i32()
        scene_index = r.i32()
        has_music = r.boolean()
        music_value = r.i32()
        dream_records.append({
            "dream_value": dream_value,
            "dream": enum_name(dreams, dream_value),
            "scene_index": scene_index,
            "has_music": has_music,
            "music_value": music_value,
            "music": enum_name(sounds, music_value),
        })

    field_offsets["_phoneNumbers"] = header["serialized_data_offset"] + r.offset
    phone_count = r.i32()
    if phone_count < 0 or phone_count > len(subscribers):
        raise ValueError(f"invalid phone dictionary entry count {phone_count}")
    phone_numbers = []
    for _ in range(phone_count):
        subscriber_value = r.i32()
        number = r.string()
        if len(number) != 6 or not number.isascii() or not number.isdigit():
            raise ValueError(f"invalid six-digit phone number {number!r}")
        phone_numbers.append({
            "subscriber_value": subscriber_value,
            "subscriber": enum_name(subscribers, subscriber_value),
            "number": number,
        })
    r.finish()

    if len({row["subscriber_value"] for row in phone_numbers}) != len(phone_numbers):
        raise ValueError("duplicate phone subscriber in serialized dictionary")
    return {
        **header,
        "class": "_Code.Infrastructure.OtherGameData.OtherGameSOData",
        "field_offsets_raw_object_bytes": field_offsets,
        "values": {
            "tv_reportage_count_by_day": tv_counts,
            "start_knock_time": start_knock_time,
            "end_knock_time": end_knock_time,
            "knock_time_progress_duration": knock_time_progress_duration,
            "radio_delta": radio_delta,
            "radio_threshold_start": radio_threshold_start,
            "wrong_state_multiplier": wrong_state_multiplier,
            "screamer_on_imposter_chance": screamer_on_imposter_chance,
            "days_range": days_range,
            "deficit_consumables": deficit_consumables,
            "bad_fema_rating_chance": bad_fema_rating_chance,
            "take_gun_after_check": take_gun_after_check,
            "not_take_gun_after_check": not_take_gun_after_check,
            "is_human": is_human,
            "listen_dialog_first_time": listen_dialog_first_time,
            "listen_dialog_repeat": listen_dialog_repeat,
            "every_day_increment": every_day_increment,
            "dreams": dream_records,
            "phone_numbers": phone_numbers,
        },
        "parsed_data_bytes": r.offset,
        "parsed_raw_bytes_end": header["serialized_data_offset"] + r.offset,
        "unparsed_tail_bytes": len(raw) - header["serialized_data_offset"] - r.offset,
    }


def decode_endings_data(raw: bytes) -> dict:
    r, header = base_header(raw, "EndingsData")
    names = [
        "kills_count",
        "body_eater_count",
        "prophet_dont_check_signs_days_needed",
        "povistkas_used_count",
        "fema_calls_count",
    ]
    values = {name: r.i32() for name in names}
    r.finish()
    return {
        **header,
        "class": "_Code.Infrastructure.Endings.Data.EndingsSOData",
        "values": values,
        "parsed_data_bytes": r.offset,
        "parsed_raw_bytes_end": header["serialized_data_offset"] + r.offset,
        "unparsed_tail_bytes": len(raw) - header["serialized_data_offset"] - r.offset,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sharedassets", type=Path, default=DEFAULT_ASSET)
    args = parser.parse_args()
    asset = args.sharedassets.resolve()
    if not asset.is_file() or asset.name != "sharedassets0.assets":
        parser.error("--sharedassets must point to the recovered sharedassets0.assets file")
    asset_hash = hashlib.sha256(asset.read_bytes()).hexdigest()
    if asset_hash != EXPECTED_ASSET_SHA256:
        raise SystemExit(
            f"sharedassets0.assets SHA256 mismatch: {asset_hash} != {EXPECTED_ASSET_SHA256}"
        )

    raw_objects = {}
    for path_id, expected_hash in EXPECTED_HASHES.items():
        raw = find_raw(asset, path_id)
        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash != expected_hash:
            raise SystemExit(
                f"path_id {path_id} raw SHA256 mismatch: {actual_hash} != {expected_hash}"
            )
        raw_objects[path_id] = raw

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path_id, raw in raw_objects.items():
        (OUT_DIR / f"raw{path_id}.bin").write_bytes(raw)

    decoded = decode_other_game_data(raw_objects[2715])
    if decoded["field_offsets_raw_object_bytes"] != EXPECTED_FIELD_OFFSETS:
        raise SystemExit("OtherGameData field offsets do not match the declared serialized layout")
    raw_sha256 = hashlib.sha256(raw_objects[2715]).hexdigest()
    endings_hash = hashlib.sha256(raw_objects[2713]).hexdigest()
    endings_check = decode_endings_data(raw_objects[2713])
    result = {
        "method": "Static raw Unity MonoBehaviour parse using retained Cpp2IL declarations; UnityPy enumerates and extracts only requested objects; no PE/DLL execution.",
        "source": {
            "asset_file": "sharedassets0.assets",
            "asset_sha256": asset_hash,
            "path_id": 2715,
            "raw_file": "raw2715.bin",
            "raw_bytes": len(raw_objects[2715]),
            "raw_sha256": raw_sha256,
            "class": decoded["class"],
            "schema_file": "reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/OtherGameData/OtherGameSOData.cs",
        },
        "enum_sources": [
            "reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/Consumables/EConsumable.cs",
            "reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/CloseUps/Views/Phone/EPhoneSubscriber.cs",
            "reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/_NINAH__Dream/EDream.cs",
            "reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/Sound/ESound.cs",
        ],
        "field_layout": [
            "_tvReportageCountByDay: int[]",
            "_startKnockTime: Vector2",
            "_endKnockTime: Vector2",
            "_knockTimeProgressDuration: float",
            "_radioDelta: float",
            "_radioThresholdStart: float",
            "_wrongStateMultiplier: float",
            "_screamerOnImposterChance: float",
            "_daysRange: Vector2Int",
            "_deficitConsumables: SerializedDictionary<EConsumable,int> serialized as count followed by key/value pairs",
            "_badFemaRatingChance, _takeGunAfterCheck, _notTakeGunAfterCheck, _isHuman, _listenDialogFirstTime, _listenDialogRepeat, _everyDayIncrement: float",
            "_dreams: DreamData[]; each value has enum, scene index, aligned serialized bool, ESound enum",
            "_phoneNumbers: SerializedDictionary<EPhoneSubscriber,string> serialized as count followed by key/length-prefixed string pairs",
        ],
        "layout_note": "For this source object, m_Name has 13 UTF-8 bytes beginning at raw offset 32; its end is padded to the 4-byte aligned serialized-data start at raw offset 48. DreamData bool bytes are padded to 4-byte alignment before ESound. The explicit raw field offsets are retained below, and the schema consumes through byte 356 with no tail.",
        "verified_related_objects": [
            {
                "source_asset": "sharedassets0.assets",
                "source_asset_sha256": asset_hash,
                "path_id": 2713,
                "raw_file": "raw2713.bin",
                "raw_bytes": len(raw_objects[2713]),
                "raw_sha256": endings_hash,
                "class": endings_check["class"],
                "schema_file": "reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/Endings/Data/EndingsSOData.cs",
                "values": endings_check["values"],
                "parsed_raw_bytes_end": endings_check["parsed_raw_bytes_end"],
                "unparsed_tail_bytes": endings_check["unparsed_tail_bytes"],
            }
        ],
        **decoded,
    }
    (OUT_DIR / "other_game_data.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    fixed_numbers = {
        "evidence_status": "verified_from_raw_unity_asset_static_parse",
        "source_object": {
            "asset_file": "sharedassets0.assets",
            "asset_sha256": asset_hash,
            "path_id": 2715,
            "raw_file": "raw2715.bin",
            "raw_bytes": len(raw_objects[2715]),
            "raw_sha256": raw_sha256,
            "name": "OtherGameData",
            "type": decoded["class"],
            "field": "_phoneNumbers",
            "field_type": "SerializedDictionary<EPhoneSubscriber, string>",
        },
        "schema_source": "reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/OtherGameData/OtherGameSOData.cs",
        "enum_source": "reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/CloseUps/Views/Phone/EPhoneSubscriber.cs",
        "numbers": [
            {**row, "value_evidence": "verified_from_raw_unity_asset_static_parse"}
            for row in decoded["values"]["phone_numbers"]
        ],
    }
    (OUT_DIR / "phone_fixed_numbers.json").write_text(
        json.dumps(fixed_numbers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(json.dumps({
        "sharedassets0_sha256": asset_hash,
        "other_game_data": {
            "path_id": 2715,
            "raw_bytes": len(raw_objects[2715]),
            "raw_sha256": raw_sha256,
            "parsed_data_bytes": decoded["parsed_data_bytes"],
            "unparsed_tail_bytes": decoded["unparsed_tail_bytes"],
            "phone_numbers": decoded["values"]["phone_numbers"],
        },
        "endings_data_verification": {
            "path_id": 2713,
            "raw_bytes": len(raw_objects[2713]),
            "raw_sha256": endings_hash,
            "parsed_values": endings_check["values"],
            "unparsed_tail_bytes": endings_check["unparsed_tail_bytes"],
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
