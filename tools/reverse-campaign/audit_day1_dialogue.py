#!/usr/bin/env python3
"""Static route inventory for selected day-1 dialogue; never executes game code."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = ROOT / "reconstruction/android-current/app/src/main/assets/narrative/program.json"
TEXTS = ROOT / "reconstruction/android-current/app/src/main/assets/narrative/texts_ptbr.json"
OUT = ROOT / "reconstruction/reverse-campaign/day1_dialogue_audit.json"
REPORT = ROOT / "reconstruction/reverse-campaign/day1_dialogue_audit.md"
STARTS = ["tv_1_necessary", "entrance_daughter_1", "Esenin_Entrance_11", "Anxiety_Entrance_11"]

# Supported command prefixes are taken from native-game command/scene routers.
SUPPORTED = {"GetItem", "LetIn", "AggressiveLetIn", "Refuse", "Kill", "KillTomorrow",
             "ExileCharacter", "ExileAfterTomorrow", "ExileByFEMA", "OrderCourier", "UpdateDeficitDay",
             "KillRoom", "SetEmotion", "SetupGun", "DontSetupGun", "ShowSign", "ShowPlayerSign",
             "StopShowingSign", "ChangePose", "ChangePoseTomorrow", "BeginCultists", "SaveCultists",
             "UnlockDeathEnding", "UnlockMushroomEnding", "VigilanteRevealsPlayer", "GetAchievement", "Ending"}


def scan_node(name, node):
    ins = node.get("instructions", [])
    commands, functions, edges = [], [], []
    for i, op in enumerate(ins):
        args = op.get("operands", [])
        if op.get("opcode_name") == "RunCommand" and args:
            command = str(args[0])
            word = command.split(" ", 1)[0]
            commands.append({"instruction": i, "text": command,
                             "host_dispatch": "supported" if word in SUPPORTED else "unsupported_or_unmapped"})
        elif op.get("opcode_name") == "CallFunc" and args:
            functions.append({"instruction": i, "name": args[0]})
        elif op.get("opcode_name") == "RunNode" and i and ins[i-1].get("opcode_name") == "PushString":
            edges.append({"instruction": i, "target": ins[i-1].get("operands", [None])[0]})
    return {"name": name, "commands": commands, "functions": functions, "run_node_edges": edges}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=OUT)
    args = ap.parse_args()
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    nodes = program["nodes"]
    inventory, missing, seen = {}, [], set()
    todo = list(STARTS)
    while todo:
        name = todo.pop(0)
        if name in seen: continue
        seen.add(name)
        if name not in nodes:
            missing.append(name); continue
        entry = scan_node(name, nodes[name]); inventory[name] = entry
        todo.extend(e["target"] for e in entry["run_node_edges"] if e["target"] and e["target"] not in seen)
    route_nodes = {s: reachable(s, inventory) for s in STARTS}
    result = {
        "scope": "static only; compiled Yarn bytecode and recovered text metadata; original executable/libraries not run",
        "sources": [str(PROGRAM.relative_to(ROOT)), "restore-v10/checkpoint/reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/Rooms/EntranceRoom.txt", "reconstruction/native-game/src/dialogue_services.cpp", "reconstruction/native-game/src/dialogue_commands.cpp", "reconstruction/native-game/src/scene_commands.cpp"],
        "routes": {s: {"reachable_nodes": sorted(route_nodes[s]),
                        "start_present": s in nodes} for s in STARTS},
        "nodes": inventory, "missing_node_targets": sorted(set(missing)),
        "schedule_evidence": {"day": 1, "preset_visits": ["Daughter (guest 1)", "Esenin (guest 2)", "Anxiety (guest 3)"],
                              "meaning": "preset schedule only; does not establish actual arrival/order or event generation"},
        "entrance_resolution": {"source": "EntranceRoom.GetDialogName recovered disassembly, lines 392 onward", "finding": "Daughter's first preset visit maps to entrance_daughter_1 according to checkpoint reconstruction notes; disassembly indicates a branch on character identity/category and visit state, but recovered text is native disassembly rather than managed C# source, so exact index/visited-bit field mapping is not claimed here."},
        "morning_tv": {"found_named_node": False, "candidate_node": "tv_1_necessary", "caveat": "No node named morningTV/morning_tv was found. The TV Yarn node is dialogue content, not proof an event is scheduled or reachable in the day-start sequence."},
        "integration_conclusion": "Only manually starting recovered nodes can be considered for the next integration slice. Day/night transition, initialization callbacks, day-1 event generation and arrival ordering are not established by this node inventory. Do not synthesize missing commands or infer arrival from preset slots."
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(render_report(result), encoding="utf-8")


def reachable(start, inventory):
    todo, seen = [start], set()
    while todo:
        n = todo.pop()
        if n in seen: continue
        seen.add(n)
        todo.extend(e["target"] for e in inventory.get(n, {}).get("run_node_edges", []))
    return seen


def render_report(data):
    lines = ["# Day-1 dialogue static audit", "",
             "Static analysis of the recovered compiled Yarn program and current host dispatch. No original game binary or library was executed.", "",
             "## Findings", "",
             "The preset schedule lists Daughter (guest 1), Esenin (guest 2), and Anxiety (guest 3). This establishes schedule configuration only; it does not establish actual day-start arrivals or their event order.", "",
             "The recovered entrance room resolves the first Daughter visit to `entrance_daughter_1` in the checkpoint notes. Its Yarn node has two authored options and branches into Daughter entrance subnodes. The native disassembly does not expose managed field names for the visit index/visited bit, so this audit preserves that mapping as checkpoint-reported rather than claiming a field-level reconstruction.", "",
             "No node named `morningTV` or `morning_tv` exists. `tv_1_necessary` is present as the TV dialogue candidate, but its presence does not prove event generation or the morning sequence.", "",
             "## Routes and reachable nodes", ""]
    for start, route in data["routes"].items():
        lines += [f"### `{start}`", "", f"Present: **{route['start_present']}**. Static RunNode closure: {', '.join('`'+n+'`' for n in route['reachable_nodes']) or '(none detected)'}.", ""]
    lines += ["## Command/function inventory", "", "Each node includes exact extracted RunCommand text and CallFunc names in the adjacent JSON inventory. Host status reflects the current typed dialogue and scene dispatchers; a recognized command may still require runtime providers or presentation assets.", ""]
    for name, node in sorted(data["nodes"].items()):
        if node["commands"] or node["functions"]:
            cs = "; ".join(f"`{c['text']}` ({c['host_dispatch']})" for c in node["commands"]) or "none"
            fs = ", ".join(f"`{f['name']}`" for f in node["functions"]) or "none"
            lines.append(f"- `{name}` — commands: {cs}; functions: {fs}.")
    lines += ["", "## Integration boundary", "", "A deterministic next slice may invoke recovered nodes directly after the existing host reaches a supported state. `IsCharacterPlaceEmpty` and `GetCharacterOnPlace` are in the current game-function adapter. `LetIn`, `AggressiveLetIn`, `Refuse`, and `ExileCharacter` have command models, but LetIn needs production inputs, ExileCharacter may need its dialog callback, and commands such as `ChangeState Beer1 1` are unsupported by the current generic dispatcher. The night-to-day transition, initialization callbacks, day-1 event generation, and actual arrival ordering remain blockers; do not claim the preset entries prove those stages.", "", "Machine-readable node-by-node route and dispatcher inventory: [`day1_dialogue_audit.json`](day1_dialogue_audit.json).", ""]
    return "\n".join(lines)


if __name__ == "__main__": main()
