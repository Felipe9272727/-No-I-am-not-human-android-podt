# Door and character animation evidence

`animation_evidence.json` records source behavior. `animation_manifest.json` contains fields extracted from the original Unity scene and sprite assets. The exporter uses UnityPy static parsing and retained C# declarations/recovered ISIL; no original executable or DLL is run.

## Main-house doors

The six `DoorTrigger` instances in `level1` are the source-backed room doors. The manifest links each trigger to the authored pivot Transform, renderer and mesh, explicit collider, Euler target, duration, close speed, and world transform.

| Room | `DoorTrigger` | Pivot Transform | Renderer | Action target | Raycast collider | Door collider | Open Y offset | Open / close |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Kitchen | 4138 | 1640 | 2141 | 3976 | 2425 | 2398 | −90° | 1 / 0.5 s |
| Office | 4006 | 1998 | 2080 | 4148 | 2449 | 2429 | −89° | 1 / 0.5 s |
| BigRoom | 4019 | 1719 | 2186 | 4205 | 2452 | 2457 | −90° | 1 / 0.5 s |
| Bathroom | 4207 | 1624 | 2149 | 4206 | 2453 | 2440 | −75° | 1 / 0.5 s |
| Pantry | 3946 | 1971 | 2167 | 4253 | 2460 | 2435 | −90° | 1 / 0.5 s |
| Bedroom | 4104 | 1590 | 2089 | 4071 | 2439 | 2428 | −90° | 1 / 0.5 s |

All six pivots are children of Transform 1602. `DoorTrigger.Awake` captures the pivot's world rotation as positive Euler degrees. Normal opening targets `(startX, startY + _openAngle, startZ)` over `_duration`; closing returns to the captured start rotation over `_duration / _closeSpeedModifier`. The serialized values give one second to open and half a second to close. The recovered IL passes numeric SetEase values 9 for the open tween and 2 for close. `OutCubic` and `InSine` are the corresponding values in the standard DOTween Ease enum; that third-party enum declaration itself is not retained in the source archive. The room extra-action coroutine awaits its tween before returning. The exact inherited view dispatch point relative to an Android 2D scene change is not proven here.

The separate generic `TriggerObjectOpenDoor` component also has six instances, all in `level4`, which BuildSettings identifies as `Assets/_Scenes/Dreams/StrangeMorning/s4_StrangeMorning.unity`. The manifest records their transforms, renderers, 1-second durations, XYZ Euler targets and four serialized `Dream_bodyeater_whisperdoor_*` sound choices. These belong to a dream scene and do not prove which object the campaign's `open_door` action should animate. The main house scene has six interior `DoorTrigger` records and no separately identified front-door instance.

## Character and scene sprites

`AnimationData.Duration` is `Frames.Length / FramesPerSecond`. Its cycling enum is `PlayOnce=0`, `Cycle=1`, and `FixLastFrame=2`; FPS is an integer with constructor default 8. `animation_manifest.json` lists all 39 scene `AnimatedImage` components with ordered frame PPtrs, FPS, cycle type, and duration, plus 27 source character-emotion animation sequences. The exports preserve exact frame order and asset IDs.

The recovered playback semantics are: `Cycle` loops, `PlayOnce` disables the `Image` after the last-frame delay, and `FixLastFrame` retains the final frame. A host elapsed-time scheduler adapts Unity's coroutine playback and does not claim identical scheduling. Character emotion clips are associated with runtime-selected emotions. Their presence in source data does not establish that those characters appear, or that a clip is active, at campaign start. The 61 room character views use authored pose sprites; the evidence does not claim every NPC has idle animation.

To regenerate the manifest and stage missing scene animation PNGs under `reconstruction/android-current/app/src/main/assets/ui/exported_images` without rerunning the full asset-preparation pipeline:

```sh
PYTHONPATH=tools/python-deps python3 tools/reverse-animations/export_animation_evidence.py \
  --data restore-v08/unity-data --stage-extras
```

The character emotion frames already have staged paths under `assets/sprites/`; the scene `AnimatedImage` frame records point to the `ui/exported_images/` assets.

## Static validation

Validate the JSON and extraction with:

```sh
python3 -m json.tool reconstruction/reverse-animations/animation_evidence.json >/dev/null
python3 -m json.tool reconstruction/reverse-animations/animation_manifest.json >/dev/null
python3 tools/reverse-animations/validate_animation_manifest.py
```
