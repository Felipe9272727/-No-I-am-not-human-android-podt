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
python3 tools/android-current/build_apk.py --skip-assets --reference-apk <current-apk> --version-code 4 --version-name 0.4-shaders-ui --output deliverables/NINAH-Port-3D-UI.apk
```

The reference APK must match LATEST_BUILD.json and its 52-file C++/Rust source
fingerprint. Changes to native sources require a real native rebuild.
`python3 tools/android-current/qa/run_gles_test.py` exercises host Mesa GLES2,
including the narrowly scoped shader-compiler fallback. This does not replace
Android execution or the user phone crash report.

Before delivering, run `python3 tools/android-current/qa/check_apk_shaders.py
deliverables/NINAH-Port-3D-UI.apk --render`. The 12 namespaced GDX resources
(including six GLSL files) must be packaged in the APK, not supplied by a
development jar. See `shader_v04_validation.json` for the isolated check.
