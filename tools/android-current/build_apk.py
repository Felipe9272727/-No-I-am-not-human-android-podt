#!/usr/bin/env python3
"""Build and validate the current reconstructed Android test APK."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ANDROID_ROOT = ROOT / "reconstruction/android-current"
ANDROID_APP = ANDROID_ROOT / "app/src/main"
ASSET_DIR = ANDROID_APP / "assets"
NATIVE_ROOT = ROOT / "reconstruction/native-game"
BRIDGE_MANIFEST = NATIVE_ROOT / "bridge/Cargo.toml"
BRIDGE_ROOT = NATIVE_ROOT / "bridge"
DEFAULT_APK = ROOT / "deliverables/NINAH-Port-3D.apk"
REPORT = ANDROID_ROOT / "port3d_validation_report.json"
PACKAGE_NAME = "org.reconstruction.port.preview"
JNI_ACTIVITY = "org.reconstruction.current.MainActivity"
KEYSTORE = ROOT / "tools/android-current/signing/port-debug.keystore"
KEY_ALIAS = "port-preview"
KEY_PASSWORD = "android"
GDX_ROOT = ROOT / "tools/android-current/libgdx/1.14.2"
ANDROIDX_ROOT = ROOT / "tools/android-current/libgdx/androidx"
ANDROIDX_CLASS_ROOT = ANDROIDX_ROOT / "extracted"
INTRO_ASSET = "assets/intro/Intro_Final_2_NO_SUBTITLES.mp4"
INTRO_SHA256 = "67d32bc7e28e5bbb528c7553650d8c594138031f358e249ec011db559b54b9d2"
ANDROID_API = "35"
MIN_API = "23"
ABIS = {
    "arm64-v8a": "aarch64-linux-android",
    "x86_64": "x86_64-linux-android",
}
ANDROID_NS = "http://schemas.android.com/apk/res/android"


def run(command: list[str], *, cwd: Path | None = None, env=None, capture=False) -> str:
    print("+", " ".join(str(part) for part in command), flush=True)
    result = subprocess.run(
        [str(part) for part in command], cwd=cwd, env=env,
        check=True, text=True, stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    return result.stdout or "" if capture else ""


def ensure_local_ecj() -> Path:
    """Restore the pinned compiler fallback from official Maven Central."""
    compiler_dir = ROOT / "tools/android-current/java"
    compiler_dir.mkdir(parents=True, exist_ok=True)
    artifact = compiler_dir / "ecj-3.38.0.jar"
    expected_sha1 = "86b2e4ab1d6aef91cb21f4d2ec364afb75d05b2c"
    if not artifact.is_file():
        url = "https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.38.0/ecj-3.38.0.jar"
        temporary = artifact.with_suffix(".jar.download")
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        if hashlib.sha1(temporary.read_bytes()).hexdigest() != expected_sha1:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("pinned ECJ download failed SHA-1 verification")
        temporary.replace(artifact)
    if hashlib.sha1(artifact.read_bytes()).hexdigest() != expected_sha1:
        raise RuntimeError("pinned ECJ compiler SHA-1 mismatch")
    return artifact


def choose_sdk() -> Path:
    for env_name in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        value = os.environ.get(env_name)
        if value and (Path(value) / "platforms/android-35/android.jar").is_file():
            return Path(value)
    return ROOT / "tools/android/sdk"


def find_build_tools(sdk: Path) -> Path:
    candidates = sorted((sdk / "build-tools").glob("35*"), reverse=True)
    for candidate in candidates:
        if all((candidate / name).is_file() for name in ("aapt", "aapt2", "d8", "zipalign", "apksigner")):
            return candidate
    raise FileNotFoundError("Android Build-Tools 35 (aapt/aapt2/d8/zipalign/apksigner) not found")


def find_ndk() -> tuple[Path, Path]:
    ndk = Path(os.environ.get("ANDROID_NDK_HOME", ROOT / "tools/android/android-ndk-r27c"))
    host_tag = "linux-x86_64"
    bin_dir = ndk / "toolchains/llvm/prebuilt" / host_tag / "bin"
    if not bin_dir.is_dir():
        raise FileNotFoundError(f"NDK LLVM toolchain not found under {ndk}")
    return ndk, bin_dir


def cargo_path() -> str | None:
    configured = os.environ.get("CARGO")
    if configured and Path(configured).is_file():
        return configured
    managed = ROOT / "tools/cargo/bin/cargo"
    if managed.is_file():
        return str(managed)
    on_path = shutil.which("cargo")
    if on_path:
        return on_path
    candidates = sorted((ROOT / "tools/rustup/toolchains").glob("*/bin/cargo"), reverse=True)
    return str(candidates[0]) if candidates else None


def engine_runtime_jars(work: Path) -> tuple[list[Path], dict[str, Path], list[Path]]:
    """Extract Android AAR classes/resources and return GDX jars/native jars."""
    backend_aar = GDX_ROOT / "gdx-backend-android-1.14.2.aar"
    androidx_core = ANDROIDX_ROOT / "core-1.17.0.aar"
    versionedparcelable = ANDROIDX_ROOT / "versionedparcelable-1.1.1.aar"
    lifecycle_runtime = ANDROIDX_ROOT / "lifecycle-runtime-2.6.2.aar"
    core_viewtree = ANDROIDX_ROOT / "core-viewtree-1.0.0.aar"
    artifacts = [
        (GDX_ROOT / "gdx-1.14.2.jar", "com.badlogicgames.gdx:gdx:1.14.2"),
        (backend_aar, "com.badlogicgames.gdx:gdx-backend-android:1.14.2"),
        (GDX_ROOT / "gdx-jnigen-loader-2.5.2.jar", "com.badlogicgames.gdx:gdx-jnigen-loader:2.5.2"),
        (GDX_ROOT / "gdx-platform-1.14.2-natives-arm64-v8a.jar", "com.badlogicgames.gdx:gdx-platform:1.14.2:natives-arm64-v8a"),
        (GDX_ROOT / "gdx-platform-1.14.2-natives-x86_64.jar", "com.badlogicgames.gdx:gdx-platform:1.14.2:natives-x86_64"),
        (androidx_core, "androidx.core:core:1.17.0"),
        (ANDROIDX_ROOT / "collection-jvm-1.4.2.jar", "androidx.collection:collection-jvm:1.4.2"),
        (versionedparcelable, "androidx.versionedparcelable:versionedparcelable:1.1.1"),
        (ANDROIDX_ROOT / "kotlin-stdlib-2.0.21.jar", "org.jetbrains.kotlin:kotlin-stdlib:2.0.21"),
        (lifecycle_runtime, "androidx.lifecycle:lifecycle-runtime:2.6.2"),
        (ANDROIDX_ROOT / "lifecycle-common-2.6.2.jar", "androidx.lifecycle:lifecycle-common:2.6.2"),
        (core_viewtree, "androidx.core:core-viewtree:1.0.0"),
        (ANDROIDX_ROOT / "kotlinx-coroutines-core-jvm-1.8.1.jar", "org.jetbrains.kotlinx:kotlinx-coroutines-core-jvm:1.8.1"),
    ]
    assets_json = json.loads((ASSET_DIR / "presentation/assets.json").read_text(encoding="utf-8"))
    expected = {row["coordinate"]: row["sha256"] for row in assets_json.get("engine_artifacts", [])}
    for artifact, coordinate in artifacts:
        if not artifact.is_file():
            raise FileNotFoundError(f"missing pinned Android runtime dependency: {artifact}")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digest != expected.get(coordinate):
            raise RuntimeError(f"runtime dependency hash mismatch for {artifact.name}: {digest}")

    classes_dir = work / "engine-classes"
    classes_dir.mkdir(parents=True, exist_ok=True)
    resource_dirs = []
    extracted_jars = [
        GDX_ROOT / "gdx-1.14.2.jar",
        GDX_ROOT / "gdx-jnigen-loader-2.5.2.jar",
        ANDROIDX_ROOT / "collection-jvm-1.4.2.jar",
        ANDROIDX_ROOT / "kotlin-stdlib-2.0.21.jar",
        ANDROIDX_ROOT / "lifecycle-common-2.6.2.jar",
        ANDROIDX_ROOT / "kotlinx-coroutines-core-jvm-1.8.1.jar",
    ]
    for aar in (backend_aar, androidx_core, versionedparcelable, lifecycle_runtime, core_viewtree):
        with zipfile.ZipFile(aar) as archive:
            stem = aar.stem
            classes_jar = classes_dir / f"{stem}-classes.jar"
            raw_classes = archive.read("classes.jar")
            if aar == backend_aar:
                # The backend ships an optional Fragment-host activity. This app
                # uses AndroidApplication (a normal Activity), so exclude that
                # unused class family and avoid bundling a large Fragment stack.
                source_classes = io.BytesIO(raw_classes)
                with zipfile.ZipFile(source_classes) as source, zipfile.ZipFile(classes_jar, "w", zipfile.ZIP_DEFLATED) as filtered:
                    for member in source.infolist():
                        if member.filename.startswith("com/badlogic/gdx/backends/android/AndroidFragmentApplication"):
                            continue
                        filtered.writestr(member, source.read(member.filename))
            else:
                classes_jar.write_bytes(raw_classes)
            extracted_jars.append(classes_jar)
            res_root = work / "aar-res" / stem
            res_root.mkdir(parents=True, exist_ok=True)
            for member in archive.namelist():
                if member.startswith("res/") and not member.endswith("/"):
                    target = res_root / member[4:]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(member))
            resource_dirs.append(res_root)

    native_jars = {
        "arm64-v8a": GDX_ROOT / "gdx-platform-1.14.2-natives-arm64-v8a.jar",
        "x86_64": GDX_ROOT / "gdx-platform-1.14.2-natives-x86_64.jar",
    }
    for abi, native_jar in native_jars.items():
        native_dir = work / "lib" / abi
        native_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(native_jar) as archive:
            native = archive.read("libgdx.so")
        native_path = native_dir / "libgdx.so"
        native_path.write_bytes(native)
        with open(native_path, "rb") as stream:
            if stream.read(4) != b"\x7fELF":
                raise RuntimeError(f"GDX native is not ELF for {abi}")
        expected_machine = {"arm64-v8a": 183, "x86_64": 62}[abi]
        machine = int.from_bytes(native_path.read_bytes()[18:20], "little")
        if machine != expected_machine:
            raise RuntimeError(f"wrong GDX ELF machine for {abi}: {machine}")
        native_jars[abi] = native_path
    return extracted_jars, native_jars, resource_dirs


def build_rust_archives(bin_dir: Path, cargo: str | None, force: bool = False) -> dict[str, Path]:
    archives = {}
    source_files = list((BRIDGE_ROOT / "src").rglob("*.rs"))
    source_files.extend((ROOT / "reconstruction/yarn-runtime/src").rglob("*.rs"))
    source_files += [
        BRIDGE_ROOT / "Cargo.toml", BRIDGE_ROOT / "Cargo.lock",
        ROOT / "reconstruction/yarn-runtime/Cargo.toml",
        ROOT / "reconstruction/yarn-runtime/Cargo.lock",
    ]
    for abi, target in ABIS.items():
        archive = BRIDGE_ROOT / "target" / target / "release/libninah_yarn_bridge.a"
        stale = not archive.is_file() or any(
            source.stat().st_mtime > archive.stat().st_mtime
            for source in source_files if source.is_file()
        )
        if stale or force:
            if not cargo:
                raise RuntimeError(
                    f"Rust bridge for {abi} is absent or stale and Cargo is unavailable; "
                    "install Cargo or restore the matching release static library"
                )
            env = os.environ.copy()
            env.setdefault("RUSTUP_HOME", str(ROOT / "tools/rustup"))
            env.setdefault("CARGO_HOME", str(ROOT / "tools/cargo"))
            linker = bin_dir / f"{target}23-clang"
            env[f"CARGO_TARGET_{target.upper().replace('-', '_')}_LINKER"] = str(linker)
            cargo_dir = Path(cargo).resolve().parent
            if (cargo_dir / "rustc").is_file():
                env["RUSTC"] = str(cargo_dir / "rustc")
                env["PATH"] = str(cargo_dir) + os.pathsep + env.get("PATH", "")
            run([
                cargo, "build", "--locked", "--release", "--manifest-path",
                BRIDGE_MANIFEST, "--target", target,
            ], cwd=ROOT, env=env)
        if not archive.is_file():
            raise FileNotFoundError(f"Rust bridge archive not found: {archive}")
        archives[abi] = archive
    return archives


def compile_native(bin_dir: Path, archives: dict[str, Path], work: Path) -> tuple[dict[str, Path], list[str]]:
    sources = sorted((NATIVE_ROOT / "src").glob("*.cpp"))
    jni_source = ANDROID_ROOT / "native/current_game.cpp"
    if not jni_source.is_file():
        raise FileNotFoundError(f"JNI entry point is not ready: {jni_source}")
    sources.append(jni_source)
    include_dirs = [
        NATIVE_ROOT / "include",
        NATIVE_ROOT / "generated",
    ]
    output = {}
    for abi, target in ABIS.items():
        compiler = bin_dir / f"{target}{MIN_API}-clang++"
        so_dir = work / "lib" / abi
        so_dir.mkdir(parents=True, exist_ok=True)
        library = so_dir / "libninah_current.so"
        command = [
            compiler, "-shared", "-std=c++17", "-O2", "-fPIC", "-fvisibility=hidden",
            "-Wall", "-Wextra", "-Werror", "-pedantic",
            "-static-libstdc++", "-Wl,--no-undefined", "-Wl,--build-id=sha1",
            "-Wl,-z,max-page-size=16384", "-Wl,-z,relro", "-Wl,-z,now",
            "-Wl,-z,noexecstack",
            "-Wl,-soname,libninah_current.so",
        ]
        for include in include_dirs:
            command.extend(["-I", include])
        command.extend(map(str, sources))
        command.extend([
            str(archives[abi]), "-ldl", "-lm", "-llog", "-o", str(library),
        ])
        run(command, cwd=ROOT)
        nm = bin_dir / "llvm-nm"
        symbols = run([nm, "-D", "--defined-only", library], capture=True)
        required_symbols = {
            "Java_org_reconstruction_current_MainActivity_nativeCreate",
            "Java_org_reconstruction_current_MainActivity_nativeAction",
        }
        missing_symbols = sorted(symbol for symbol in required_symbols if symbol not in symbols)
        if missing_symbols:
            raise RuntimeError(f"JNI exports missing from {abi} library: {missing_symbols}")
        output[abi] = library
    return output, [path.name for path in sources]


def compile_resources(build_tools: Path, android_jar: Path, work: Path,
                      aar_resource_dirs: list[Path]) -> tuple[Path, Path]:
    resource_dirs = [ANDROID_APP / "res", *aar_resource_dirs]
    compiled_resources = []
    for index, resource_dir in enumerate(resource_dirs):
        if not resource_dir.is_dir():
            continue
        output = work / f"resources-{index}.zip"
        run([build_tools / "aapt2", "compile", "--dir", resource_dir,
             "-o", output], cwd=ROOT)
        compiled_resources.append(output)

    base_apk = work / "base.apk"
    gen_dir = work / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    manifest = work / "AndroidManifest.xml"
    manifest_root = ET.parse(ANDROID_APP / "AndroidManifest.xml").getroot()
    manifest_root.set("package", PACKAGE_NAME)
    activity_name = f"{{{ANDROID_NS}}}name"
    activities = manifest_root.findall("application/activity")
    if len(activities) != 1:
        raise RuntimeError(f"expected one Android activity, found {len(activities)}")
    activities[0].set(activity_name, JNI_ACTIVITY)
    # AndroidApplication needs an OpenGL ES 2.0-capable device.
    gl_key = f"{{{ANDROID_NS}}}glEsVersion"
    has_gles = any(node.attrib.get(gl_key) == "0x00020000" for node in manifest_root.findall("uses-feature"))
    if not has_gles:
        feature = ET.SubElement(manifest_root, "uses-feature")
        feature.set(gl_key, "0x00020000")
        feature.set(f"{{{ANDROID_NS}}}required", "true")
    ET.register_namespace("android", ANDROID_NS)
    ET.ElementTree(manifest_root).write(manifest, encoding="utf-8", xml_declaration=True)

    command = [
        build_tools / "aapt2", "link", "-o", base_apk,
        "--manifest", manifest,
        "-I", android_jar, "-A", ASSET_DIR,
        "--java", gen_dir,
        "--output-text-symbols", work / "symbols",
        "--extra-packages", "com.badlogic.gdx.backends.android:androidx.core:androidx.versionedparcelable:androidx.lifecycle:androidx.core.viewtree",
        "--min-sdk-version", MIN_API,
        "--target-sdk-version", ANDROID_API,
        "--version-code", "2", "--version-name", "0.2-port-3d",
        "--rename-manifest-package", PACKAGE_NAME,
        "--auto-add-overlay", "-0", "mp4",
    ]
    for resource in compiled_resources:
        command.extend(["-R", resource])
    run(command, cwd=ROOT)
    return base_apk, gen_dir


def compile_java(build_tools: Path, android_jar: Path, work: Path,
                 generated_sources: Path, engine_jars: list[Path]) -> tuple[Path, Path, list[str]]:
    java_files = sorted((ANDROID_APP / "java").rglob("*.java"))
    if not any(path.name == "RoomEngine.java" for path in java_files):
        raise FileNotFoundError("RoomEngine.java is required in the final libGDX APK")
    java_files.extend(sorted(generated_sources.rglob("*.java")))
    if not java_files:
        raise FileNotFoundError("No Java sources found under app/src/main/java")
    classes = work / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    javac = os.environ.get("JAVAC") or shutil.which("javac")
    using_ecj = False
    if not javac:
        local_ecj = ROOT / "tools/android-current/java/javac"
        if local_ecj.is_file():
            javac = str(local_ecj)
            using_ecj = True
    elif Path(javac).resolve() == (ROOT / "tools/android-current/java/javac").resolve():
        using_ecj = True
    if using_ecj:
        ensure_local_ecj()
        # ECJ resolves Java 17 core classes from the host runtime. Keep Android
        # framework APIs on its class path, but strip Android's java.* stubs so
        # ECJ does not see duplicate java.base types (and can resolve lambdas).
        filtered_android = work / "android-api-classpath.jar"
        with zipfile.ZipFile(android_jar) as source, zipfile.ZipFile(filtered_android, "w", zipfile.ZIP_DEFLATED) as filtered:
            for member in source.infolist():
                if not member.filename.startswith("java/"):
                    filtered.writestr(member, source.read(member.filename))
        classpath_jars = [filtered_android, *engine_jars]
    else:
        classpath_jars = [android_jar, *engine_jars]
    classpath = os.pathsep.join(map(str, classpath_jars))
    if javac:
        compiler_options = ["-source", "17", "-target", "17"]
        run([javac, *compiler_options, "-classpath", classpath, "-d", classes, *java_files], cwd=ROOT)
    else:
        raise FileNotFoundError("a Java 17 compiler (javac or the pinned Eclipse ECJ wrapper) is required")
    classes_jar = work / "classes.jar"
    with zipfile.ZipFile(classes_jar, "w", compression=zipfile.ZIP_DEFLATED) as jar:
        for file in classes.rglob("*.class"):
            jar.write(file, file.relative_to(classes).as_posix())
    dex_dir = work / "dex"
    dex_dir.mkdir()
    run([build_tools / "d8", "--min-api", MIN_API, "--lib", android_jar,
         "--output", dex_dir, classes_jar, *engine_jars], cwd=ROOT)
    dex = dex_dir / "classes.dex"
    if not dex.is_file():
        raise FileNotFoundError("D8 completed without producing classes.dex")
    jdeps = shutil.which("jdeps")
    unresolved = []
    if jdeps:
        check = run([jdeps, "--multi-release", "base", "--missing-deps",
                     "--class-path", classpath, classes_jar], cwd=ROOT, capture=True)
        unresolved = [line for line in check.splitlines() if "not found" in line]
        if unresolved:
            raise RuntimeError("unresolved direct Android runtime dependencies:\n" + "\n".join(unresolved))
    return dex, classes_jar, unresolved


def package_apk(build_tools: Path, base_apk: Path,
                native_libs: dict[str, Path], gdx_native_libs: dict[str, Path],
                dex: Path, work: Path, output: Path) -> None:
    with zipfile.ZipFile(base_apk, "a", compression=zipfile.ZIP_DEFLATED) as apk:
        apk.write(dex, "classes.dex")
        for abi, library in native_libs.items():
            apk.write(library, f"lib/{abi}/libninah_current.so", compress_type=zipfile.ZIP_STORED)
        for abi, library in gdx_native_libs.items():
            apk.write(library, f"lib/{abi}/libgdx.so", compress_type=zipfile.ZIP_STORED)
    aligned = work / "aligned.apk"
    run([build_tools / "zipalign", "-f", "-P", "16", "4", base_apk, aligned], cwd=ROOT)
    keytool = os.environ.get("KEYTOOL") or shutil.which("keytool")
    if not keytool:
        raise FileNotFoundError("keytool is required to use the stable Port Inicio debug signing key")
    if not KEYSTORE.is_file():
        KEYSTORE.parent.mkdir(parents=True, exist_ok=True)
        run([
            keytool, "-genkeypair", "-storetype", "JKS", "-keystore", KEYSTORE,
            "-storepass", KEY_PASSWORD, "-keypass", KEY_PASSWORD, "-alias", KEY_ALIAS,
            "-dname", "CN=No I'm Not a Human Port Inicio Preview,O=Reconstruction,C=XX",
            "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000", "-noprompt",
        ], cwd=ROOT)
    output.parent.mkdir(parents=True, exist_ok=True)
    run([
        build_tools / "apksigner", "sign", "--ks", KEYSTORE,
        "--ks-key-alias", KEY_ALIAS, "--ks-pass", f"pass:{KEY_PASSWORD}",
        "--key-pass", f"pass:{KEY_PASSWORD}", "--out", output, aligned,
    ], cwd=ROOT)
    run([build_tools / "apksigner", "verify", "--verbose", output], cwd=ROOT)
    run([build_tools / "zipalign", "-c", "-P", "16", "-v", "4", output], cwd=ROOT)


def collect_report(output: Path, build_tools: Path, source_modules: list[str],
                   unresolved_dependencies: list[str]) -> dict:
    badging = run([build_tools / "aapt", "dump", "badging", output], capture=True)
    package_match = re.search(r"^package: name='([^']+)'", badging, re.MULTILINE)
    activity_match = re.search(r"^launchable-activity: name='([^']+)'", badging, re.MULTILINE)
    version_match = re.search(r"^package:.*versionCode='(\d+)'", badging, re.MULTILINE)
    package_name = package_match.group(1) if package_match else None
    launch_activity = activity_match.group(1) if activity_match else None
    manifest_root = ET.parse(ANDROID_APP / "AndroidManifest.xml").getroot()
    permissions = [element.attrib.get(f"{{{ANDROID_NS}}}name", "")
                   for element in manifest_root.findall("uses-permission")]
    with zipfile.ZipFile(output) as apk:
        bad_member = apk.testzip()
        if bad_member:
            raise RuntimeError(f"APK ZIP CRC check failed at {bad_member}")
        names = apk.namelist()
        libraries = sorted(name for name in names if re.fullmatch(
            r"lib/[^/]+/(?:libninah_current|libgdx)\.so", name))
        staged_pngs = [name for name in names if name.startswith("assets/sprites/") and name.endswith(".png")]
        menu_pngs = [name for name in names if name.startswith("assets/menu/") and name.endswith(".png")]
        required_assets = [
            "assets/narrative/program.json", "assets/narrative/line_metadata.json",
            "assets/narrative/texts_ptbr.json", "assets/presentation/assets.json",
            "assets/intro/Intro_Final_2_NO_SUBTITLES.mp4", "assets/menu/mainMenu_bg.png",
            "assets/presentation/ui/ui_manifest.json", "assets/world/world_manifest.json",
            "assets/licenses/THIRD_PARTY_NOTICES.txt",
            "assets/licenses/nlohmann-json-LICENSE-MIT.txt",
            "assets/licenses/apache-2.0-LICENSE.txt",
        ]
        missing = [name for name in required_assets if name not in names]
        if missing:
            raise RuntimeError(f"APK is missing required assets: {missing}")
        expected_libraries = {f"lib/{abi}/{lib}.so" for abi in ABIS for lib in ("libninah_current", "libgdx")}
        if set(libraries) != expected_libraries:
            raise RuntimeError(f"APK ABI libraries are incomplete: {libraries}")
        if len(staged_pngs) != 1210:
            raise RuntimeError(f"expected 1210 staged image assets, found {len(staged_pngs)}")
        if len(menu_pngs) != 15:
            raise RuntimeError(f"expected 14 recovered menu images plus the native background alias, found {len(menu_pngs)}")
        world_manifest = json.loads(apk.read("assets/world/world_manifest.json"))
        world_meshes = world_manifest.get("meshes", [])
        world_textures = world_manifest.get("textures", [])
        if len(world_meshes) != 100 or len(world_textures) != 42:
            raise RuntimeError(f"world assets incomplete: {len(world_meshes)} meshes, {len(world_textures)} textures")
        world_texture_bytes = 0
        for row in world_meshes:
            asset = row.get("android_asset")
            if not asset or f"assets/{asset}" not in names:
                raise RuntimeError(f"APK missing world mesh asset: {asset}")
        for row in world_textures:
            asset = row.get("android_asset")
            if not asset or f"assets/{asset}" not in names:
                raise RuntimeError(f"APK missing world texture asset: {asset}")
            image = Image.open(io.BytesIO(apk.read(f"assets/{asset}")))
            if max(image.size) > 1024:
                raise RuntimeError(f"Android world texture exceeds 1024px: {asset} ({image.size})")
            world_texture_bytes += apk.getinfo(f"assets/{asset}").file_size
        if world_texture_bytes > 64 * 1024 * 1024:
            raise RuntimeError(f"APK world texture budget exceeds 64 MiB: {world_texture_bytes}")
        ui_manifest = json.loads(apk.read("assets/presentation/ui/ui_manifest.json"))
        ui_sprite_table = ui_manifest.get("sprites", ui_manifest.get("images", []))
        ui_sprites = list(ui_sprite_table.values()) if isinstance(ui_sprite_table, dict) else ui_sprite_table
        ui_fonts = ui_manifest.get("fonts", [])
        if len(ui_sprites) != 119 or len(ui_fonts) != 5:
            raise RuntimeError(f"original game UI incomplete: {len(ui_sprites)} sprites, {len(ui_fonts)} fonts")
        for row in ui_sprites:
            asset = row.get("android_asset", row.get("asset"))
            if not asset or f"assets/{asset}" not in names:
                raise RuntimeError(f"APK missing original UI asset: {asset}")
        for row in ui_fonts:
            font = row.get("embedded_ttf") or row
            asset = font.get("android_asset", font.get("asset"))
            if not asset or f"assets/{asset}" not in names:
                raise RuntimeError(f"APK missing original UI font: {asset}")
            atlas = row.get("atlas") or {}
            atlas_asset = atlas.get("android_asset", atlas.get("path"))
            if atlas_asset and f"assets/{atlas_asset}" not in names:
                raise RuntimeError(f"APK missing original UI font atlas: {atlas_asset}")
        license_members = sorted(name for name in names if name.startswith("assets/licenses/") and not name.endswith("/"))
        if len(license_members) < 3:
            raise RuntimeError(f"expected bundled third-party notices and licenses, found {license_members}")
        if "classes.dex" not in names:
            raise RuntimeError("APK does not contain classes.dex")
        forbidden_extensions = {".exe", ".dll", ".rne", ".msi"}
        forbidden_paths = sorted(name for name in names if Path(name).suffix.lower() in forbidden_extensions)
        mz_members = []
        for name in names:
            with apk.open(name) as member:
                if member.read(2) == b"MZ":
                    mz_members.append(name)
        if forbidden_paths or mz_members:
            raise RuntimeError(f"APK contains Windows executable material: extensions={forbidden_paths}, MZ={mz_members}")
        elf_machines, load_alignments, zip_alignments = {}, {}, {}
        expected_machines = {"arm64-v8a": 183, "x86_64": 62}
        for abi, expected_machine in expected_machines.items():
            for lib in ("libninah_current", "libgdx"):
                member_name = f"lib/{abi}/{lib}.so"
                binary = apk.read(member_name)
                if binary[:4] != b"\x7fELF":
                    raise RuntimeError(f"native library is not ELF: {member_name}")
                machine = int.from_bytes(binary[18:20], byteorder="little")
                if machine != expected_machine:
                    raise RuntimeError(f"wrong ELF machine for {member_name}: {machine}, expected {expected_machine}")
                elf_machines[f"{abi}/{lib}"] = machine
                phoff = int.from_bytes(binary[32:40], "little")
                phentsize = int.from_bytes(binary[54:56], "little")
                phnum = int.from_bytes(binary[56:58], "little")
                aligns = [int.from_bytes(binary[phoff + i * phentsize + 48:phoff + i * phentsize + 56], "little")
                          for i in range(phnum) if int.from_bytes(binary[phoff + i * phentsize:phoff + i * phentsize + 4], "little") == 1]
                load_alignments[f"{abi}/{lib}"] = max(aligns, default=0)
                info = apk.getinfo(member_name)
                with output.open("rb") as stream:
                    stream.seek(info.header_offset)
                    local_header = stream.read(30)
                name_length = int.from_bytes(local_header[26:28], "little")
                extra_length = int.from_bytes(local_header[28:30], "little")
                offset = info.header_offset + 30 + name_length + extra_length
                zip_alignments[member_name] = offset % 16384
                if offset % 16384:
                    raise RuntimeError(f"native library ZIP data is not 16 KB aligned: {member_name}")
        intro_member = "assets/intro/Intro_Final_2_NO_SUBTITLES.mp4"
        intro_info = apk.getinfo(intro_member)
        intro_bytes = apk.read(intro_member)
        intro_hash = hashlib.sha256(intro_bytes).hexdigest()
        if intro_info.compress_type != zipfile.ZIP_STORED or intro_hash != INTRO_SHA256:
            raise RuntimeError("intro video ZIP storage or source hash validation failed")
        apk_size = output.stat().st_size
    if package_name != PACKAGE_NAME:
        raise RuntimeError(f"unexpected Android package name: {package_name!r}")
    if launch_activity != JNI_ACTIVITY:
        raise RuntimeError(f"unexpected launch activity: {launch_activity!r}")
    if version_match is None or int(version_match.group(1)) != 2:
        raise RuntimeError(f"unexpected Android version code: {version_match.group(1) if version_match else None}")
    hasher = hashlib.sha256()
    with output.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    digest = hasher.hexdigest()
    assets_json = json.loads((ASSET_DIR / "presentation/assets.json").read_text(encoding="utf-8"))
    localization = json.loads((ASSET_DIR / "narrative/texts_ptbr.json").read_text(encoding="utf-8"))
    line_metadata = json.loads((ASSET_DIR / "narrative/line_metadata.json").read_text(encoding="utf-8"))["line_metadata"]
    missing_line_keys = sorted(set(line_metadata) - set(localization["texts"]))
    if missing_line_keys:
        raise RuntimeError(f"staged PT-BR localization misses {len(missing_line_keys)} Yarn IDs")
    expected_image_keys = set(assets_json["images"])
    if len(expected_image_keys) != 1210:
        raise RuntimeError(f"expected 1210 static presentation image mappings, found {len(expected_image_keys)}")
    return {
        "status": "built_and_verified",
        "artifact": str(output.relative_to(ROOT)) if output.is_relative_to(ROOT) else str(output),
        "sha256": digest, "bytes": apk_size, "zip_crc_check": "passed",
        "package_name": package_name, "launch_activity": launch_activity,
        "version_code": int(version_match.group(1)), "version_name": "0.2-port-3d",
        "min_sdk": int(MIN_API), "target_sdk": int(ANDROID_API),
        "abis": ["arm64-v8a", "x86_64"], "native_libraries": libraries,
        "elf_machines": elf_machines, "elf_load_segment_max_alignment_bytes": load_alignments,
        "native_zip_data_offset_mod_16384": zip_alignments,
        "unresolved_direct_android_dependencies": unresolved_dependencies,
        "intro_video": {"asset": intro_member, "bytes": len(intro_bytes), "sha256": intro_hash,
                        "zip_stored": intro_info.compress_type == zipfile.ZIP_STORED},
        "jni_exports": ["Java_org_reconstruction_current_MainActivity_nativeCreate",
                        "Java_org_reconstruction_current_MainActivity_nativeAction"],
        "native_game_cpp_modules": source_modules,
        "assets": {
            "png_count": len(staged_pngs), "menu_png_count_including_native_alias": len(menu_pngs),
            "character_sprite_texture_exports": 1200, "supplemental_scene_sprites": 10,
            "image_reference_mappings": len(assets_json["images"]),
            "exported_image_objects_mapped": len(expected_image_keys),
            "bundled_license_files": len(license_members),
            "room_backgrounds": len(assets_json["backgrounds"]),
            "room_character_layouts": len(assets_json["room_layout"]),
            "pt_br_localization_texts_by_line_key": len(localization["texts"]),
            "pt_br_localization_texts_by_numeric_id": len(localization["ids"]),
            "line_metadata_keys_validated": len(line_metadata),
            "standalone_audio_assets_included": False,
            "intro_video_original_audio_channels": assets_json["intro"]["audio_channel_count"],
            "world_meshes": len(world_meshes), "world_textures": len(world_textures),
            "world_texture_bytes": world_texture_bytes, "world_texture_max_edge": 1024,
            "original_game_ui_sprites": len(ui_sprites), "original_game_ui_fonts": len(ui_fonts),
        },
        "embedded_windows_executable_extensions": forbidden_paths,
        "embedded_mz_magic_entries": mz_members, "permissions": permissions,
        "original_game_or_native_library_executed": False,
        "full_campaign_implemented": False, "android_device_execution_tested": False,
        "notes": [
            "This preview opens the recovered intro and current reconstructed campaign renderer; it is not a complete campaign port.",
            "The intro MP4 retains its recovered stereo soundtrack; no standalone game audio is packaged.",
            "APK signing uses the stable local preview debug key for repeatable test installation.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_APK)
    parser.add_argument("--skip-assets", action="store_true", help="reuse an existing staged asset tree")
    parser.add_argument("--rebuild-rust", action="store_true", help="force locked release builds for both Rust targets")
    args = parser.parse_args()

    sdk = choose_sdk().resolve()
    build_tools = find_build_tools(sdk)
    android_jar = sdk / f"platforms/android-{ANDROID_API}/android.jar"
    if not android_jar.is_file():
        raise FileNotFoundError(f"Android platform {ANDROID_API} not found at {android_jar}")
    _, bin_dir = find_ndk()

    if not args.skip_assets:
        run([sys.executable, ROOT / "tools/android-current/prepare_assets.py"], cwd=ROOT)
    for path in (
        ASSET_DIR / "narrative/program.json",
        ASSET_DIR / "narrative/line_metadata.json",
        ASSET_DIR / "narrative/texts_ptbr.json",
        ASSET_DIR / "presentation/assets.json",
    ):
        if not path.is_file():
            raise FileNotFoundError(f"staged asset missing: {path}; rerun prepare_assets.py")

    cargo = cargo_path()
    work_root = ANDROID_ROOT / "build"
    work_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="apk-build-", dir=work_root) as temporary:
        work = Path(temporary)
        engine_jars, gdx_native_libs, aar_resource_dirs = engine_runtime_jars(work)
        base_apk, generated_sources = compile_resources(
            build_tools, android_jar, work, aar_resource_dirs,
        )
        archives = build_rust_archives(bin_dir, cargo, args.rebuild_rust)
        native_libs, source_modules = compile_native(bin_dir, archives, work)
        dex, _, unresolved_dependencies = compile_java(
            build_tools, android_jar, work, generated_sources, engine_jars,
        )
        output = args.output.resolve()
        package_apk(build_tools, base_apk, native_libs, gdx_native_libs,
                    dex, work, output)
        report = collect_report(output, build_tools, source_modules, unresolved_dependencies)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
