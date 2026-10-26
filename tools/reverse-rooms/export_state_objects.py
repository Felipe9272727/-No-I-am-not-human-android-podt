#!/usr/bin/env python3
"""Export serialized StateObjectsViewProvider tables from Unity assets.

Reads level1 and globalgamemanagers.assets only; does not load or execute the game.
"""
from __future__ import annotations
import argparse
import json
import struct
from pathlib import Path
import UnityPy

STATE_OBJECT_TYPES = {
    0: "Carpet", 1: "Ground", 2: "WindowBoardsTriggers",
    3: "PeepholeEndingTrigger", 4: "HatchEnter", 5: "Apple",
    6: "Clock", 7: "Mushroom", 8: "Mushroomlist",
    9: "CultistsSheets", 10: "Husband", 11: "BathWater",
    12: "TunnelBlocker", 13: "Beer1", 14: "Beer2",
    15: "BlackHole", 16: "HoleInteract",
}
PROVIDER = "_Code.Infrastructure.StateObjects.StateObjectsViewProvider"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="Unity data directory")
    ap.add_argument("--out", type=Path, required=True, help="output JSON path")
    args = ap.parse_args()
    env = UnityPy.Environment()
    env.load_file(str(args.data / "level1"))
    env.load_file(str(args.data / "globalgamemanagers.assets"))
    files = {Path(f.name).name: f for f in env.files.values()}
    scene, manager = files["level1"], files["globalgamemanagers.assets"]

    scripts = {}
    for obj in manager.objects.values():
        if obj.type.name == "MonoScript":
            data = obj.read()
            name = f"{data.m_Namespace}.{data.m_ClassName}" if data.m_Namespace else str(data.m_ClassName)
            scripts[obj.path_id] = name
    game_objects = {
        obj.path_id: obj.read_typetree()["m_Name"]
        for obj in scene.objects.values() if obj.type.name == "GameObject"
    }
    providers = []
    for obj in scene.objects.values():
        if obj.type.name != "MonoBehaviour":
            continue
        raw = obj.get_raw_data()
        if len(raw) < 32:
            continue
        script_id = struct.unpack_from("<q", raw, 20)[0]
        if scripts.get(script_id) == PROVIDER:
            providers.append((obj.path_id, raw))
    if len(providers) != 1:
        raise SystemExit(f"expected exactly one {PROVIDER}, found {len(providers)}")

    provider_id, raw = providers[0]
    offset = 32  # Unity MonoBehaviour serialized prefix.
    count, = struct.unpack_from("<i", raw, offset)
    offset += 4
    if count < 0 or count > 1000:
        raise SystemExit(f"invalid state object count {count}")
    entries = []
    for _ in range(count):
        kind, states_count = struct.unpack_from("<ii", raw, offset)
        offset += 8
        if states_count < 0 or states_count > 1000:
            raise SystemExit(f"invalid state count {states_count} for enum {kind}")
        states = []
        for index in range(states_count):
            file_id, path_id = struct.unpack_from("<iq", raw, offset)
            offset += 12
            if file_id not in (0,):
                raise SystemExit(f"unexpected external file reference {file_id} in state table")
            states.append({
                "index": index,
                "game_object_path_id": path_id or None,
                "game_object_name": game_objects.get(path_id) if path_id else None,
            })
        entries.append({
            "enum_value": kind,
            "enum_name": STATE_OBJECT_TYPES.get(kind, f"Unknown({kind})"),
            "states": states,
        })
    if offset != len(raw):
        raise SystemExit(f"provider schema consumed {offset} bytes, raw component is {len(raw)}")
    result = {
        "evidence": {
            "asset": "level1",
            "provider_component_path_id": provider_id,
            "provider_type": PROVIDER,
            "provider_raw_size": len(raw),
            "schema": "MonoBehaviour prefix (32 bytes), serialized StateObjet[]; each record is enum int32 plus GameObject[] of PPtrs",
            "enum_source": "_Code.Infrastructure.StateObjects.EStateObjectType.cs in recovered C# source",
        },
        "state_objects": entries,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"state_objects={len(entries)} provider_path_id={provider_id} output={args.out}")


if __name__ == "__main__":
    main()
