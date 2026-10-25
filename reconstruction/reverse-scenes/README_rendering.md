# Scene character, dialog and examination rendering evidence

`scene_render_manifest.json` joins the authored room character views to the already decoded `CharacterSOData` poses, emotion registry, and human/imposter sign assets. The exporter reads `level1` and `globalgamemanagers.assets` with UnityPy static parsing and does not execute the recovered PE or managed code. Every scene component and asset reference retains its Unity file/path ID.

Run the exporter from the repository root with:

```sh
python tools/reverse-scenes/export_scene_render_manifest.py \
  --data malware-review/No.Im.not.a.Human.v1.3.18/No.Im.not.a.Human.v1.3.18/NoImNotAHuman_Data
python tools/reverse-scenes/export_scene_sprites.py \
  --data malware-review/No.Im.not.a.Human.v1.3.18/No.Im.not.a.Human.v1.3.18/NoImNotAHuman_Data
python tools/reverse-scenes/validate_scene_render_manifest.py
```

The current export contains 61 room character instances across the seven rooms, 61 character data records, one `DialogView`, one `DialogSignsView`, two moving sign views, one eye view, 39 `AnimatedImage` components, 32 Canvas components, 32 CanvasScaler components, and two cameras.

The separate `exported_scene_assets/manifest.json` contains ten additional exact PNGs absent from the character asset export: seven room backgrounds and three `DialogView` overlay sprites. All room pose, dialog emotion, and examination sprite references already resolve in `exported_character_assets/manifest.json`; no extra examination asset extraction was needed.

## Room characters

The scene component is `_Code.Rooms.CharacterRoomObjectView`, derived from `_Code.Rooms.ARoomObjectView<ERoomPeopleState>`. Its serialized `Data` pointer is at raw offset 56, `_startState` at 68, corpse material at 72, and inherited `_button` / `_image` pointers at 32 / 44. The data pointer in `level1` resolves through external file ID 3 to `sharedassets0.assets`.

On `Awake`, the generic view selects the authored start state from `CharacterSOData.Poses`. The selected pose provides the image sprite and sets the view transform local position to `(PositionShift.x, PositionShift.y, 0)` and local scale to `(ScaleShift.x, ScaleShift.y, 0)`. Runtime pose selection repeats that state lookup. `CharacterRoomObjectView.TryStartDialog` rejects interaction when the selected pose has `CannotInteract=true`. The manifest records every pose and the serialized initial state; runtime save state still needs to choose the live pose.

## Dialog character

The room image and dialog portrait are separate. The room view uses the active pose sprite. `_Code.DialogSystem.DialogView.SetCharacterEmotion` gets a character `AnimationData` for the requested emotion and applies an optional emotion override to the dialog portrait transform. The position rule recovered from ISIL is `override.Position + CharacterSOData.DialogPosition`. The verified scale rule is `(CharacterSOData.DialogScale, CharacterSOData.DialogScale, CharacterSOData.DialogScale) + override.Scale`. The native body multiplies Vector3.one by DialogScale before adding the override; the earlier ISIL inference had incorrectly multiplied the override as well. When no emotion override exists, the view uses zero position and zero scale delta. The Base emotion enum value is `-1966747463`.

`DialogView` serializes its parent Canvas at offset 32 and reserve Camera at offset 268. Its `LastUsedCamera` method returns `parentCanvas.worldCamera` when a parent Canvas is present. The scene has two cameras: `Main Camera` (path ID 2060, 60 degree field of view) and `PeepholeCam` (path ID 2059, 32.9 degree field of view). Canvas render modes, sorting orders, world cameras, CanvasScaler scale modes, and reference resolutions are included in the JSON. The dialogue Canvas is path ID 3101 on GameObject 529 and uses Main Camera with a 1920×1080 Scale With Screen Size reference.

## Examination signs

`DialogSignsView.ShowSign` first disables all sign containers, then enables and fills the chosen container. `ECharacterSign` values are Eye 0, Hands 1, Teeth 2, AuraPhoto 3, Armpit 4, and Ear 5. The `CharacterSOData` getters choose human or imposter data using runtime `IsImposter`.

Eye examination assigns white and iris sprites and starts `MoveIris`; eye movement uses the authored distance multiplier and min/max durations plus random target points. Hands assign a sprite and move using the serialized start/end positions, easing, duration, and pre-delay. Teeth assign a sprite. AuraPhoto assigns a photo sprite and uses the same moving-content animation. Armpit and Ear use `AnimatedImage` with `AnimationData` frames, FPS, and cycling type. No photo sound array is serialized. The source data includes all human/imposter sprites and animation frames by PPtr.

`DialogCommandsInstance.ShowSign` resolves the character by name from `ICharactersSODataProvider`, parses the requested `ECharacterSign`, then raises the sign event. `DialogManager.OnSignShowed` delegates to `DialogView.ShowSign` and updates the sign-shown runtime flag. No per-sign unlock predicate appears in that command path. `PlayerSigns` tracks fake-state booleans for teeth, hands, eyes, armpit, and photo; it has no ear fake-state field, and those flags describe player signs rather than gating character examination. `DialogSignElementViewMovingContent.Move` waits for `BeforeDelay`, then tweens from the serialized start to end position with the authored ease and duration. `AnimatedImage.StartAnimationOrSetFirstFrame` shows the first frame for `Cycle` mode and starts its playback coroutine for other modes. The renderer needs the active runtime character, `IsImposter`, requested sign, and current animation time to reproduce a live examination. It should use the scene containers and source assets in the manifest rather than treating dialog content as a static gallery.

## Limits

The export records authored state and data. It does not simulate Yarn execution, runtime character state, audio playback, or animation frame clocks. Eye targets depend on runtime randomness. Exact device presentation also depends on runtime screen dimensions and safe area; CanvasScaler reference resolutions and camera settings are recovered, while device geometry must come from Android.
