# Native Android component build

Run `python3 tools/native-game/build_android.py` with official Android NDK
27.2.12479018 at `tools/android/android-ndk-r27c` and Rust 1.85.1 with the
`aarch64-linux-android` and `x86_64-linux-android` targets installed. The script
accepts `--ndk`, `--cargo`, and repeated `--abi` overrides.

Each ABI produces a C++ gameplay static archive (`libninah_gameplay.a`) and a
shared library exposing the nine Rust Yarn C ABI functions, including the
loader for recovered per-line metadata and VM snapshot dump/restore. Every
current C++ translation unit is compiled with strict warnings for Android API
23; linking rejects unresolved symbols. The report checks the resulting ELF
architecture, required libraries, exported Yarn functions and output hashes.

The shared library currently exports only the Yarn API. The C++ archive is an
input for the Android host still to be written. This is a cross-compilation
check, not a test on an Android device, a complete JNI integration, or an APK.
Original Windows code is neither linked into the components nor executed.

`ANDROID_BUILD_VALIDATION.json` is written only after all selected ABI builds
and static ELF checks complete successfully. Build products and toolchain
downloads are excluded from the source checkpoint.

The locally restored toolchain can be selected with `RUSTUP_HOME="$PWD/tools/rustup" CARGO_HOME="$PWD/tools/cargo" CARGO="$PWD/tools/cargo/bin/cargo"` before the Python command. `build.sh` detects this local installation automatically. Toolchain downloads are excluded from the checkpoint.

The current test APK has a separate build in `tools/android-current/build_apk.py`, linking all current C++ modules plus its JNI host. Its authoritative build/content report is `reconstruction/android-current/validation_report.json`; the standalone archive report describes the earlier component build.
