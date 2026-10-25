# Static music recovery

`music_manifest.json` records the selected Unity `AudioClip` objects, their streamed resource ranges and hashes, original FSB payloads, source `AudioSource` evidence where the clip is directly assigned in a scene, and the final OGG hashes. `routing_evidence` preserves the `SoundData` (`sharedassets0.assets`, MonoBehaviour path ID 2718) and `SoundList` (path ID 2719) references, plus the directly verified menu and day-0 NIGHT sources. The custom MonoBehaviour type trees are stripped from the supplied Unity assets, so routes for days 1–18 are left explicitly unexpanded rather than guessed.

Install the static parser with `python3 -m pip install -r tools/reverse-music/requirements.txt`; ffmpeg and ffprobe must also be available. The recorded parser is UnityPy 1.25.4.

The export is reproducible from the SHA-verified ZIP rebuilt by `tools/security/restore_original_archive.py`:

```sh
python -m pip install -r tools/reverse-music/requirements.txt
python tools/reverse-music/export_original_music.py /path/to/NINAH-Original-v1.3.18.zip
```

The exporter statically reads Unity assets with UnityPy, saves the source FSB payloads, decodes the selected AudioClips to temporary WAV files, then encodes OGG Vorbis at ffmpeg quality 4. Each OGG is written to a stage-tmp file, fully decoded and probed before it replaces the exported version and enters the manifest. It does not load or run any original executable or library. `exported_music/*.ogg` and `exported_music/original_fsb/` are generated, ignored files; the source, evidence manifest and Java player remain tracked.

Run `python tools/reverse-music/validate_music_export.py` to verify the 14 keys, OGG hashes, durations, and full ffmpeg decode. Pass `--assets-root reconstruction/android-current/app/src/main/assets` to compare the staged copies and manifest too.

For the Android asset tree, copy the OGGs to `reconstruction/android-current/app/src/main/assets/music/` and the manifest to `reconstruction/android-current/app/src/main/assets/music_manifest.json`. The manifest's `extracted_asset` paths are relative to `reconstruction/reverse-music/`.
