#!/usr/bin/env python3
"""Build and validate the current reconstructed Android test APK."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import urllib.parse
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
DEFAULT_APK = ROOT / "deliverables/NINAH-Port-Casa-v013.apk"
REPORT = ANDROID_ROOT / "port3d_validation_report.json"
PACKAGE_NAME = "org.reconstruction.port.preview"
JNI_ACTIVITY = "org.reconstruction.current.MainActivity"
KEYSTORE = ROOT / "tools/android-current/signing/port-debug.keystore"
SIGNING_CONFIG = KEYSTORE.with_name("signing.json")
EXPECTED_SIGNER_CERT_SHA256 = "f07ec9f06df46a41621203512a410bbbfce871a4300cb85a0bbe59461721176a"
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
GDX_SHADER_ROOT = "com/badlogic/gdx/graphics/g3d/"
REQUIRED_GDX_SHADERS = tuple(GDX_SHADER_ROOT + name for name in (
    "shaders/default.vertex.glsl", "shaders/default.fragment.glsl",
    "shaders/depth.vertex.glsl", "shaders/depth.fragment.glsl",
    "particles/particles.vertex.glsl", "particles/particles.fragment.glsl",
))


def run(command: list[str], *, cwd: Path | None = None, env=None, capture=False, label=None) -> str:
    print("+", label if label else " ".join(str(part) for part in command), flush=True)
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
    artifact_paths = {
        "com.badlogicgames.gdx:gdx:1.14.2": GDX_ROOT / "gdx-1.14.2.jar",
        "com.badlogicgames.gdx:gdx-backend-android:1.14.2": backend_aar,
        "com.badlogicgames.gdx:gdx-jnigen-loader:2.5.2": GDX_ROOT / "gdx-jnigen-loader-2.5.2.jar",
        "com.badlogicgames.gdx:gdx-platform:1.14.2:natives-arm64-v8a": GDX_ROOT / "gdx-platform-1.14.2-natives-arm64-v8a.jar",
        "com.badlogicgames.gdx:gdx-platform:1.14.2:natives-x86_64": GDX_ROOT / "gdx-platform-1.14.2-natives-x86_64.jar",
        "androidx.core:core:1.17.0": androidx_core,
        "androidx.collection:collection-jvm:1.4.2": ANDROIDX_ROOT / "collection-jvm-1.4.2.jar",
        "androidx.versionedparcelable:versionedparcelable:1.1.1": versionedparcelable,
        "org.jetbrains.kotlin:kotlin-stdlib:2.0.21": ANDROIDX_ROOT / "kotlin-stdlib-2.0.21.jar",
        "androidx.lifecycle:lifecycle-runtime:2.6.2": lifecycle_runtime,
        "androidx.lifecycle:lifecycle-common:2.6.2": ANDROIDX_ROOT / "lifecycle-common-2.6.2.jar",
        "androidx.core:core-viewtree:1.0.0": core_viewtree,
        "org.jetbrains.kotlinx:kotlinx-coroutines-core-jvm:1.8.1": ANDROIDX_ROOT / "kotlinx-coroutines-core-jvm-1.8.1.jar",
    }
    assets_json = json.loads((ASSET_DIR / "presentation/assets.json").read_text(encoding="utf-8"))
    expected = {row["coordinate"]: row["sha256"] for row in assets_json.get("engine_artifacts", [])}
    from prepare_assets import ENGINE_ARTIFACTS
    pinned = {row["coordinate"]: row for row in ENGINE_ARTIFACTS}
    for coordinate, artifact in artifact_paths.items():
        pin = pinned.get(coordinate)
        if not pin or expected.get(coordinate) != pin["sha256"]:
            raise RuntimeError(f"prepared assets do not match pinned dependency metadata: {coordinate}")
        if not artifact.is_file():
            if urllib.parse.urlparse(pin["url"]).hostname not in {"repo.maven.apache.org", "dl.google.com"}:
                raise RuntimeError(f"refusing untrusted dependency host for {coordinate}")
            artifact.parent.mkdir(parents=True, exist_ok=True)
            temporary = artifact.with_name(artifact.name + ".download")
            with urllib.request.urlopen(pin["url"], timeout=90) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
            downloaded_hash = hashlib.sha256(temporary.read_bytes()).hexdigest()
            if downloaded_hash != pin["sha256"]:
                temporary.unlink(missing_ok=True)
                raise RuntimeError(f"downloaded dependency hash mismatch for {coordinate}: {downloaded_hash}")
            temporary.replace(artifact)
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digest != pin["sha256"]:
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


def native_source_fingerprint() -> tuple[str, int]:
    """Stable digest for the exact C++/Rust source tree that built the reference APK."""
    candidates = []
    for directory in (
        NATIVE_ROOT / "src", NATIVE_ROOT / "include", NATIVE_ROOT / "generated",
        BRIDGE_ROOT / "src", ROOT / "reconstruction/yarn-runtime/src",
    ):
        if directory.exists():
            candidates.extend(path for path in directory.rglob("*")
                              if path.is_file() and path.suffix in {".cpp", ".hpp", ".h", ".rs"})
    candidates.extend((
        BRIDGE_ROOT / "Cargo.toml", BRIDGE_ROOT / "Cargo.lock",
        ROOT / "reconstruction/yarn-runtime/Cargo.toml",
        ROOT / "reconstruction/yarn-runtime/Cargo.lock",
        ANDROID_ROOT / "native/current_game.cpp",
    ))
    files = sorted({path for path in candidates if path.is_file()}, key=lambda path: path.relative_to(ROOT).as_posix())
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(ROOT).as_posix().encode("utf-8")
        contents = path.read_bytes()
        digest.update(relative + b"\0" + len(contents).to_bytes(8, "little") + contents)
    return digest.hexdigest(), len(files)


def reuse_reference_native(reference_apk: Path, work: Path) -> tuple[dict[str, Path], dict]:
    """Extract JNI libraries only from the exact v2 APK, while native inputs match its lock."""
    build_lock = json.loads((ROOT / "LATEST_BUILD.json").read_text(encoding="utf-8"))
    expected_apk_sha = build_lock.get("sha256")
    if not expected_apk_sha or not build_lock.get("native_source_tree_sha256"):
        raise RuntimeError("LATEST_BUILD.json lacks the reference APK and native source fingerprints")
    apk_digest = hashlib.sha256()
    with reference_apk.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            apk_digest.update(block)
    actual_apk_sha = apk_digest.hexdigest()
    if actual_apk_sha != expected_apk_sha:
        raise RuntimeError(f"reference APK SHA-256 mismatch: {actual_apk_sha}")
    current_source_sha, source_count = native_source_fingerprint()
    if current_source_sha != build_lock["native_source_tree_sha256"]:
        raise RuntimeError(
            "native C++/Rust sources differ from the reference APK baseline; refusing to reuse old JNI libraries"
        )
    result = {}
    metadata = {"reference_apk": str(reference_apk), "sha256": actual_apk_sha,
                "native_source_tree_sha256": current_source_sha,
                "native_source_file_count": source_count, "libraries": {}}
    machines = {"arm64-v8a": 183, "x86_64": 62}
    required_exports = (
        b"Java_org_reconstruction_current_MainActivity_nativeCreate",
        b"Java_org_reconstruction_current_MainActivity_nativeAction",
    )
    with zipfile.ZipFile(reference_apk) as apk:
        for abi, expected_machine in machines.items():
            member = f"lib/{abi}/libninah_current.so"
            try:
                binary = apk.read(member)
            except KeyError as error:
                raise RuntimeError(f"reference APK is missing {member}") from error
            if binary[:4] != b"\x7fELF":
                raise RuntimeError(f"reference JNI library is not ELF: {member}")
            machine = int.from_bytes(binary[18:20], "little")
            if machine != expected_machine:
                raise RuntimeError(f"wrong ELF machine in {member}: {machine}, expected {expected_machine}")
            phoff = int.from_bytes(binary[32:40], "little")
            phentsize = int.from_bytes(binary[54:56], "little")
            phnum = int.from_bytes(binary[56:58], "little")
            alignments = [
                int.from_bytes(binary[phoff + i * phentsize + 48:phoff + i * phentsize + 56], "little")
                for i in range(phnum)
                if int.from_bytes(binary[phoff + i * phentsize:phoff + i * phentsize + 4], "little") == 1
            ]
            max_alignment = max(alignments, default=0)
            if max_alignment < 16384:
                raise RuntimeError(f"reference JNI library is not 16KB-page aligned: {member}")
            missing_exports = [symbol.decode("ascii") for symbol in required_exports if symbol not in binary]
            if missing_exports:
                raise RuntimeError(f"reference library lacks required JNI exports ({member}): {missing_exports}")
            destination = work / "reference-native" / abi / "libninah_current.so"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(binary)
            result[abi] = destination
            metadata["libraries"][abi] = {"member": member, "bytes": len(binary),
                                          "elf_machine": machine,
                                          "max_load_segment_alignment_bytes": max_alignment}
    return result, metadata


def compile_resources(build_tools: Path, android_jar: Path, work: Path,
                      aar_resource_dirs: list[Path], version_code: int,
                      version_name: str) -> tuple[Path, Path]:
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

    assets_for_packaging=ASSET_DIR
    world_manifest=json.loads((ASSET_DIR / "world/world_manifest.json").read_text())
    if world_manifest.get("android_mesh_optimization"):
        assets_for_packaging=work / "packaged-assets"
        referenced_models={Path(row.get("android_asset", "")).name for row in world_manifest.get("meshes", [])
                           if row.get("android_asset", "").startswith("world/models/")}
        def omit_source_meshes(directory,names):
            if Path(directory)==ASSET_DIR / "world" and not referenced_models:return {"models"}
            if Path(directory)==ASSET_DIR / "world/models":return set(names)-referenced_models
            return set()
        def link_asset(source,target):
            try: os.link(source,target)
            except OSError: shutil.copyfile(source,target)
            return target
        shutil.copytree(ASSET_DIR,assets_for_packaging,copy_function=link_asset,ignore=omit_source_meshes)
    command = [
        build_tools / "aapt2", "link", "-o", base_apk,
        "--manifest", manifest,
        "-I", android_jar, "-A", assets_for_packaging,
        "--java", gen_dir,
        "--output-text-symbols", work / "symbols",
        "--extra-packages", "com.badlogic.gdx.backends.android:androidx.core:androidx.versionedparcelable:androidx.lifecycle:androidx.core.viewtree",
        "--min-sdk-version", MIN_API,
        "--target-sdk-version", ANDROID_API,
        "--version-code", str(version_code), "--version-name", version_name,
        "--rename-manifest-package", PACKAGE_NAME,
        "--auto-add-overlay", "-0", "mp4", "-0", "ogg", "-0", "wav", "-0", "mp3",
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


def gdx_java_resources(jars: list[Path]) -> dict[str, bytes]:
    """DEX contains classes only; preserve GDX's classpath shaders and font resources."""
    resources = {}
    for jar in jars:
        with zipfile.ZipFile(jar) as archive:
            for member in archive.infolist():
                name = member.filename
                if member.is_dir() or not name.startswith("com/badlogic/gdx/") or name.endswith(".class"):
                    continue
                if ".." in Path(name).parts:
                    raise RuntimeError(f"invalid Java resource path in {jar.name}: {name}")
                content = archive.read(member)
                if name in resources and resources[name] != content:
                    raise RuntimeError(f"conflicting GDX Java resource: {name}")
                resources[name] = content
    missing = sorted(set(REQUIRED_GDX_SHADERS) - resources.keys())
    if missing:
        raise RuntimeError(f"libGDX runtime jars miss required shader resources: {missing}")
    return resources


def validate_gdx_java_resources(apk: zipfile.ZipFile) -> list[dict]:
    """Validate the delivered ZIP bytes, not just resources on the compiler classpath."""
    expected = gdx_java_resources([GDX_ROOT / "gdx-1.14.2.jar"])
    result = []
    for name, content in sorted(expected.items()):
        if apk.namelist().count(name) != 1:
            raise RuntimeError(f"APK must contain one classpath resource: {name}")
        if apk.read(name) != content:
            raise RuntimeError(f"APK classpath resource differs from pinned GDX: {name}")
        result.append({"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    return result


def load_signing_configuration() -> dict:
    """Read the existing private key configuration; no credentials are in source or logs."""
    if not KEYSTORE.is_file() or not SIGNING_CONFIG.is_file():
        raise FileNotFoundError("Restore the stable private keystore and its signing.json before building")
    config=json.loads(SIGNING_CONFIG.read_text())
    for field in ("alias","store_password","key_password"):
        if not isinstance(config.get(field),str) or not config[field]:
            raise ValueError("Private signing configuration is incomplete")
    return config


def sign_apk(build_tools: Path, aligned: Path, output: Path) -> None:
    config=load_signing_configuration()
    signing_env=os.environ.copy()
    signing_env["NINAH_SIGN_STORE_PASSWORD"]=config["store_password"]
    signing_env["NINAH_SIGN_KEY_PASSWORD"]=config["key_password"]
    output.parent.mkdir(parents=True, exist_ok=True)
    run([
        build_tools / "apksigner", "sign", "--ks", KEYSTORE,
        "--ks-key-alias", config["alias"], "--ks-pass", "env:NINAH_SIGN_STORE_PASSWORD",
        "--key-pass", "env:NINAH_SIGN_KEY_PASSWORD", "--out", output, aligned,
    ], cwd=ROOT, env=signing_env, label="Sign APK with restored private configuration")
    verification=run([build_tools / "apksigner", "verify", "--verbose", "--print-certs", output], cwd=ROOT, capture=True)
    if "certificate SHA-256 digest: "+EXPECTED_SIGNER_CERT_SHA256 not in verification:
        raise RuntimeError("APK signer differs from the stable preview certificate")
    print("Stable APK signing certificate verified",flush=True)


def package_apk(build_tools: Path, base_apk: Path,
                native_libs: dict[str, Path], gdx_native_libs: dict[str, Path],
                dex: Path, work: Path, output: Path, engine_jars: list[Path]) -> None:
    unsigned=work/"unsigned.apk"
    # Keep aapt2's resource archive immutable. Repack into one closed ZIP rather
    # than appending a second central directory to the resource APK.
    with zipfile.ZipFile(base_apk) as resources,zipfile.ZipFile(unsigned,"w",compression=zipfile.ZIP_DEFLATED) as apk:
        if "AndroidManifest.xml" not in resources.namelist():
            raise RuntimeError("aapt2 resource archive is missing AndroidManifest.xml")
        for member in resources.infolist():
            apk.writestr(member,resources.read(member))
        for name, content in sorted(gdx_java_resources(engine_jars).items()):
            if name in apk.namelist():
                raise RuntimeError(f"base APK already contains Java resource: {name}")
            apk.writestr(name, content)
        apk.write(dex, "classes.dex")
        for abi, library in native_libs.items():
            apk.write(library, f"lib/{abi}/libninah_current.so", compress_type=zipfile.ZIP_STORED)
        for abi, library in gdx_native_libs.items():
            apk.write(library, f"lib/{abi}/libgdx.so", compress_type=zipfile.ZIP_STORED)
    aligned = work / "aligned.apk"
    for path in (unsigned,):
        with path.open("rb") as stream:os.fsync(stream.fileno())
        with zipfile.ZipFile(path) as archive:
            if "AndroidManifest.xml" not in archive.namelist() or archive.testzip() is not None:
                raise RuntimeError("Unsigned APK is incomplete or failed CRC validation")
    run([build_tools / "zipalign", "-f", "-P", "16", "4", unsigned, aligned], cwd=ROOT)
    with aligned.open("rb") as stream:os.fsync(stream.fileno())
    with zipfile.ZipFile(aligned) as archive:
        if "AndroidManifest.xml" not in archive.namelist() or archive.testzip() is not None:
            raise RuntimeError("Aligned APK is incomplete or failed CRC validation")
    signed=work/"signed.apk"
    sign_apk(build_tools,aligned,signed)
    with signed.open("rb") as stream:os.fsync(stream.fileno())
    output.parent.mkdir(parents=True,exist_ok=True)
    signed.replace(output)
    run([build_tools / "zipalign", "-c", "-P", "16", "-v", "4", output], cwd=ROOT)


def validate_png_bytes(data: bytes, label: str) -> tuple[int,int]:
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            return image.size
    except Exception as failure:
        raise RuntimeError(f"Invalid PNG data: {label}: {failure}") from failure


def validate_music_assets(apk: zipfile.ZipFile, version_code: int) -> list[dict]:
    manifest_path="assets/music_manifest.json"
    if manifest_path not in apk.namelist():
        if version_code>=5:
            raise RuntimeError("Music manifest is required for version 5+")
        return []
    manifest=json.loads(apk.read(manifest_path))
    if manifest.get("errors"):
        raise RuntimeError("Music export contains unresolved errors")
    tracks=manifest["tracks"]
    if not {"main_menu","night1","ambience_house"}.issubset({row["key"] for row in tracks}):
        raise RuntimeError("Opening music routes are incomplete")
    result=[]
    for row in tracks:
        relative=Path(row["asset"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise RuntimeError(f"Unsafe music asset path: {relative}")
        member="assets/"+relative.as_posix()
        data=apk.read(member)
        digest=hashlib.sha256(data).hexdigest()
        if not data.startswith(b"OggS") or digest!=row["ogg"]["sha256"]:
            raise RuntimeError(f"Music bytes do not match validated export: {member}")
        if apk.getinfo(member).compress_type!=zipfile.ZIP_STORED:
            raise RuntimeError(f"MediaPlayer openFd requires stored OGG: {member}")
        result.append({"key":row["key"],"asset":member,"bytes":len(data),"sha256":digest,
                       "duration_seconds":row["ogg"].get("duration_seconds")})
    return result


def collect_report(output: Path, build_tools: Path, source_modules: list[str],
                   unresolved_dependencies: list[str], version_code: int,
                   version_name: str, native_reuse: dict | None = None) -> dict:
    badging = run([build_tools / "aapt", "dump", "badging", output], capture=True)
    package_match = re.search(r"^package: name='([^']+)'", badging, re.MULTILINE)
    activity_match = re.search(r"^launchable-activity: name='([^']+)'", badging, re.MULTILINE)
    version_match = re.search(r"^package:.*versionCode='(\d+)'", badging, re.MULTILINE)
    package_name = package_match.group(1) if package_match else None
    launch_activity = activity_match.group(1) if activity_match else None
    manifest_root = ET.parse(ANDROID_APP / "AndroidManifest.xml").getroot()
    hardware_requested=manifest_root.find("application").get(f"{{{ANDROID_NS}}}hardwareAccelerated")=="true"
    if version_code>=7:
        manifest_dump=run([build_tools / "aapt", "dump", "xmltree", output, "AndroidManifest.xml"],capture=True)
        if not hardware_requested or not re.search(r"hardwareAccelerated.*0xffffffff",manifest_dump):
            raise RuntimeError("Version 7+ must request hardware accelerated Android UI")
    permissions = [element.attrib.get(f"{{{ANDROID_NS}}}name", "")
                   for element in manifest_root.findall("uses-permission")]
    with zipfile.ZipFile(output) as apk:
        bad_member = apk.testzip()
        if bad_member:
            raise RuntimeError(f"APK ZIP CRC check failed at {bad_member}")
        names = apk.namelist()
        temporary_assets=[name for name in names if ".pending." in name or ".stage-tmp" in name]
        if temporary_assets:
            raise RuntimeError(f"Unfinished staged assets in APK: {temporary_assets}")
        all_pngs=[name for name in names if name.lower().endswith(".png")]
        for name in all_pngs:
            validate_png_bytes(apk.read(name),name)
        music_tracks=validate_music_assets(apk,version_code)
        door_animation_count = 0
        room_layer_count = 0
        if version_code >= 8:
            animation = json.loads(apk.read("assets/animations/animation_manifest.json"))
            source_animation = json.loads((ROOT / "reconstruction/reverse-animations/animation_manifest.json").read_text())
            if animation != source_animation:
                raise RuntimeError("Packaged door animation data differs from the recovered source manifest")
            door_animation_count = len(animation.get("door_triggers", []))
            if door_animation_count != 6:
                raise RuntimeError("Missing recovered interior door animations")
        if version_code >= 9:
            presentation = json.loads(apk.read("assets/presentation/assets.json"))
            relative = presentation.get("room_layers_manifest", "")
            if relative != "presentation/room_layers.json":
                raise RuntimeError("Missing authored room-layer manifest")
            composition = json.loads(apk.read("assets/" + relative))
            staged = json.loads((ASSET_DIR / relative).read_text())
            if composition != staged or composition.get("schema_version") != 1:
                raise RuntimeError("Packaged room layers differ from staged source data")
            rooms = composition.get("rooms", [])
            if len(rooms) != 7 or {r.get("id") for r in rooms} != set(range(7)):
                raise RuntimeError("Expected all seven source room views")
            for room in rooms:
                layers = room.get("layers", [])
                if not layers:
                    raise RuntimeError("Authored room view has no static layers")
                for layer in layers:
                    if "assets/" + layer["asset"] not in names:
                        raise RuntimeError("Missing authored room sprite: " + layer["asset"])
                room_layer_count += len(layers)
            if version_code >= 10:
                bedroom = next(room for room in rooms if room["id"] == 6)
                bed = [layer for layer in bedroom["layers"] if layer.get("source_state_component") == 4801]
                if len(bed) != 1 or bed[0].get("condition") != "bed_visible" or bed[0].get("source_state_enum") != 0:
                    raise RuntimeError("Missing verified first-morning bed layer")
        java_resources = validate_gdx_java_resources(apk)
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
        if version_code >= 11:
            required_assets.append("assets/world/cat3d_manifest.json")
        if version_code >= 13:
            required_assets.extend(["assets/presentation/ui/tv_source_manifest.json",
                                    "assets/presentation/room_layers.json"])
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
        skinned_mesh_indices={row["mesh_index"] for row in world_manifest.get("skinned_renderers",[])
                              if isinstance(row.get("mesh_index"),int)}
        if any(index<0 or index>=len(world_meshes) for index in skinned_mesh_indices):
            raise RuntimeError("World skinned renderer references a missing mesh")
        if len(world_meshes)-len(skinned_mesh_indices) != 100 or len(world_textures) != 42:
            raise RuntimeError(f"world assets incomplete: {len(world_meshes)} meshes, {len(world_textures)} textures")
        if version_code>=13 and (len(world_manifest.get("skinned_renderers",[]))!=6 or len(skinned_mesh_indices)!=1):
            raise RuntimeError("Version 13+ requires all six source skinned-renderer records and the active source pose")
        world_texture_bytes = 0
        mesh_source_vertices=mesh_android_vertices=mesh_android_bytes=0
        for row in world_meshes:
            asset = row.get("android_asset")
            if not asset or f"assets/{asset}" not in names:
                raise RuntimeError(f"APK missing world mesh asset: {asset}")
            data=apk.read(f"assets/{asset}")
            expected=row.get("android_sha256",row.get("source_sha256",row.get("sha256")))
            if hashlib.sha256(data).hexdigest()!=expected:
                raise RuntimeError(f"World mesh hash mismatch: {asset}")
            vertices=row.get("android_vertex_count",row["vertex_count"])
            indices=row.get("android_index_count",row["index_count"])
            if len(data)!=vertices*32+indices*4:
                raise RuntimeError(f"World mesh buffer/count mismatch: {asset}")
            mesh_source_vertices+=row["vertex_count"];mesh_android_vertices+=vertices;mesh_android_bytes+=len(data)
        if version_code>=6:
            if not world_manifest.get("android_mesh_optimization"):
                raise RuntimeError("Version 6+ requires lossless mesh optimization")
            referenced_world_meshes={f"assets/{row['android_asset']}" for row in world_meshes}
            if any(name.startswith("assets/world/models/") and name not in referenced_world_meshes for name in names):
                raise RuntimeError("Unreferenced source meshes should not be packaged alongside optimized copies")
            if "assets/licenses/meshoptimizer-LICENSE-MIT.txt" not in names:
                raise RuntimeError("Meshoptimizer license missing")
        for row in world_textures:
            asset = row.get("android_asset")
            if not asset or f"assets/{asset}" not in names:
                raise RuntimeError(f"APK missing world texture asset: {asset}")
            data=apk.read(f"assets/{asset}")
            if hashlib.sha256(data).hexdigest()!=row["android_sha256"]:
                raise RuntimeError(f"Android world texture hash mismatch: {asset}")
            dimensions=validate_png_bytes(data,asset)
            if max(dimensions)>1024:
                raise RuntimeError(f"Android world texture exceeds 1024px: {asset} ({dimensions})")
            world_texture_bytes += apk.getinfo(f"assets/{asset}").file_size
        if world_texture_bytes > 64 * 1024 * 1024:
            raise RuntimeError(f"APK world texture budget exceeds 64 MiB: {world_texture_bytes}")
        cat_summary=None
        if version_code >= 11:
            cat_manifest=json.loads(apk.read("assets/world/cat3d_manifest.json"))
            cat_mesh=cat_manifest.get("mesh",{});cat_material=cat_manifest.get("material",{})
            visibility=cat_manifest.get("visibility",{})
            if visibility.get("scene_active_self") is not False or "debug preview only" not in visibility.get("purpose",""):
                raise RuntimeError("Cat 3D preview must remain debug-only and preserve its inactive source scene flag")
            if cat_mesh.get("vertex_count") != 1112 or cat_mesh.get("index_count") != 4557:
                raise RuntimeError("Unexpected source cat mesh vertex/index counts")
            mesh_asset=cat_mesh.get("android_asset")
            if not mesh_asset or f"assets/{mesh_asset}" not in names:
                raise RuntimeError(f"APK missing source cat 3D mesh: {mesh_asset}")
            mesh_data=apk.read(f"assets/{mesh_asset}")
            expected_mesh=cat_mesh.get("staged_sha256",cat_mesh.get("sha256"))
            if hashlib.sha256(mesh_data).hexdigest()!=expected_mesh:
                raise RuntimeError(f"Source cat 3D mesh hash mismatch: {mesh_asset}")
            expected_mesh_bytes=cat_mesh["vertex_count"]*32+cat_mesh["index_count"]*4
            if len(mesh_data)!=expected_mesh_bytes:
                raise RuntimeError(f"Source cat mesh byte/count mismatch: {len(mesh_data)} vs {expected_mesh_bytes}")
            floats=struct.unpack_from("<"+"f"*(cat_mesh["vertex_count"]*8),mesh_data)
            if not all(math.isfinite(value) for value in floats):
                raise RuntimeError("Source cat mesh contains a non-finite vertex or normal")
            indices=struct.unpack_from("<"+"I"*cat_mesh["index_count"],mesh_data,cat_mesh["vertex_count"]*32)
            if any(index>=cat_mesh["vertex_count"] for index in indices):
                raise RuntimeError("Source cat mesh index is outside the vertex buffer")
            texture_asset=cat_material.get("android_asset")
            if not texture_asset or f"assets/{texture_asset}" not in names:
                raise RuntimeError(f"APK missing source cat albedo texture: {texture_asset}")
            texture_data=apk.read(f"assets/{texture_asset}")
            expected_texture=cat_material.get("staged_sha256",cat_material.get("texture_sha256"))
            if hashlib.sha256(texture_data).hexdigest()!=expected_texture:
                raise RuntimeError(f"Source cat albedo hash mismatch: {texture_asset}")
            cat_texture_dimensions=validate_png_bytes(texture_data,texture_asset)
            if max(cat_texture_dimensions)>1024:
                raise RuntimeError(f"Source cat texture exceeds 1024px: {cat_texture_dimensions}")
            cat_summary={"vertices":cat_mesh["vertex_count"],"triangles":cat_mesh["triangle_count"],
                         "mesh_bytes":len(mesh_data),"texture_dimensions":cat_texture_dimensions,
                         "debug_only":True,"default_visible":False}
        ui_manifest = json.loads(apk.read("assets/presentation/ui/ui_manifest.json"))
        sign_summary=None
        if version_code>=12:
            sign_path="assets/presentation/ui/sign_layout.json"
            if sign_path not in names:raise RuntimeError("Source examination layout is missing")
            signs=json.loads(apk.read(sign_path))
            if signs.get("schema_version")!=1:raise RuntimeError("Unsupported source sign schema")
            expected={0:[4518,4760,4428],1:[4527,5178,4393],2:[4444,5094],3:[4600],4:[4536,4618],5:[4977,4469]}
            views={view["enum_value"]:view for view in signs.get("signs",[])}
            if set(views)!=set(expected):raise RuntimeError("Six original sign views are required")
            ui_by_id={item["path_id"]:item for item in ui_manifest["components"]}
            if not signs["view"]["text_container"].get("hide_during_sign"):
                raise RuntimeError("Original inspection must hide DialogContent")
            for kind,ids in expected.items():
                view=views[kind];layers=view["layers_back_to_front"]
                if [layer["image_id"] for layer in layers]!=ids:
                    raise RuntimeError("Original sign sibling order changed")
                if bool(view.get("hide_dialogue_text"))!=(kind==3):
                    raise RuntimeError("Photo-only dialogue text visibility changed")
                for layer in layers:
                    image=ui_by_id.get(layer["image_id"])
                    if not image or image.get("class")!="UnityEngine.UI.Image":
                        raise RuntimeError("Inspection layer has no original Image")
                    rect=image["rect_transform"]["screen_rect_1920x1080"]
                    if rect!=layer["screen_rect_1920x1080"]:
                        raise RuntimeError("Inspection image rectangle differs from source")
                    if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in rect) or min(rect[2:])<=0:
                        raise RuntimeError("Invalid original inspection rectangle")
                    if image["image"]["sprite_source"]!=layer["source_image"]:
                        raise RuntimeError("Inspection sprite PPtr differs from source")
                    if layer["role"]=="static" and f"assets/{image['asset']}" not in names:
                        raise RuntimeError("Original inspection frame is not packaged")
            if views[1]["layers_back_to_front"][1]["mask_image_id"]!=4527:
                raise RuntimeError("Original hands mask is missing")
            hand,photo=views[1]["movement"],views[3]["movement"]
            if hand["start_position"]!=[0,-400,0] or hand["ease_value"]!=2 or abs(hand["duration_seconds"]-2/3)>1e-5:
                raise RuntimeError("Recovered hands move data changed")
            if photo["start_position"]!=[0,-1100,0] or photo["ease_value"]!=9 or photo["duration_seconds"]!=1 or photo["before_delay_seconds"]!=2:
                raise RuntimeError("Recovered photo move data changed")
            sign_summary={"views":6,"source_image_layers":sum(map(len,expected.values())),"source_sibling_order":True,
                          "hands_mask_image":4527,"authored_content_moves":2,"eye_random_motion_implemented":False}
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
    if version_match is None or int(version_match.group(1)) != version_code:
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
        "version_code": int(version_match.group(1)), "version_name": version_name,
        "native_source_tree_sha256": native_source_fingerprint()[0],
        "native_source_fingerprint_inputs": native_source_fingerprint()[1],
        "min_sdk": int(MIN_API), "target_sdk": int(ANDROID_API),
        "android_ui_hardware_acceleration_requested":hardware_requested,
        "abis": ["arm64-v8a", "x86_64"], "native_libraries": libraries,
        "source_interior_door_animation_count": door_animation_count,
        "authored_room_layer_count": room_layer_count,
        "elf_machines": elf_machines, "elf_load_segment_max_alignment_bytes": load_alignments,
        "native_zip_data_offset_mod_16384": zip_alignments,
        "unresolved_direct_android_dependencies": unresolved_dependencies,
        "intro_video": {"asset": intro_member, "bytes": len(intro_bytes), "sha256": intro_hash,
                        "zip_stored": intro_info.compress_type == zipfile.ZIP_STORED},
        "jni_exports": ["Java_org_reconstruction_current_MainActivity_nativeCreate",
                        "Java_org_reconstruction_current_MainActivity_nativeAction"],
        "native_game_cpp_modules": source_modules,
        "gdx_java_classpath_resources": java_resources,
        "assets": {
            "source_sign_layouts":sign_summary,
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
            "standalone_audio_assets_included": bool(music_tracks),
            "fully_decoded_png_count": len(all_pngs),
            "music_tracks": music_tracks,
            "intro_video_original_audio_channels": assets_json["intro"]["audio_channel_count"],
            "world_meshes": len(world_meshes), "world_textures": len(world_textures),
            "world_source_vertices":mesh_source_vertices,"world_android_vertices":mesh_android_vertices,
            "world_android_mesh_bytes":mesh_android_bytes,"world_mesh_hashes_validated":len(world_meshes),
            "world_texture_bytes": world_texture_bytes, "world_texture_max_edge": 1024,
            "cat_3d_preview":cat_summary,
            "original_game_ui_sprites": len(ui_sprites), "original_game_ui_fonts": len(ui_fonts),
        },
        "embedded_windows_executable_extensions": forbidden_paths,
        "embedded_mz_magic_entries": mz_members, "permissions": permissions,
        "original_game_or_native_library_executed": False,
        "full_campaign_implemented": False, "android_device_execution_tested": False,
        "reused_native_from_apk": native_reuse,
        "notes": [
            "This preview opens the recovered intro and current reconstructed campaign renderer; it is not a complete campaign port.",
            "The intro MP4 retains its soundtrack; original source music is packaged separately when listed in assets.music_tracks.",
            "APK signing uses the stable local preview debug key for repeatable test installation.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_APK)
    parser.add_argument("--skip-assets", action="store_true", help="reuse an existing staged asset tree")
    parser.add_argument("--reference-apk", type=Path,
                        help="reuse JNI libraries only from the exact hash-locked current APK")
    parser.add_argument("--version-code", type=int, default=13)
    parser.add_argument("--version-name", default="0.13-house-fidelity")
    parser.add_argument("--rebuild-rust", action="store_true", help="force locked release builds for both Rust targets")
    args = parser.parse_args()

    if args.version_code < 1:
        parser.error("--version-code must be positive")
    load_signing_configuration()

    sdk = choose_sdk().resolve()
    build_tools = find_build_tools(sdk)
    android_jar = sdk / f"platforms/android-{ANDROID_API}/android.jar"
    if not android_jar.is_file():
        raise FileNotFoundError(f"Android platform {ANDROID_API} not found at {android_jar}")
    bin_dir = None if args.reference_apk else find_ndk()[1]

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
    source_fingerprint_before = native_source_fingerprint()
    work_root = ANDROID_ROOT / "build"
    work_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="apk-build-", dir=work_root) as temporary:
        work = Path(temporary)
        engine_jars, gdx_native_libs, aar_resource_dirs = engine_runtime_jars(work)
        base_apk, generated_sources = compile_resources(
            build_tools, android_jar, work, aar_resource_dirs,
            args.version_code, args.version_name,
        )
        # Validate Android Java before invoking both native cross-compilers.
        dex, _, unresolved_dependencies = compile_java(
            build_tools, android_jar, work, generated_sources, engine_jars,
        )
        native_reuse = None
        if args.reference_apk:
            native_libs, native_reuse = reuse_reference_native(
                args.reference_apk.resolve(), work,
            )
            source_modules = sorted(path.name for path in (NATIVE_ROOT / "src").glob("*.cpp"))
            source_modules.append("current_game.cpp")
        else:
            assert bin_dir is not None
            archives = build_rust_archives(bin_dir, cargo, args.rebuild_rust)
            native_libs, source_modules = compile_native(bin_dir, archives, work)
        if native_source_fingerprint() != source_fingerprint_before:
            raise RuntimeError("Native sources changed during compilation; refusing mixed inputs")
        output = args.output.resolve()
        package_apk(build_tools, base_apk, native_libs, gdx_native_libs,
                    dex, work, output, engine_jars)
        report = collect_report(output, build_tools, source_modules, unresolved_dependencies,
                                args.version_code, args.version_name, native_reuse)
        # Reopen the closed artifact after the report scans; never deliver a report
        # for bytes whose final ZIP/signature no longer validate.
        run([build_tools / "apksigner", "verify", "--verbose", output], cwd=ROOT)
        with zipfile.ZipFile(output) as final_apk:
            if final_apk.testzip() is not None:
                raise RuntimeError("final APK CRC verification failed")
        if hashlib.sha256(output.read_bytes()).hexdigest() != report["sha256"]:
            raise RuntimeError("APK changed during final validation")
    report_path = output.with_name(output.stem + "_validation_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
