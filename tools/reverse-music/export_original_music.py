#!/usr/bin/env python3
"""Statically extract selected Unity AudioClips and transcode to Vorbis OGG."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import UnityPy

EXPECTED_ARCHIVE_SHA256 = "f8e6a46efbd41452266790a1350bbec3cfd6027470282171b912df80b08489f1"
GAME_DATA_SUFFIX = "NoImNotAHuman_Data/"
TRACK_NAMES = (
    "main_menu", "ambience_house", "day", "night1", "day_02", "night_02_01",
    "night_02_02", "night3", "burning_light", "noise_1_loop", "noise_2_loop",
    "noise_3_loop", "noise_4_loop", "gun_music",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_entry(archive: zipfile.ZipFile, basename: str) -> zipfile.ZipInfo:
    matches = [item for item in archive.infolist() if item.filename.endswith(GAME_DATA_SUFFIX + basename)]
    if len(matches) != 1:
        raise ValueError(f"Expected one {basename} in original archive, found {len(matches)}")
    return matches[0]


def unpack_static_inputs(archive_path: Path, work: Path) -> dict[str, Path]:
    names = ("sharedassets0.assets", "sharedassets0.resource", "level0", "level1")
    outputs = {}
    with zipfile.ZipFile(archive_path) as archive:
        for name in names:
            info = find_entry(archive, name)
            target = work / name
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
            outputs[name] = target
    return outputs


def audio_source_evidence(level_path: Path, wanted: set[str]) -> dict[str, dict]:
    env = UnityPy.load(str(level_path))
    found = {}
    for obj in env.objects:
        if obj.type.name != "AudioSource":
            continue
        source = obj.read()
        pointer = source.m_Resource
        clip = None
        try:
            clip = pointer.read()
        except Exception:
            pass
        clip_name = getattr(clip, "m_Name", "") if clip is not None else ""
        if clip_name not in wanted:
            continue
        game_object = source.m_GameObject.read()
        found[clip_name] = {
            "unity_file": level_path.name,
            "audio_source_path_id": obj.path_id,
            "game_object": game_object.m_Name,
            "clip_pointer": {"file_id": pointer.m_FileID, "path_id": pointer.m_PathID},
            "loop": bool(source.Loop),
            "play_on_awake": bool(source.m_PlayOnAwake),
            "volume": float(source.m_Volume),
        }
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="SHA-verified reassembled original ZIP")
    parser.add_argument("--output", type=Path, default=Path("reconstruction/reverse-music/exported_music"))
    parser.add_argument("--manifest", type=Path, default=Path("reconstruction/reverse-music/music_manifest.json"))
    args = parser.parse_args()

    archive_path = args.archive.resolve()
    actual_archive_hash = sha256_file(archive_path)
    if actual_archive_hash != EXPECTED_ARCHIVE_SHA256:
        raise ValueError(f"Unexpected original archive SHA-256: {actual_archive_hash}")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required")

    source_root = Path("reconstruction/reverse-music").resolve()
    output_root = args.output.resolve()
    output_root.relative_to(source_root)
    args.output.mkdir(parents=True, exist_ok=True)
    raw_dir = args.output / "original_fsb"
    raw_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ninah-music-static-") as temporary:
        work = Path(temporary)
        inputs = unpack_static_inputs(archive_path, work)
        shared = UnityPy.load(str(inputs["sharedassets0.assets"]))
        clips = {}
        for obj in shared.objects:
            if obj.type.name != "AudioClip":
                continue
            clip = obj.read()
            if clip.m_Name in TRACK_NAMES:
                if clip.m_Name in clips:
                    raise ValueError(f"Duplicate AudioClip named {clip.m_Name}")
                clips[clip.m_Name] = (obj, clip)
        missing = sorted(set(TRACK_NAMES) - clips.keys())
        if missing:
            raise ValueError(f"Missing expected source AudioClips: {missing}")

        sources = {}
        for level in (inputs["level0"], inputs["level1"]):
            sources.update(audio_source_evidence(level, {"main_menu", "ambience_house", "night1"}))

        rows = []
        for key in TRACK_NAMES:
            obj, clip = clips[key]
            wav_name, wav_data = next(iter(clip.samples.items()))
            wav_path = raw_dir / wav_name
            wav_path.write_bytes(wav_data)
            output_asset = args.output / f"{key}.ogg"
            staged_asset = output_asset.with_suffix(output_asset.suffix + ".stage-tmp")
            staged_asset.unlink(missing_ok=True)
            subprocess.run([
                "ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
                "-xerror", "-i", str(wav_path), "-c:a", "libvorbis", "-q:a", "4", "-f", "ogg", str(staged_asset),
            ], check=True)
            wav_path.unlink()
            subprocess.run([
                "ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(staged_asset), "-f", "null", "-",
            ], check=True)
            probe = subprocess.run([
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "json", str(staged_asset),
            ], check=True, capture_output=True, text=True)
            duration = float(json.loads(probe.stdout)["format"]["duration"])
            resource = clip.m_Resource
            resource_hash = None
            resource_bytes = None
            if resource and resource.m_Source == "sharedassets0.resource":
                with inputs["sharedassets0.resource"].open("rb") as stream:
                    stream.seek(resource.m_Offset)
                    resource_bytes = stream.read(resource.m_Size)
                if len(resource_bytes) != resource.m_Size:
                    raise ValueError(f"Short resource read for {key}")
                resource_hash = sha256_bytes(resource_bytes)
                (raw_dir / f"{key}.fsb").write_bytes(resource_bytes)

            staged_asset.replace(output_asset)

            audio_source = sources.get(key)
            row = {
                "key": key,
                "asset": f"music/{key}.ogg",
                "extracted_asset": output_asset.resolve().relative_to(source_root).as_posix(),
                "source": {
                    "unity_file": "sharedassets0.assets",
                    "unity_type": "AudioClip",
                    "path_id": obj.path_id,
                    "name": clip.m_Name,
                    "compression_format": int(clip.m_CompressionFormat),
                    "channels": int(clip.m_Channels),
                    "sample_rate": int(clip.m_Frequency),
                    "unity_length_seconds": float(clip.m_Length),
                    "resource": {
                        "file": resource.m_Source,
                        "offset": int(resource.m_Offset),
                        "size": int(resource.m_Size),
                        "sha256": resource_hash,
                        "extracted_fsb": f"exported_music/original_fsb/{key}.fsb",
                    } if resource else None,
                    "audio_source": audio_source,
                },
                "ogg": {
                    "sha256": sha256_file(output_asset),
                    "duration_seconds": duration,
                    "size_bytes": output_asset.stat().st_size,
                    "codec": "vorbis",
                    "quality": 4,
                },
            }
            if audio_source:
                row["loop"] = bool(audio_source["loop"])
                row["source_volume"] = float(audio_source["volume"])
            rows.append(row)

    manifest = {
        "schema_version": 1,
        "source_archive": {"sha256": actual_archive_hash, "size_bytes": archive_path.stat().st_size},
        "extraction": {"tool": "UnityPy", "version": UnityPy.__version__, "audio_payload": "FSB5"},
        "transcode": {"tool": "ffmpeg", "codec": "libvorbis", "quality": 4},
        "tracks": rows,
        "routing_evidence": {
            "scriptable_objects": [
                {"unity_file": "sharedassets0.assets", "unity_type": "MonoBehaviour", "path_id": 2718, "name": "SoundData", "source_script_path_id": 261, "rows": 19, "day_indices": list(range(19))},
                {"unity_file": "sharedassets0.assets", "unity_type": "MonoBehaviour", "path_id": 2719, "name": "SoundList", "source_script_path_id": 2812},
            ],
            "known_scene_routes": {
                "menu": {"clip": "main_menu", "source": "level0:MusicSource", "loop": True, "volume": 1.0},
                "day_0_night": {"clips": ["night1", "ambience_house"], "sources": ["level1:2DMusicSourceNight", "level1:2DMusicSourceAmbient"]},
            },
            "days": [
                {"day": 0, "classification": "NIGHT", "tracks": ["night1", "ambience_house"], "status": "verified"}
                if day == 0 else {"day": day, "classification": None, "tracks": [], "status": "unresolved_stripped_typetree"}
                for day in range(19)
            ],
            "note": "The MonoBehaviour script type trees are stripped from these Unity assets; source PPtrs and scene AudioSources are recorded directly. Day-index routing beyond the known day-0 NIGHT route remains unexpanded here.",
        },
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"tracks": len(rows), "manifest": str(args.manifest), "source_sha256": actual_archive_hash,
                      "ogg_bytes": sum(row["ogg"]["size_bytes"] for row in rows)}, indent=2))


if __name__ == "__main__":
    main()
