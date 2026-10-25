# Bootstrap evidence

`bootstrap_manifest.json` records the startup findings that are supported by the recovered native method bodies and the original serialized Unity scene. It keeps unresolved campaign behavior explicit so a host does not substitute an arbitrary node-picker start, roster, or energy default.

The evidence collectors parse serialized Unity objects with UnityPy; they never execute the original EXE or DLL. The scene collector is [extract_scene_bootstrap_evidence.py](../../tools/reverse-bootstrap/extract_scene_bootstrap_evidence.py). The Intro collector is [extract_intro_evidence.py](../../tools/reverse-bootstrap/extract_intro_evidence.py), and the menu collector is [extract_menu_evidence.py](../../tools/reverse-bootstrap/extract_menu_evidence.py).

The strongest verified facts are:

- Unity build index 0 is `s0_MainMenuScene`; index 1 is `s1_GameScene`. `MainMenuView.StartGameAsync` explicitly opens scene 1.
- Continue/load resolves `IGameSaveDataHandler` at DI binding ID 10 and starts with `isSkipFade=false`. For a new game, `MainMenuView.StartNewGameAsync` subscribes to `GachaWindow.CartoonEnded`; after EndingView signals completion, `MainMenuView.OnIntroCartoonEnded` resolves handler ID 11 and starts with `isSkipFade=true`.
- A newly constructed `DayNightSaveData` starts at day 0 and Night (`ETimeOfDay.Night == 1`) with a raw `DayActions` field of 0, zero extra energy slots, and an empty energy-fines map. `DayNightController.Init` then assigns `DayActions = MaxDayActions`; the retained day-0 table value is 1, so the initialized new-game energy is 1. The later save-load branch invokes `InitNewNight(true)`. The raw constructor value and initialized energy are distinct stages.
- The full raw parser recovered 73 `CharacterSOData` records. Its unique day-0 preset visitor is `Neighbour` (`character_type_value=3`, `character_type="Neighbour"`, `name="Neighbour"`), scheduled for day 0 guest 1, preset enabled, and minimum completed games 0. The retained 960-byte raw asset backs this record, and `production_configs.json` independently confirms the asset identity and enum value. This is a scheduled visitor, not proof that Neighbour is already in `CharactersInside` before the event fires.
- `GameEventsManager` starts `GenerateDingDongEventsForPresetAsync` from its constructor. That state machine waits until `IGameplayRandomizer` is ready and then calls `GenerateDingDongEventsForPreset`. The first configured preset event is Neighbour on day 0, guest 1; the recovered delay function returns 1 second for that pair. The exact moment the countdown begins and the event fires remains unknown.
- The level1 scene contains `SceneContext`/`GameplaySceneInstaller`, `PlayerInstance`, the dialog runner/view, localization provider, variable storage, and dialog commands. Its serialized `FirstMarker` components are on UI controls. They do not identify the first gameplay-scene Yarn node.
- The serialized `GameEventsData` asset (sharedassets0 path ID 2714) stores first-guest values 6–8 seconds and later-guest values 2–5 seconds. Native `GetDingDongDelay(0, 1)` instead returns a special 1.0-second constant. On a nonzero day, the recovered native body passes the first-guest minimum (6) and later-guest maximum (5) to `Random.Range`; it does not read the serialized first-guest maximum (8). The reversed 6-to-5 arguments are recorded as observed, without asserting Unity's result for that input. Which generator starts the first countdown is still unresolved.

The first new-game Intro subtitle is proven as `Intro_1`; this does not establish the first Yarn node after gameplay scene load. The first inside roster and chosen player start point remain unknown. The recovered day-0 preset visit identifies the first configured visitor but does not prove the current inside roster. `ResourceMother` (sharedassets0 path ID 2594) contains 72 possible characters; that array is a pool and is not evidence for the first inside roster. The title screen/menu path and player start position are different layers, so the scene snapshot does not imply where the player is initially placed.

The Intro ending is `EndingViewSOData` path ID 2707 (`EEnding.Intro=10`). Its VideoClip path ID 2562 is `Intro_Final_2_NO_SUBTITLES`, 1920x1080 at 24 fps with 1,728 frames, stereo audio, and a 72-second timeline. The subtitle nodes and active intervals are `Intro_1` 10–18s, `Intro_2` 20–23s, `Intro_3` 28–34s, `Intro_4` 43–52s, and `Intro_5` 59–72s. The referenced stream payload is exported under `exported_intro/`; its SHA-256 is recorded in `intro_evidence.json`.

The serialized menu scene is build index 0 (`s0_MainMenuScene`). Its `MainMenuView` component is path ID 2273 on provider GameObject 112. Selected original menu sprites and all selected menu GameObject/component transforms are in `menu_evidence.json`; the corresponding PNG exports are in `exported_menu/`. The main background, house, logo, face eyes, teeth, and button sprites are sharedassets0 path IDs 2048, 1616, 1863, 2213, 2309, and 1769. The five primary buttons share 200x75 layouts at anchored x positions -440, -220, 0, 220, and 440 (New Game, Continue, Settings, Collection, Quit respectively), each y=105.

The next verified dialogue after Neighbour is admitted and then interacted with is `talk_neighbour_1`, when that character has zero saved room talks. `ARoom.GetDialogName` selects `talk_<lowercase type>_<talk count + 1>`; completed entrance dialogues do not increment the room-talk count. The full boundary and limits are recorded in [first-night-continuation.md](first-night-continuation.md).

The serialized `UnityEngine.UI.Image.preserveAspect` flag is true for all seven room background Images and all 61 character Images (field byte offset 104). The per-component values are in `image_layout_evidence.json`; character sprites themselves are swapped by runtime animation, while the Image component's preserve-aspect setting is serialized.

Native method references point into `reconstruction/logic/recovered_isil/Assembly-CSharp/`; their method names and retained body paths are recorded in the manifest. Exact native entrypoint RVAs were not independently mapped. The GameAssembly SHA-256 in the manifest pins the recovered listing to the analyzed binary.

To regenerate the scene evidence from the extracted data directory:

```sh
python3 tools/reverse-bootstrap/extract_scene_bootstrap_evidence.py \
  /path/to/NoImNotAHuman_Data \
  reconstruction/reverse-bootstrap/level1_bootstrap_evidence.json

python3 tools/reverse-bootstrap/extract_intro_evidence.py \
  /path/to/NoImNotAHuman_Data \
  reconstruction/reverse-bootstrap/intro_evidence.json \
  --export-video reconstruction/reverse-bootstrap/exported_intro/Intro_Final_2_NO_SUBTITLES.mp4

python3 tools/reverse-bootstrap/extract_menu_evidence.py \
  /path/to/NoImNotAHuman_Data \
  reconstruction/reverse-bootstrap/menu_evidence.json \
  --sprite-dir reconstruction/reverse-bootstrap/exported_menu

python3 tools/reverse-bootstrap/extract_image_layout_evidence.py \
  /path/to/NoImNotAHuman_Data \
  reconstruction/reverse-scenes/scene_render_manifest.json \
  reconstruction/reverse-rooms/room_manifest.json \
  reconstruction/reverse-bootstrap/image_layout_evidence.json
```
