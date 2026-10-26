#!/usr/bin/env python3
"""Validate the source-link structure of the retained animation manifest."""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=ROOT / "reconstruction/reverse-animations/animation_manifest.json")
    ap.add_argument("--assets", type=Path, default=ROOT / "reconstruction/android-current/app/src/main/assets")
    args = ap.parse_args()
    data = json.loads(args.manifest.read_text())
    errors = []
    doors = data["door_triggers"]
    if len(doors) != 6:
        errors.append(f"expected 6 main-house DoorTriggers; got {len(doors)}")
    for door in doors:
        name = door["game_object_name"]
        pivot = door["door_pivot"]
        fields = door["serialized_fields"]
        if pivot["parent_transform_path_id"] != 1602:
            errors.append(f"{name}: unexpected pivot parent {pivot['parent_transform_path_id']}")
        if not pivot.get("world_renderer_path_id"):
            errors.append(f"{name}: missing world renderer path ID")
        if not fields.get("source_collider", {}).get("resolved"):
            errors.append(f"{name}: source collider PPtr unresolved")
        if fields.get("duration_seconds") != 1.0 or fields.get("close_speed_modifier") != 2.0:
            errors.append(f"{name}: serialized timing no longer matches expected source values")
        action = door["runtime_actions"]
        if not math.isclose(action["close"]["duration_seconds"], 0.5, abs_tol=1e-7):
            errors.append(f"{name}: close duration does not reflect duration / close-speed modifier")
        if action["open"]["set_ease_numeric"] != 9 or action["close"]["set_ease_numeric"] != 2:
            errors.append(f"{name}: recovered numeric SetEase values differ")

    dream_actions = data["open_door_scene_actions"]
    if len(dream_actions) != 6 or any(x["scene_asset_path"] != "Assets/_Scenes/Dreams/StrangeMorning/s4_StrangeMorning.unity" for x in dream_actions):
        errors.append("expected six generic TriggerObjectOpenDoor actions in StrangeMorning")
    if any(x["serialized_fields"]["duration_seconds"] != 1.0 for x in dream_actions):
        errors.append("generic open-door action duration differs from serialized 1-second source")
    if any(len(x["serialized_fields"]["sound_enum_values"]) != 4 for x in dream_actions):
        errors.append("expected four serialized ESound values per StrangeMorning open-door trigger")

    animated = data["animated_image_components"]
    if len(animated) != 39:
        errors.append(f"expected 39 scene AnimatedImage components; got {len(animated)}")
    for component in animated:
        if component["frame_count"] != len(component["frames"]):
            errors.append(f"{component['game_object_name']}: frame count/list mismatch")
        if component["frame_count"] and component["frames_per_second"] <= 0:
            errors.append(f"{component['game_object_name']}: invalid FPS")
        for frame in component["frames"]:
            path = frame["sprite"].get("android_asset")
            if path and not (args.assets / path).is_file():
                errors.append(f"{component['game_object_name']}: staged frame is missing: {path}")

    char_clips = data["character_emotion_animations"]
    if len(char_clips) != 27:
        errors.append(f"expected 27 recovered character emotion sequences; got {len(char_clips)}")
    for clip in char_clips:
        if clip["frame_count"] != len(clip["frames"]) or clip["frames_per_second"] <= 0:
            errors.append(f"{clip['character']}/{clip['emotion']}: invalid frame timing data")
        for frame in clip["frames"]:
            path = frame.get("android_asset")
            if path and not (args.assets / path).is_file():
                errors.append(f"{clip['character']}/{clip['emotion']}: staged frame is missing: {path}")

    if errors:
        raise SystemExit("\n".join(errors))
    print(json.dumps({"door_triggers": len(doors), "dream_open_door_actions": len(dream_actions),
                      "animated_image_components": len(animated), "character_emotion_animations": len(char_clips),
                      "all_staged_frame_paths_exist": True}, indent=2))


if __name__ == "__main__":
    main()
