#!/usr/bin/env python3
"""Verify every exported Vorbis OGG and, optionally, its staged Android copy."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

EXPECTED_KEYS = {
    "main_menu", "ambience_house", "day", "night1", "day_02", "night_02_01",
    "night_02_02", "night3", "burning_light", "noise_1_loop", "noise_2_loop",
    "noise_3_loop", "noise_4_loop", "gun_music",
}
EXPECTED_ARCHIVE_SHA256 = "f8e6a46efbd41452266790a1350bbec3cfd6027470282171b912df80b08489f1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def safe_asset(base: Path, relative: str) -> Path:
    candidate = (base / relative).resolve()
    candidate.relative_to(base.resolve())
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def probe_duration(path: Path) -> float:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path),
    ], check=True, capture_output=True, text=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?", default=Path("reconstruction/reverse-music/music_manifest.json"))
    parser.add_argument("--assets-root", type=Path, help="Also compare the staged Android assets and manifest")
    args = parser.parse_args()
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required")
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("source_archive", {}).get("sha256") != EXPECTED_ARCHIVE_SHA256:
        raise ValueError("Manifest source archive hash does not match the recovered original")
    rows = manifest.get("tracks")
    if not isinstance(rows, list):
        raise ValueError("Manifest tracks must be a list")
    keys = [row.get("key") for row in rows]
    if len(keys) != len(set(keys)) or set(keys) != EXPECTED_KEYS:
        raise ValueError(f"Manifest track keys do not match expected 14: {keys}")
    source_base = manifest_path.parent.resolve()
    if args.assets_root:
        assets_root = args.assets_root.resolve()
        staged = json.loads((assets_root / "music_manifest.json").read_text())
        staged_rows = {row["key"]: row for row in staged.get("tracks", [])}
        if set(staged_rows) != EXPECTED_KEYS:
            raise ValueError("Staged manifest track keys differ from expected source keys")
    else:
        assets_root = None
        staged_rows = {}

    total_bytes = 0
    for row in rows:
        key = row["key"]
        extracted = safe_asset(source_base, row["extracted_asset"])
        expected_hash = row["ogg"]["sha256"]
        actual_hash = sha256(extracted)
        if actual_hash != expected_hash:
            raise ValueError(f"{key}: source OGG SHA-256 mismatch: {actual_hash}")
        decoded = subprocess.run([
            "ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(extracted), "-f", "null", "-",
        ], check=True, capture_output=True, text=True)
        actual_duration = probe_duration(extracted)
        if abs(actual_duration - float(row["ogg"]["duration_seconds"])) > 0.05:
            raise ValueError(f"{key}: duration mismatch {actual_duration} vs {row['ogg']['duration_seconds']}")
        if assets_root:
            staged_row = staged_rows[key]
            if staged_row.get("asset") != row.get("asset") or staged_row.get("ogg", {}).get("sha256") != expected_hash:
                raise ValueError(f"{key}: staged manifest does not match source manifest")
            staged_asset = safe_asset(assets_root, staged_row["asset"])
            if sha256(staged_asset) != expected_hash:
                raise ValueError(f"{key}: staged Android asset SHA-256 mismatch")
            subprocess.run([
                "ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(staged_asset), "-f", "null", "-",
            ], check=True, capture_output=True, text=True)
        source = row.get("source", {})
        resource = source.get("resource") if isinstance(source, dict) else None
        if not resource or not resource.get("extracted_fsb"):
            raise ValueError(f"{key}: source FSB evidence is missing")
        fsb = safe_asset(source_base, resource["extracted_fsb"])
        fsb_hash = sha256(fsb)
        if fsb_hash != resource.get("sha256"):
            raise ValueError(f"{key}: extracted FSB SHA-256 mismatch: {fsb_hash}")
        with fsb.open("rb") as stream:
            if stream.read(4) != b"FSB5":
                raise ValueError(f"{key}: source payload is not FSB5")
        total_bytes += extracted.stat().st_size

    stage_temps = list(source_base.rglob("*.stage-tmp"))
    if stage_temps:
        raise ValueError(f"Stale staged files remain: {[str(path) for path in stage_temps]}")

    print(json.dumps({"validated_tracks": len(rows), "full_decode": True,
                      "staged_assets_checked": bool(assets_root), "ogg_bytes": total_bytes}, indent=2))


if __name__ == "__main__":
    main()
