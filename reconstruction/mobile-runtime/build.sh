#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="$(cd "$ROOT/../.." && pwd)"
SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$WORKSPACE/tools/android/sdk}}"
NDK_ROOT="${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-$SDK_ROOT/ndk/27.2.12479018}}"
BUILD_TOOLS="${ANDROID_BUILD_TOOLS:-$SDK_ROOT/build-tools/35.0.0}"
PLATFORM="${ANDROID_PLATFORM:-$SDK_ROOT/platforms/android-35}"
ECJ_JAR="${ECJ_JAR:-$WORKSPACE/tools/android/ecj/ecj-3.38.0.jar}"
OUT="$ROOT/app/build"
ANDROID_JAR="$PLATFORM/android.jar"

# Refresh the actual build inputs; never package stale exports made before key recovery.
python3 - "$WORKSPACE" "$ROOT" <<'PY'
import json
import re
import shutil
import sys
from pathlib import Path
workspace, root = map(Path, sys.argv[1:])
source = workspace / 'reconstruction'
assets = root / 'app/src/main/assets'
for locale in ('english_en_', 'portuguese_brazil_pt-br_'):
    target = assets / f'localization/{locale}.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / f'assets/localization/{locale}.json', target)
target = assets / 'narrative/program.json'
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source / 'narrative/program.json', target)
images = source / 'assets/images'
scene_aliases = {
    re.sub(r'[^A-Za-z0-9._-]+', '_', row['name']) + '.png': images / row['output']
    for row in json.loads((images / 'scene_manifest.json').read_text())
}
java = (root / 'app/src/main/java/org/reconstruction/viewer/MainActivity.java').read_text()
image_block = java.split('String[] IMAGES = {', 1)[1].split('};', 1)[0]
for name in re.findall(r'"([^\"]+\.png)"', image_block):
    candidates = [images / name, images / 'backgrounds' / name, scene_aliases.get(name)]
    original = next((path for path in candidates if path and path.is_file()), None)
    if original is None:
        raise SystemExit(f'Missing recovered image required by Android UI: {name}')
    target = assets / 'images' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original, target)
PY

for tool in aapt2 d8 zipalign apksigner; do
    [[ -x "$BUILD_TOOLS/$tool" ]] || { echo "Missing Android build tool: $BUILD_TOOLS/$tool" >&2; exit 2; }
done
[[ -f "$ANDROID_JAR" ]] || { echo "Missing Android platform jar: $ANDROID_JAR" >&2; exit 2; }
[[ -x "$NDK_ROOT/toolchains/llvm/prebuilt/linux-x86_64/bin/clang" ]] || {
    echo "Android NDK 27.2.12479018 is required at $NDK_ROOT." >&2; exit 2;
}
command -v cargo >/dev/null 2>&1 || { echo "Install stable Rust/Cargo with rustup first." >&2; exit 2; }
command -v java >/dev/null 2>&1 || { echo "Java 17 or newer is required." >&2; exit 2; }
if ! command -v javac >/dev/null 2>&1 && [[ ! -f "$ECJ_JAR" ]]; then
    mkdir -p "$(dirname "$ECJ_JAR")"
    command -v curl >/dev/null 2>&1 || { echo "Install javac or curl to obtain the ECJ compiler." >&2; exit 2; }
    curl -L --fail --silent --show-error --output "$ECJ_JAR" \
        https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.38.0/ecj-3.38.0.jar
fi

export ANDROID_SDK_ROOT="$SDK_ROOT" ANDROID_NDK_HOME="$NDK_ROOT" ANDROID_NDK_ROOT="$NDK_ROOT"
if ! cargo ndk --version >/dev/null 2>&1; then cargo install --locked cargo-ndk; fi

rm -rf "$OUT"
mkdir -p "$OUT/classes" "$OUT/dex" "$OUT/jniLibs" "$OUT/stage/lib/arm64-v8a" "$OUT/stage/lib/x86_64"
(cd "$ROOT/native" && cargo ndk -t arm64-v8a -t x86_64 -o "$OUT/jniLibs" build --release)
JAVA_SOURCE="$ROOT/app/src/main/java/org/reconstruction/viewer/MainActivity.java"
if command -v javac >/dev/null 2>&1; then
    javac --release 8 -classpath "$ANDROID_JAR" -d "$OUT/classes" "$JAVA_SOURCE"
else
    java -jar "$ECJ_JAR" -source 8 -target 8 -classpath "$ANDROID_JAR" -d "$OUT/classes" "$JAVA_SOURCE"
fi
"$BUILD_TOOLS/d8" --lib "$ANDROID_JAR" --min-api 23 --output "$OUT/dex" $(find "$OUT/classes" -name '*.class' -print)

"$BUILD_TOOLS/aapt2" link \
    -o "$OUT/base.apk" \
    -I "$ANDROID_JAR" \
    --manifest "$ROOT/app/src/main/AndroidManifest.xml" \
    --min-sdk-version 23 --target-sdk-version 28 \
    --version-code 1 --version-name 0.1-recovery-prototype \
    -A "$ROOT/app/src/main/assets"
cp "$OUT/dex/classes.dex" "$OUT/stage/classes.dex"
cp "$OUT/jniLibs/arm64-v8a/librecovery_viewer.so" "$OUT/stage/lib/arm64-v8a/"
cp "$OUT/jniLibs/x86_64/librecovery_viewer.so" "$OUT/stage/lib/x86_64/"
cp "$OUT/base.apk" "$OUT/unsigned.apk"
zip -q "$OUT/unsigned.apk" -j "$OUT/stage/classes.dex"
(cd "$OUT/stage" && zip -q -r "$OUT/unsigned.apk" lib)
"$BUILD_TOOLS/zipalign" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"

KEYSTORE="$OUT/reconstruction-debug.keystore"
keytool -genkeypair -noprompt -keystore "$KEYSTORE" -storepass android \
    -keypass android -alias reconstruction -dname "CN=NINAH Recovery Prototype" \
    -keyalg RSA -keysize 2048 -validity 10000 >/dev/null 2>&1
"$BUILD_TOOLS/apksigner" sign --ks "$KEYSTORE" --ks-key-alias reconstruction \
    --ks-pass pass:android --key-pass pass:android --out "$OUT/app-debug.apk" "$OUT/aligned.apk"
"$BUILD_TOOLS/apksigner" verify --verbose "$OUT/app-debug.apk"
"$BUILD_TOOLS/aapt2" dump badging "$OUT/app-debug.apk" | head -5
echo "APK: $OUT/app-debug.apk"
