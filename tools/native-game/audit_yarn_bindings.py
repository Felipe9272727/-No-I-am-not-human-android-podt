#!/usr/bin/env python3
"""Audit Yarn command/function usage against recovered game API bindings.

This is a static inventory only. It reads the decoded Yarn program, the generated
API map, and Cpp2IL-generated IL headings; it does not execute game binaries.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = ROOT / "reconstruction/narrative/program.json"
API_MAP = ROOT / "reconstruction/logic/yarn_api_map.md"
IL = ROOT / "reconstruction/logic/selected_method_bodies.il"
OUT = ROOT / "reconstruction/native-game/YARN_BINDINGS.json"

MAP_ROW = re.compile(r"^\|\s*(Command|Function)\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|$")
IL_HEAD = re.compile(r"^###\s+(.+?)\s+\[RVA\s+0x[0-9A-Fa-f]+,")


def main() -> None:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    rows = []
    for line in API_MAP.read_text(encoding="utf-8").splitlines():
        match = MAP_ROW.match(line)
        if match:
            rows.append({"kind": match[1].lower(), "name": match[2], "signature": match[3]})
    il_names = []
    for line in IL.read_text(encoding="utf-8").splitlines():
        match = IL_HEAD.match(line)
        if match:
            il_names.append(match[1].rsplit("::", 1)[-1])
    il_counts = Counter(il_names)

    command_uses: Counter[str] = Counter()
    function_uses: Counter[str] = Counter()
    function_arity: dict[str, Counter[int]] = {}
    opcode_counts: Counter[str] = Counter()
    node_count = len(program.get("nodes", {}))
    choices = 0
    tags_present = 0
    tags_total = 0
    headers_total = 0
    nodes_with_headers = 0
    unknown_command_forms: Counter[str] = Counter()
    for node in program.get("nodes", {}).values():
        tags = node.get("tags", []) or []
        tags_total += len(tags)
        tags_present += bool(tags)
        headers = node.get("headers", []) or []
        headers_total += len(headers)
        nodes_with_headers += bool(headers)
        for ins in node.get("instructions", []):
            op = ins.get("opcode_name", "Unknown")
            opcode_counts[op] += 1
            args = ins.get("operands", [])
            if op == "AddOption":
                choices += 1
            elif op == "RunCommand" and args and isinstance(args[0], str):
                # Yarn command text begins with the registered command name;
                # preserve the complete first token and count malformed forms.
                parts = args[0].split()
                if parts:
                    command_uses[parts[0]] += 1
                else:
                    unknown_command_forms["empty RunCommand operand"] += 1
            elif op == "CallFunc" and args and isinstance(args[0], str):
                name = args[0]
                function_uses[name] += 1
                # The compiled instruction's operands contain the function name;
                # stack-based arity is separately not encoded here.
                function_arity.setdefault(name, Counter())[len(args) - 1] += 1

    bindings = []
    for row in rows:
        uses = command_uses if row["kind"] == "command" else function_uses
        method_match = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", row["signature"])
        method = method_match.group(1) if method_match else ""
        body_count = il_counts.get(method, 0)
        bindings.append({
            **row,
            "game_method": method,
            "use_count": uses.get(row["name"], 0),
            "selected_il_body_count_by_method_name": body_count,
            "evidence": {
                "api_binding": "reconstruction/logic/yarn_api_map.md",
                "body_listing": "reconstruction/logic/selected_method_bodies.il" if body_count else None,
            },
        })

    map_names = {(r["kind"], r["name"]) for r in rows}
    runtime_commands = {"wait"}
    runtime_functions = {"Bool.And", "Bool.Not", "Bool.Or", "Number.Add", "Number.EqualTo", "Number.GreaterThan", "Number.GreaterThanOrEqualTo", "Number.LessThan", "dice", "visited", "visited_count"}
    unmapped_commands = sorted(n for n, count in command_uses.items() if count and ("command", n) not in map_names and n not in runtime_commands)
    unmapped_functions = sorted(n for n, count in function_uses.items() if count and ("function", n) not in map_names and n not in runtime_functions)
    used = [b for b in bindings if b["use_count"]]
    unused = [b for b in bindings if not b["use_count"]]
    used_with_body = [b for b in used if b["selected_il_body_count_by_method_name"]]
    body_gaps = [b for b in used if not b["selected_il_body_count_by_method_name"]]

    report = {
        "scope": "static inventory from decoded Yarn program and recovered metadata-aware C# binding signatures; no executable inspection",
        "inputs": {
            "program": "reconstruction/narrative/program.json",
            "api_map": "reconstruction/logic/yarn_api_map.md",
            "selected_method_bodies": "reconstruction/logic/selected_method_bodies.il",
        },
        "counts": {
            "nodes": node_count,
            "instructions": sum(opcode_counts.values()),
            "run_command_instructions": opcode_counts["RunCommand"],
            "call_func_instructions": opcode_counts["CallFunc"],
            "add_option_instructions": choices,
            "unique_command_names_used": len(command_uses),
            "unique_function_names_used": len(function_uses),
            "registered_commands_in_api_map": sum(r["kind"] == "command" for r in rows),
            "registered_functions_in_api_map": sum(r["kind"] == "function" for r in rows),
            "registered_bindings_used": len(used),
            "registered_bindings_unused": len(unused),
            "used_bindings_with_selected_il_body_by_method_name": len(used_with_body),
            "used_bindings_without_selected_il_body_by_method_name": len(body_gaps),
        },
        "opcode_counts": dict(sorted(opcode_counts.items())),
        "commands_used": [{"name": n, "count": c, "mapped": ("command", n) in map_names} for n, c in sorted(command_uses.items())],
        "functions_used": [{"name": n, "count": c, "mapped": ("function", n) in map_names, "instruction_operand_count_histogram": dict(sorted(function_arity[n].items()))} for n, c in sorted(function_uses.items())],
        "bindings": bindings,
        "unmapped_commands": unmapped_commands,
        "unmapped_functions": unmapped_functions,
        "standard_runtime_commands_used": [{"name": n, "count": command_uses[n]} for n in sorted(runtime_commands) if command_uses[n]],
        "standard_runtime_functions_used": [{"name": n, "count": function_uses[n]} for n in sorted(runtime_functions) if function_uses[n]],
        "body_evidence_gaps_for_used_bindings": [{"kind": b["kind"], "name": b["name"], "game_method": b["game_method"], "use_count": b["use_count"]} for b in body_gaps],
        "choice_metadata_evidence": {
            "program_nodes_with_nonempty_tags": tags_present,
            "program_node_tag_entries": tags_total,
            "nodes_with_headers": nodes_with_headers,
            "node_header_entries": headers_total,
            "add_option_operand_shape": "[localized line ID, destination label, float, bool] (example: reconstruction/narrative/program.json, Firefighter_WannaCheck first AddOption)",
            "conclusion": "No choice-specific metadata tags are present in the retained decoded program: all node tag arrays are empty, and AddOption carries only the standard line/destination/float/bool operands. Node headers survive, but are node-level title/position data rather than per-choice tags. The raw retained MonoBehaviour bytes and string dump contain compiled identifiers and operands, not recoverable source Yarn metadata tags.",
            "evidence_paths": [
                "reconstruction/narrative/program.json",
                "reconstruction/assets/narrative/compiled_yarn_program.json",
                "reconstruction/assets/narrative/compiled_yarn_program.pb",
                "reconstruction/assets/narrative/monobehaviour_2735.bin",
                "reconstruction/assets/narrative/monobehaviour_2735_strings.json",
                "tools/assets/decode_yarn_program.py",
            ],
        },
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["counts"], indent=2))
    print(f"unmapped commands: {unmapped_commands}")
    print(f"unmapped functions: {unmapped_functions}")
    print(f"used binding body evidence gaps: {[b['name'] for b in body_gaps]}")


if __name__ == "__main__":
    main()
