# Recovered original gameplay UI

`ui_manifest.json` contains the authored level 1 UI hierarchy grouped for the Android renderer as `scenes.world`, `scenes.room`, `scenes.dialogue`, and `scenes.pause`. Components preserve source path IDs, GameObject names and ancestor paths, Canvas sorting data, RectTransforms, active/enabled startup state, and relevant image or text fields.

Run the exporter against the original Unity data directory:

```sh
python tools/reverse-ui/extract_ui.py --data path/to/NoImNotAHuman_Data
```

Rectangles use top-left coordinates in `[left, top, width, height]` order relative to 1920×1080. The extractor calculates them recursively from anchors, pivots, anchored positions, and size deltas. Screen-space Canvas roots use the reference viewport, including nested canvases whose own serialized transforms are zero-sized.

Images retain their sprite PPtr, Unity Image type, color, preserve-aspect bit, and raycast setting. Sprite exports preserve source ID, dimensions, SHA-256, sprite border, rect, and pivot. This keeps the nine-slice border available for `Sliced` Images. All exported PNGs are original Unity sprites.

TMP text keeps the serialized text and resolved font-asset candidates. Where the serialized values validate, the manifest includes font size (raw byte offset 300) and face color (offset 160). Five source TTF files are exported for Android Typeface use; the original TMP atlas is also exported when it has usable dimensions. Text alignment is null because that serialized field was not independently confirmed.

`visible` reports serialized startup hierarchy and component enabled state. Pause items include `pause_open` and Settings children include `settings_open`; dialogue items use `dialogue_open`. HUD hint and controls visibility is presenter-driven. Runtime animation, localization, clipping, and dialog state can change authored startup visibility.

The tool reads `level1`, `globalgamemanagers.assets`, `sharedassets0.assets`, `sharedassets1.assets`, `resources.assets`, and adjacent `.resS` streams via UnityPy. It does not load or execute the original executable or native libraries. Runtime visibility references are the retained `HUDView.cs`, `DialogView.cs`, `PauseMenuView.cs`, and `FakeDialogRunner.cs` managed-source stubs and ISIL.
