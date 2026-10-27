# Recovery and build inputs

The Git repository preserves editable source, generators, tests and reports.
The original game media and generated build caches are separate inputs.

The validated private backup is `NINAH-Reconstrucao-Rust-Checkpoint.zip`, version
8. It contains the prior opening preview, narrative/localization data, character
exports and source evidence. The original archive is preserved in three parts;
see `reconstruction/security/ORIGINAL_ARCHIVE_RECOVERY.json` in that checkpoint.
Original ZIP SHA-256:
`f8e6a46efbd41452266790a1350bbec3cfd6027470282171b912df80b08489f1`.

Restore data into a temporary directory first. Copy required asset/data inputs
into the checkout without overwriting newer source files from Git. The original
source archive is needed to regenerate world and UI exports. Use the static
extractors under `tools/reverse-world/` and `tools/reverse-ui/`; their README
files describe the expected Unity data directory.

The stable debug key is preserved separately as `NINAH-Port-Chave-Teste.zip`.
Restore it to `tools/android-current/signing/port-debug.keystore`; never commit
the actual key. The private owner can retrieve these existing saved files.

Build with Java 17, Android SDK/Build-Tools 35, NDK r27c and Rust 1.85.1 plus
aarch64-linux-android/x86_64-linux-android targets. The build scripts pin libGDX
1.14.2 and its runtime dependencies. Run from the checkout root:

```sh
python3 tools/android-current/build_apk.py
```

The source repository alone is not a complete distributable game: it requires
the supplied data and does not yet implement the full campaign.

For a Java-only diagnostic rebuild, the current delivered APK can supply its
unchanged native libraries and staged assets. Restore its assets/ members under
`reconstruction/android-current/app/src/main/assets`, then run:

```sh
python3 tools/android-current/build_apk.py --skip-assets --reference-apk <current-apk> --version-code 12 --version-name 0.12-scene-fidelity --output deliverables/NINAH-Port-Cena-Original.apk
```

The reference APK must match LATEST_BUILD.json and its 53-file C++/Rust source
fingerprint. Changes to native sources require a real native rebuild.
`python3 tools/android-current/qa/run_gles_test.py` exercises host Mesa GLES2,
including the narrowly scoped shader-compiler fallback. This does not replace
Android execution or the user phone crash report.

Before delivering, run `python3 tools/android-current/qa/check_apk_shaders.py
deliverables/NINAH-Port-Cena-Original.apk --render`. The 12 namespaced GDX resources
(including six GLSL files) must be packaged in the APK, not supplied by a
development jar. See `shader_v04_validation.json` for the isolated check.


## Music and texture recovery

The v0.5 APK includes the staged music and its provenance manifest, so extracting
its assets/ entries restores these inputs too. To migrate staged v0.4 data,
restore and verify the original three-part archive and the private
NINAH-Recursos-3D-UI.zip bundle, then run:

```sh
python3 tools/android-current/repair_staged_textures.py /path/to/NINAH-Recursos-3D-UI.zip
python3 tools/reverse-music/export_original_music.py /path/to/original.zip
python3 tools/android-current/prepare_assets.py --music-only
python3 tools/reverse-music/validate_music_export.py --assets-root reconstruction/android-current/app/src/main/assets
```

Use trusted UnityPy, ffmpeg and ffprobe. Original executables/libraries are never
loaded. The repair requires the exact source-bundle hash and reproduces the
existing world_manifest.android_sha256 values. Generated music, FSB chunks,
world textures, APKs and signing keys stay outside Git. The music manifest and
extractor are tracked; new encodes record their actual OGG hashes.

The final packager reopens the closed APK for another ZIP CRC/signature/hash
check after report collection. Independent final verification also uses
`apksigner verify --verbose --print-certs`. A rejected first v0.5 artifact was
repacked; only the exact hash in LATEST_BUILD.json is deliverable.


## Lossless mesh preparation (v0.6)

When migrating a staged v0.4/v0.5 tree, run
`python3 tools/mesh-opt/optimize_world.py --apply` before the skip-assets build.
The helper compiles its new C++ source with g++ and includes a pinned, SHA-checked
MIT-licensed subset of meshoptimizer. The candidate manifest stays generated;
source blobs remain under world/models and optimized copies under models_android.
The APK contains only the referenced optimized copies. Rebuilding directly from
a v0.6 APK needs no reoptimization; its extracted assets already contain them.
Rerunning optimization requires the original blobs from the saved earlier APK
or source bundle. The C++/Rust game fingerprint is unchanged; this new C++ tool
runs offline and does not add a new Android JNI library.

Validate with the Java geometry/visibility/resolution tests and isolated final
APK shader/render test. These host results do not measure Xiaomi FPS or validate
Android SurfaceHolder resizing. See release_v06_summary.json for exact scope.


The v0.7 rebuild changes only Java/manifest presentation paths, retaining the
same52-file native fingerprint. Restore the assets from the latest saved APK
and use that exact APK with --reference-apk after checking LATEST_BUILD.json.
Run WorldInteractionTest and RenderLoopPolicyTest in addition to existing Java
and GLES checks. Host captures do not exercise Android Canvas acceleration;
private Options/Diagnostic reports actual hardware/software Canvas, HUD timing
and input redraw counts for a physical-device test.


## Current v0.11 recovery

The delivered `NINAH-Port-Gato-Save.apk` contains all staged assets, including the small original cat mesh, cutout texture and separate manifest. Restore all of its `assets/` entries under the current app asset directory and use `--skip-assets`. The source manifest under `reconstruction/reverse-world/cat3d/` is metadata only; source BIN/PNG media are deliberately absent from Git. To regenerate them, run `tools/reverse-world/export_cat3d.py` against the static Unity data and the original archive's texture sidecar as documented in `reconstruction/reverse-world/CAT3D.md`, then stage normally.

The native-source fingerprint now covers 53 inputs; v0.8/v0.9/v0.10 JNI libraries do not match the current native save implementation. A reference build may use only the exact v0.11 APK hash recorded in LATEST_BUILD.json and an identical current native fingerprint. Otherwise rebuild Rust and C++ for both ABIs. NDK extraction must preserve Unix symlinks (35 in r27c), and Build-Tools executables including d8 must be executable. Run the host campaign test in its isolated build directory; do not reuse objects from diagnostic runs.

Private Android disk saves are installed-app data, not bundled in the APK. Manual **Salvar jogo**, close/reopen, then **Continuar** still needs a phone test. The debug cat option defaults off and is separate from campaign save data.


## v0.12 fidelity data

`NINAH-Port-Cena-Original.apk` contains the corrected staged room sibling order and `assets/presentation/ui/sign_layout.json`. Restore all assets from this APK when using `--skip-assets`. The sign metadata source is tracked at `reconstruction/reverse-ui/sign_layout.json`; full staging copies it automatically. `export_sign_layout.py` reads only level1/globalgamemanagers.assets and the recovered UI manifest, validates 12-byte PPtrs and the 80-byte MovingContent/Eye objects, then emits source image order, masks and movement fields. The corrected room exporter follows serialized Transform.m_Children. Do not restore an older room_manifest/room_layers file over these sources.

Native rules are identical to v0.11; this release reused JNI only while the exact v0.11 APK and all 53 native input hashes matched the previous lock. Future rebuilds must use the current APK hash in LATEST_BUILD.json or compile native code again. Source world parity can be independently checked with `PYTHONPATH=tools/python-deps python tools/reverse-world/audit_world_parity.py --data /path/to/unity-data`. Without raw data the tool explicitly reports that raw-source verification is skipped.

The current signer requires both `port-debug.keystore` and `signing.json` from the existing private key archive in `tools/android-current/signing/`. It never generates a replacement key or supplies embedded fallback passwords. Signing uses environment references for the tool invocation and checks the public certificate fingerprint. The private configuration stays ignored by Git.

## v0.13 house reconstruction

The current artifact is `NINAH-Port-Casa-v013.apk` (0.13-house-fidelity). Restore all assets from it for `--skip-assets`; the new `presentation/ui/tv_source_manifest.json` supplies fixed-room-actor and dialogue rules. `presentation/assets.json` includes `house_scene_manifest` and source parent offsets for all 61 actor layouts.

The room export now includes raw object-state tables. Fridge state 2 is always drawn; interaction activity does not hide its sprite. The TV remains a room fixture rather than an admitted visitor. Source dialogue X=385/-575 is applied to the serialized line/options geometry separately, with the options panel copying the base panel position. Portraits precede dialogue panels according to raw Transform child order.

The world manifest retains its original 100 mesh entries and adds one baked source skinned pose at index 100. Metadata for all six SkinnedMeshRenderers is retained, with only source-active renderer 2558 baked. To regenerate, export the original Unity data and run `tools/android-current/stage_skinned_world.py --source-export /path/to/export/world_manifest.json`; the sidecar JSON is tracked, while mesh bytes stay in the APK/private data. The source materials/textures already exist in the base staging and are checked by ID/hash. No Animator clip is evaluated.

Builder packaging now keeps only referenced source model files, preserves the aapt2 resource ZIP, and creates/validates a separate unsigned archive before alignment and signing. The final signed artifact is installed atomically. Native sources are unchanged from v0.11/v0.12; future reference builds must use the exact current LATEST_BUILD hash and unchanged 53-input fingerprint.
