# Recovered Asset Viewer — Android Rust prototype

This is a native Android application with a Java Android UI and Rust JNI runtime. It runs selected real nodes from the recovered Yarn graph, shows touchable choices when the graph emits them, displays the recovered command text without executing game commands, and includes a gallery of extracted PNGs plus an English/Brazilian Portuguese localization catalog. Its screens are explicitly labeled a recovery prototype. It does not reproduce the original game's rooms, examination logic, state integration, or full progression.

The Rust side embeds the recovered Yarn interpreter as a local crate dependency. The initial picker offers a small set of verified entry nodes; options follow the recovered graph's destinations. The interpreter observes a step budget, surfaces commands as text, and reports missing game hooks without pretending to perform their effects. Localized line keys are joined against the extracted key-to-text records. The catalog preserves the source order and record text and does not infer links between adjacent dialogue entries.

## Build

Requirements: stable Rust, Android SDK platform 35, Android build-tools 35.0.0, Android NDK 27.2.12479018, Java 17, Python 3, and `cargo-ndk` (the build script installs `cargo-ndk` if absent). A Java compiler is needed; the script uses `javac` when present or downloads ECJ to a local build-tool cache. The build uses the Android SDK's `aapt2`, `d8`, `zipalign`, and `apksigner` directly, so Gradle is not required. Set `ANDROID_SDK_ROOT` or `ANDROID_HOME`, `ANDROID_NDK_HOME`, `ANDROID_BUILD_TOOLS`, `ANDROID_PLATFORM`, or `ECJ_JAR` to override the workspace defaults. Then run:

```sh
./build.sh
```

The self-signed prototype APK is written to `app/build/app-debug.apk` and includes `arm64-v8a` and `x86_64`. Its local reconstruction debug key is generated under `app/build/` and must not be used for release signing. For Rust unit tests, run `cargo test --manifest-path native/Cargo.toml`.

The bundled localization files and images are copied from `reconstruction/assets`. Only English and Brazilian Portuguese are currently bundled to keep the prototype small; all 18 extracted locale files remain available in the recovery source tree. The APK is an inspection tool, not a playable game build.
