#!/usr/bin/env python3
"""Stage exact vertex deduplication and fetch remapping for Android world meshes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSET_ROOT = ROOT / "reconstruction/android-current/app/src/main/assets"
DEFAULT_CANDIDATE = ROOT / "tools/mesh-opt/world_manifest.optimized.json"
DEFAULT_REPORT = ROOT / "tools/mesh-opt/optimization_report.json"
STRIDE = 32
UPSTREAM = {
    "project": "zeux/meshoptimizer",
    "tag": "v1.3",
    "commit": "9e1f07b159d3cb777f1c67ed31fc11fd117986f4",
    "source_archive_sha256": "ca4f47d451201593904b9e3067fa54b65db94bc34ab5173864950862b748a145",
    "vendored_file_sha256": {
        "LICENSE.md": "f03037ca7bad1e3eb7f4a63fa6084a8baabd5ba30d3c239a9a7f35705d873e26",
        "meshoptimizer.h": "e3688ef553f603391747895a5c221ef1528574cc7f8173782417a96cb531f61b",
        "indexgenerator.cpp": "f362cdcd8af10016333bf699347a9364335987f413f061e5b7e8cafe3b498948",
        "vfetchoptimizer.cpp": "aa534bb8150ca27ae229c58a0dc51f85f9acccbc5d4214f4c82edd91fc08e478",
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_asset_path(value: str, assets_root: Path) -> Path:
    path = (assets_root / value).resolve()
    try:
        path.relative_to(assets_root.resolve())
    except ValueError as error:
        raise RuntimeError(f"asset path escapes Android asset root: {value}") from error
    return path


def source_path(row: dict, assets_root: Path) -> Path:
    for key in ("source_android_asset", "mesh_asset", "asset", "path", "android_asset"):
        value = row.get(key)
        if not isinstance(value, str) or not value:
            continue
        candidates = [checked_asset_path(value, assets_root)]
        if key == "mesh_asset" and not value.startswith("world/"):
            candidates.insert(0, checked_asset_path("world/" + value, assets_root))
        for path in candidates:
            if path.is_file():
                return path
    raise FileNotFoundError(f"no source mesh blob found for {row.get('name', '<unnamed>')}")


def compile_optimizer() -> Path:
    build_dir = Path(__file__).resolve().parent / "build"
    vendor_dir = Path(__file__).parent / "third_party/meshoptimizer-v1.3"
    executable = build_dir / "meshopt_reindex"
    for name, expected in UPSTREAM["vendored_file_sha256"].items():
        actual = sha256((vendor_dir / name).read_bytes())
        if actual != expected:
            raise RuntimeError(f"vendored meshoptimizer file hash mismatch for {name}: {actual}")
    source_files = [
        Path(__file__).with_name("meshopt_reindex.cpp"),
        vendor_dir / "indexgenerator.cpp",
        vendor_dir / "vfetchoptimizer.cpp",
    ]
    if executable.is_file() and executable.stat().st_mtime >= max(path.stat().st_mtime for path in source_files):
        return executable
    build_dir.mkdir(parents=True, exist_ok=True)
    temporary = build_dir / "meshopt_reindex.tmp"
    command = ["g++", "-std=c++17", "-O3", "-DNDEBUG", "-Wall", "-Wextra", "-Wpedantic",
               *(str(path) for path in source_files), "-o", str(temporary)]
    subprocess.run(command, cwd=ROOT, check=True)
    temporary.replace(executable)
    return executable


def optimize_one(executable: Path, row: dict, output_dir: Path, assets_root: Path) -> tuple[dict, dict]:
    source = source_path(row, assets_root)
    vertex_count = row.get("vertex_count")
    index_count = row.get("index_count")
    if not isinstance(vertex_count, int) or vertex_count < 0 or not isinstance(index_count, int) or index_count < 0:
        raise RuntimeError(f"missing or invalid source counts for {source}")
    if row.get("vertex_stride_bytes") != STRIDE or row.get("index_type") != "uint32_le":
        raise RuntimeError(f"unsupported source layout for {source}: expected stride=32 and uint32_le indices")

    # Read and hash the original before passing it to the optimizer.
    original = source.read_bytes()
    actual_source_hash = sha256(original)
    expected_hashes = [row.get(key) for key in ("source_sha256", "sha256") if row.get(key)]
    if not expected_hashes or any(value != actual_source_hash for value in expected_hashes):
        raise RuntimeError(f"source SHA-256 mismatch for {source}: got {actual_source_hash}, expected {expected_hashes}")
    expected_size = vertex_count * STRIDE + index_count * 4
    if len(original) != expected_size:
        raise RuntimeError(f"source size/count mismatch for {source}: {len(original)} bytes, expected {expected_size}")

    output = output_dir / source.name
    relative_name = output.relative_to(assets_root).as_posix()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=source.stem + ".", suffix=".tmp", dir=output.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        subprocess.run([str(executable), str(source), str(temporary), str(vertex_count), str(index_count)],
                       cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        optimized = temporary.read_bytes()
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"meshoptimizer failed for {source}: {error.stderr}") from error
    finally:
        temporary.unlink(missing_ok=True)

    if len(optimized) < index_count * 4 or (len(optimized) - index_count * 4) % STRIDE:
        raise RuntimeError(f"optimized mesh byte length is invalid for {source}")
    android_vertex_count = (len(optimized) - index_count * 4) // STRIDE
    if android_vertex_count > vertex_count:
        raise RuntimeError(f"vertex remapping unexpectedly increased vertex count for {source}")

    source_indices = original[vertex_count * STRIDE:]
    output_indices = optimized[android_vertex_count * STRIDE:]
    if len(source_indices) != len(output_indices):
        raise RuntimeError(f"index count changed for {source}; refusing staged output")

    # Reconstruct all indexed corners and require exact source bytes in order.
    optimized_vertices = optimized[:android_vertex_count * STRIDE]
    for corner, (source_index,) in enumerate(struct.iter_unpack("<I", source_indices)):
        if source_index >= vertex_count:
            raise RuntimeError(f"source index {source_index} is out of range in {source}")
        expected = original[source_index * STRIDE:(source_index + 1) * STRIDE]
        optimized_index = int.from_bytes(output_indices[corner * 4:corner * 4 + 4], "little")
        if optimized_index >= android_vertex_count:
            raise RuntimeError(f"optimized index {optimized_index} is out of range in {source}")
        actual = optimized_vertices[optimized_index * STRIDE:(optimized_index + 1) * STRIDE]
        if actual != expected:
            raise RuntimeError(f"indexed vertex corner {corner} changed in {source}")

    output_hash = sha256(optimized)
    temporary_output = output.with_name(output.name + ".tmp")
    temporary_output.write_bytes(optimized)
    temporary_output.replace(output)
    new_row = dict(row)
    new_row["android_asset"] = relative_name
    new_row["android_vertex_count"] = android_vertex_count
    new_row["android_index_count"] = index_count
    new_row["android_sha256"] = output_hash
    return {
        "name": row.get("name", source.name),
        "source_asset": source.relative_to(assets_root).as_posix(),
        "android_asset": relative_name,
        "source_sha256": actual_source_hash,
        "android_sha256": output_hash,
        "source_vertex_count": vertex_count,
        "android_vertex_count": android_vertex_count,
        "index_count_preserved": index_count,
        "source_bytes": len(original),
        "android_bytes": len(optimized),
        "vertex_reduction": vertex_count - android_vertex_count,
        "byte_reduction": len(original) - len(optimized),
        "corner_bytes_verified": index_count,
        "index_order_preserved": True,
        "staged": True,
    }, new_row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-root", type=Path, default=DEFAULT_ASSET_ROOT,
                        help="Android assets root containing world/world_manifest.json")
    parser.add_argument("--output-dir", type=Path,
                        help="optimized mesh output directory (default: ASSETS_ROOT/world/models_android)")
    parser.add_argument("--candidate-manifest", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--apply", action="store_true",
                        help="atomically replace the active world/world_manifest.json after all mesh checks pass")
    args = parser.parse_args()

    assets_root = args.assets_root.resolve()
    source_manifest_path = assets_root / "world/world_manifest.json"
    source_manifest_bytes = source_manifest_path.read_bytes()
    source_manifest = json.loads(source_manifest_bytes)
    output_root = (args.output_dir or assets_root / "world/models_android").resolve()
    meshes = source_manifest.get("meshes")
    if not isinstance(meshes, list) or not meshes:
        raise RuntimeError("source world manifest has no meshes array")
    try:
        output_root.relative_to(assets_root)
    except ValueError as error:
        raise RuntimeError("optimized output directory must remain under the Android asset root") from error
    candidate_path = args.candidate_manifest.resolve()
    report_path = args.report.resolve()
    for path, label in ((candidate_path, "candidate manifest"), (report_path, "optimization report")):
        try:
            path.relative_to(ROOT.resolve())
        except ValueError as error:
            raise RuntimeError(f"{label} must remain inside the repository") from error
    if source_manifest_path.resolve() in (candidate_path, report_path):
        raise RuntimeError("refusing to overwrite the active source world_manifest.json")
    if candidate_path == report_path:
        raise RuntimeError("candidate manifest and report must be separate files")

    executable = compile_optimizer()
    report_meshes = []
    candidate_meshes = []
    names = set()
    for row in meshes:
        if not isinstance(row, dict):
            raise RuntimeError("invalid mesh row in source manifest")
        result, updated = optimize_one(executable, row, output_root, assets_root)
        if result["android_asset"] in names:
            raise RuntimeError(f"duplicate optimized asset path: {result['android_asset']}")
        names.add(result["android_asset"])
        report_meshes.append(result)
        candidate_meshes.append(updated)
        print(f"{result['source_asset']}: {result['source_vertex_count']} -> {result['android_vertex_count']} vertices, "
              f"{result['source_bytes']} -> {result['android_bytes']} bytes")

    candidate = dict(source_manifest)
    candidate["meshes"] = candidate_meshes
    for original, updated in zip(meshes, candidate_meshes):
        if "source_android_asset" not in updated:
            updated["source_android_asset"] = original.get("source_android_asset") or source_path(original, assets_root).relative_to(assets_root).as_posix()
    candidate["android_mesh_optimization"] = {
        "optimizer": "meshoptimizer",
        "version": UPSTREAM["tag"],
        "commit": UPSTREAM["commit"],
        "source_archive_sha256": UPSTREAM["source_archive_sha256"],
        "vertex_stride_bytes": STRIDE,
        "index_type": "uint32_le",
        "operations": ["exact_32_byte_vertex_deduplication", "vertex_fetch_remap"],
        "preserves_triangle_and_submesh_order": True,
        "source_mesh_blobs_preserved": True,
        "lossy_operations": [],
    }
    total_source_bytes = sum(item["source_bytes"] for item in report_meshes)
    total_android_bytes = sum(item["android_bytes"] for item in report_meshes)
    report = {
        "schema_version": 1,
        "source_manifest": source_manifest_path.relative_to(ROOT.resolve()).as_posix()
        if source_manifest_path.is_relative_to(ROOT.resolve()) else str(source_manifest_path),
        "source_manifest_sha256": sha256(source_manifest_bytes),
        "candidate_manifest": candidate_path.relative_to(ROOT.resolve()).as_posix(),
        "optimizer": UPSTREAM,
        "mesh_count": len(report_meshes),
        "source_bytes_total": total_source_bytes,
        "android_bytes_total": total_android_bytes,
        "bytes_saved_total": total_source_bytes - total_android_bytes,
        "source_vertices_total": sum(row["source_vertex_count"] for row in report_meshes),
        "android_vertices_total": sum(row["android_vertex_count"] for row in report_meshes),
        "indices_preserved_total": sum(row["index_count_preserved"] for row in report_meshes),
        "all_indexed_corner_bytes_verified": all(row["corner_bytes_verified"] == row["index_count_preserved"] for row in report_meshes),
        "all_index_orders_preserved": all(row["index_order_preserved"] for row in report_meshes),
        "meshes": report_meshes,
    }
    args.candidate_manifest.parent.mkdir(parents=True, exist_ok=True)
    candidate_temp = args.candidate_manifest.with_name(args.candidate_manifest.name + ".tmp")
    candidate_temp.write_text(json.dumps(candidate, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    candidate_temp.replace(args.candidate_manifest)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report_temp = args.report.with_name(args.report.name + ".tmp")
    report_temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_temp.replace(args.report)
    if args.apply:
        active_temp = source_manifest_path.with_name(source_manifest_path.name + ".tmp")
        active_temp.write_text(json.dumps(candidate, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        active_temp.replace(source_manifest_path)
    print(json.dumps({key: report[key] for key in (
        "mesh_count", "source_bytes_total", "android_bytes_total", "bytes_saved_total",
        "source_vertices_total", "android_vertices_total", "indices_preserved_total",
        "all_indexed_corner_bytes_verified", "all_index_orders_preserved")}, indent=2))


if __name__ == "__main__":
    main()
