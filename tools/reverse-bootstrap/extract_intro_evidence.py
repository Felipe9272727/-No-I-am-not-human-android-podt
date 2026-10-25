#!/usr/bin/env python3
"""Recover the original Intro EndingView asset metadata and VideoClip bytes.

UnityPy parses serialized Unity objects only; this script does not execute the
original executable or native library. MonoBehaviour fields are read from the
retained serialized payload using the recovered EndingViewSOData layout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import UnityPy


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def aligned_string(data: bytes, offset: int) -> tuple[str, int]:
    (length,) = struct.unpack_from("<I", data, offset)
    offset += 4
    value = data[offset : offset + length].decode("utf-8")
    offset = (offset + length + 3) & ~3
    return value, offset


def read_intro_payload(raw: bytes) -> tuple[int, int, list[dict]]:
    # MonoBehaviour base fields: GameObject ptr, enabled, MonoScript ptr, name.
    name, offset = aligned_string(raw, 28)
    if name != "Intro":
        raise ValueError(f"expected MonoBehaviour name Intro, got {name!r}")
    (ending_type,) = struct.unpack_from("<i", raw, offset)
    offset += 4
    video_file_id, video_path_id = struct.unpack_from("<iq", raw, offset)
    offset += 12
    (count,) = struct.unpack_from("<i", raw, offset)
    offset += 4
    subtitles = []
    for index in range(count):
        node, offset = aligned_string(raw, offset)
        duration, before_delay = struct.unpack_from("<ff", raw, offset)
        offset += 8
        subtitles.append({
            "order": index,
            "node": node,
            "before_node_delay_seconds": before_delay,
            "duration_seconds": duration,
            "timeline_start_seconds": round(sum(s["before_node_delay_seconds"] + s["duration_seconds"] for s in subtitles) + before_delay, 6),
            "timeline_end_seconds": round(sum(s["before_node_delay_seconds"] + s["duration_seconds"] for s in subtitles) + before_delay + duration, 6),
        })
    return ending_type, video_path_id, subtitles


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("game_data", type=Path, help="Path to NoImNotAHuman_Data")
    ap.add_argument("output", type=Path, help="Evidence JSON output path")
    ap.add_argument("--export-video", type=Path, help="Optional destination for extracted video payload")
    args = ap.parse_args()
    data = args.game_data.resolve()
    assets = data / "sharedassets0.assets"
    resource = data / "sharedassets0.resource"
    if not assets.is_file() or not resource.is_file():
        raise SystemExit(f"expected {assets} and {resource}")

    env = UnityPy.load(str(assets))
    objects = {int(o.path_id): o for o in env.objects}
    intro_obj = objects[2707]
    intro_raw = intro_obj.get_raw_data()
    ending_type, video_path_id, subtitles = read_intro_payload(intro_raw)
    clip_obj = objects[video_path_id]
    clip = clip_obj.read(check_read=False)
    if clip.m_Name != "Intro_Final_2_NO_SUBTITLES":
        raise ValueError(f"unexpected Intro VideoClip: {clip.m_Name}")
    ext = clip.m_ExternalResources
    if ext.m_Source != resource.name:
        raise ValueError(f"unexpected stream source {ext.m_Source!r}")
    offset, size = int(ext.m_Offset), int(ext.m_Size)
    with resource.open("rb") as f:
        f.seek(offset)
        payload = f.read(size)
    if len(payload) != size:
        raise ValueError(f"truncated VideoClip payload: expected {size}, got {len(payload)}")
    payload_sha = hashlib.sha256(payload).hexdigest()
    exported = None
    if args.export_video:
        args.export_video.parent.mkdir(parents=True, exist_ok=True)
        args.export_video.write_bytes(payload)
        exported = str(args.export_video)

    evidence = {
        "method": "UnityPy serialized-file parsing plus bounded extraction of the referenced VideoClip resource bytes; no original executable or native library executed",
        "source": {
            "assets_file": assets.name,
            "assets_sha256": sha256_file(assets),
            "resource_file": resource.name,
            "resource_sha256": sha256_file(resource),
            "ending_view_so_path_id": int(intro_obj.path_id),
            "ending_view_so_name": "Intro",
        },
        "ending": {
            "enum_value": ending_type,
            "video_clip_path_id": video_path_id,
            "video": {
                "name": clip.m_Name,
                "original_path": clip.m_OriginalPath,
                "width": int(clip.Width),
                "height": int(clip.Height),
                "frame_rate": float(clip.m_FrameRate),
                "frame_count": int(clip.m_FrameCount),
                "audio_channels": [int(x) for x in clip.m_AudioChannelCount],
                "audio_sample_rates": [int(x) for x in clip.m_AudioSampleRate],
                "stream_source": ext.m_Source,
                "stream_offset": offset,
                "stream_size": size,
                "payload_sha256": payload_sha,
                "exported_path": exported,
            },
            "subtitles": subtitles,
            "total_timeline_seconds": round(subtitles[-1]["timeline_end_seconds"], 6) if subtitles else 0.0,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
