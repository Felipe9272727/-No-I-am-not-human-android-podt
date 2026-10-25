#!/usr/bin/env python3
"""Export Yarn LineMetadata from one Unity Localization shared-data bundle.

Only the specified asset bundle is parsed. No game executable or native library
is loaded or executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import UnityPy

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "malware-review/No.Im.not.a.Human.v1.3.18/No.Im.not.a.Human.v1.3.18/NoImNotAHuman_Data/StreamingAssets/aa/StandaloneWindows64/localization-assets-shared_assets_all.bundle"
DEFAULT_PROGRAM = ROOT / "reconstruction/narrative/program.json"
DEFAULT_OUTPUT = ROOT / "reconstruction/reverse-localization/line_metadata.json"
LINE_ID = re.compile(r"^line:(.+)$")


def graph_line_ids(program_path: Path) -> dict[str, dict[str, set[str]]]:
    """Map compiled localized line keys to node names and instruction kinds."""
    program = json.loads(program_path.read_text(encoding="utf-8"))
    result: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"nodes": set(), "instruction_kinds": set()})
    for node_name, node in program.get("nodes", {}).items():
        for ins in node.get("instructions", []):
            op = ins.get("opcode_name")
            args = ins.get("operands", [])
            if op == "RunLine" and args and isinstance(args[0], str):
                result[args[0]]["nodes"].add(node_name)
                result[args[0]]["instruction_kinds"].add("RunLine")
            elif op == "AddOption" and args and isinstance(args[0], str):
                result[args[0]]["nodes"].add(node_name)
                result[args[0]]["instruction_kinds"].add("AddOption")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--program", type=Path, default=DEFAULT_PROGRAM)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    # UnityPy is pointed at exactly one small Addressables bundle, not the game
    # directory, sharedassets collections, executable, or DLL.
    env = UnityPy.load(str(args.source))
    candidates = []
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        table = obj.read()
        name = getattr(table, "m_Name", "")
        if name == "Dialogs Shared Data":
            candidates.append((obj, table))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one Dialogs Shared Data MonoBehaviour; found {len(candidates)}")
    obj, table = candidates[0]

    managed_refs = {}
    for ref in getattr(table.references, "RefIds", []):
        type_info = getattr(ref, "type", None)
        if getattr(type_info, "class", None) == "LineMetadata":
            managed_refs[ref.rid] = ref

    graph_nodes = graph_line_ids(args.program)
    entries_by_key = {}
    for entry in table.m_Entries:
        key = getattr(entry, "m_Key", "")
        if not key.startswith("line:"):
            continue
        entries_by_key[key] = entry

    records = {}
    metadata_without_ref = []
    for key, entry in entries_by_key.items():
        metadata = []
        for item in entry.m_Metadata.m_Items:
            ref = managed_refs.get(item.rid)
            if ref is None:
                continue
            data = ref.data
            metadata.append({
                "node_name": getattr(data, "nodeName", ""),
                "tags": list(getattr(data, "tags", [])),
                "managed_reference_id": int(ref.rid),
                "managed_type": "Yarn.Unity.UnityLocalization.LineMetadata",
                "assembly": "YarnSpinner.Unity",
            })
        if not metadata:
            metadata_without_ref.append(key)
        records[key] = metadata

    graph_ids = set(graph_nodes)
    asset_ids = set(records)
    missing_asset_keys = sorted(graph_ids - asset_ids)
    extra_asset_keys = sorted(asset_ids - graph_ids)
    node_name_mismatches = []
    for key in sorted(graph_ids & asset_ids):
        expected_nodes = graph_nodes[key]["nodes"]
        for metadata in records[key]:
            if metadata["node_name"] not in expected_nodes:
                node_name_mismatches.append({
                    "line_id": key,
                    "graph_nodes": sorted(expected_nodes),
                    "metadata_node_name": metadata["node_name"],
                    "managed_reference_id": metadata["managed_reference_id"],
                })

    relevant_records = {key: records[key] for key in graph_ids & asset_ids}
    tag_counts = Counter(tag for value in relevant_records.values() for meta in value for tag in meta["tags"])
    tagged_entry_counts = Counter(tag for value in relevant_records.values() for meta in value for tag in set(meta["tags"]))
    tag_counts_by_instruction = {kind: Counter() for kind in ("RunLine", "AddOption")}
    tagged_entries_by_instruction = {kind: Counter() for kind in ("RunLine", "AddOption")}
    for key, value in relevant_records.items():
        for kind in graph_nodes[key]["instruction_kinds"]:
            for meta in value:
                tag_counts_by_instruction[kind].update(meta["tags"])
                tagged_entries_by_instruction[kind].update(set(meta["tags"]))
    graph_coverage = len(graph_ids & asset_ids)
    source_bytes = args.source.read_bytes()
    report = {
        "source": {
            "path": str(args.source.relative_to(ROOT)) if args.source.is_relative_to(ROOT) else str(args.source),
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
            "unity_object_name": "Dialogs Shared Data",
            "unity_object_path_id": int(obj.path_id),
            "unity_object_type": "MonoBehaviour / SharedTableData",
            "metadata_storage": "SharedTableEntry.m_Metadata -> MetadataCollection.m_Items -> ManagedReferencesRegistry.RefIds -> LineMetadata",
            "line_metadata_type": "Yarn.Unity.UnityLocalization.LineMetadata",
            "line_metadata_assembly": "YarnSpinner.Unity",
        },
        "validation": {
            "graph_line_id_count": len(graph_ids),
            "shared_table_line_key_count": len(asset_ids),
            "graph_ids_found_in_shared_table": graph_coverage,
            "graph_ids_missing_from_shared_table": missing_asset_keys,
            "shared_table_keys_not_used_by_graph_count": len(extra_asset_keys),
            "shared_table_keys_not_used_by_graph": extra_asset_keys,
            "line_metadata_managed_reference_count": len(managed_refs),
            "graph_ids_without_line_metadata_reference": [key for key in sorted(graph_ids & asset_ids) if not records[key]],
            "graph_ids_with_node_name_mismatch": node_name_mismatches,
            "graph_nodes_per_line_id_ambiguous": {key: sorted(details["nodes"]) for key, details in graph_nodes.items() if len(details["nodes"]) != 1},
        },
        "summary": {
            "shared_table_line_entries_scanned": len(records),
            "graph_entries_exported": len(relevant_records),
            "graph_entries_with_any_tags": sum(any(m["tags"] for m in value) for value in relevant_records.values()),
            "graph_entries_with_any_metadata": sum(bool(value) for value in relevant_records.values()),
            "graph_metadata_records": sum(len(value) for value in relevant_records.values()),
            "tag_occurrences": dict(sorted(tag_counts.items())),
            "entries_per_tag": dict(sorted(tagged_entry_counts.items())),
            "tag_occurrences_by_instruction_kind": {kind: dict(sorted(counter.items())) for kind, counter in tag_counts_by_instruction.items()},
            "entries_per_tag_by_instruction_kind": {kind: dict(sorted(counter.items())) for kind, counter in tagged_entries_by_instruction.items()},
            "unique_tag_sets": sorted({tuple(m["tags"]) for value in records.values() for m in value if m["tags"]}),
        },
        "line_metadata": {key: {"graph_nodes": sorted(graph_nodes[key]["nodes"]), "instruction_kinds": sorted(graph_nodes[key]["instruction_kinds"]), "metadata": records[key]} for key in sorted(graph_ids & asset_ids)},
        "evidence": {
            "compiled_graph": str(args.program.relative_to(ROOT)) if args.program.is_relative_to(ROOT) else str(args.program),
            "UnityPy_version": getattr(UnityPy, "__version__", "unknown"),
            "graph_line_id_sources": ["RunLine first operand", "AddOption first operand"],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation_summary = {key: value for key, value in report["validation"].items() if not isinstance(value, list) or not value}
    validation_summary["shared_table_keys_not_used_by_graph_sample"] = extra_asset_keys[:8]
    print(json.dumps({"source_sha256": report["source"]["sha256"], **validation_summary, **report["summary"]}, ensure_ascii=False, indent=2))
    if missing_asset_keys or node_name_mismatches or report["validation"]["graph_ids_without_line_metadata_reference"]:
        raise SystemExit("structural validation found differences; see output report")


if __name__ == "__main__":
    main()
