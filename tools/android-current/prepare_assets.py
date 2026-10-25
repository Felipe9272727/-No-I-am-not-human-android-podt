#!/usr/bin/env python3
"""Stage the recovered, non-audio assets used by the current Android shell."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tomllib
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CHARACTER_EXPORTS = ROOT / "reconstruction/reverse-characters/exported_character_assets"
SCENE_EXPORTS = ROOT / "reconstruction/reverse-scenes/exported_scene_assets"
PROGRAM = ROOT / "reconstruction/narrative/program.json"
LINE_METADATA = ROOT / "reconstruction/reverse-localization/line_metadata.json"
PT_BR = ROOT / "reconstruction/assets/localization/portuguese_brazil_pt-br_.json"
SCENE_RENDER = ROOT / "reconstruction/reverse-scenes/scene_render_manifest.json"
INTRO_DIR = ROOT / "reconstruction/reverse-bootstrap/exported_intro"
INTRO_EVIDENCE = ROOT / "reconstruction/reverse-bootstrap/intro_evidence.json"
MENU_DIR = ROOT / "reconstruction/reverse-bootstrap/exported_menu"
MENU_EVIDENCE = ROOT / "reconstruction/reverse-bootstrap/menu_evidence.json"
WORLD_SOURCE = ROOT / "reconstruction/reverse-world"
MUSIC_SOURCE = ROOT / "reconstruction/reverse-music"
UI_SOURCE = ROOT / "reconstruction/reverse-ui"
INTRO_NAME = "Intro_Final_2_NO_SUBTITLES.mp4"
INTRO_SHA256 = "67d32bc7e28e5bbb528c7553650d8c594138031f358e249ec011db559b54b9d2"
MENU_EXPORTS = {
    "house": (1616, "sharedassets0_1616_mainMenu_House.png"),
    "trioskaz_banner": (1692, "sharedassets0_1692_trioskaz_banner_main.png"),
    "button": (1769, "sharedassets0_1769_button_2.png"),
    "logo": (1863, "sharedassets0_1863_No_im_not_a_human_logo.png"),
    "peephole": (1986, "sharedassets0_1986_mainMenu_circle.png"),
    "collection_background": (2016, "sharedassets0_2016_Fake_collection_background.png"),
    "background": (2048, "sharedassets0_2048_mainMenu_bg.png"),
    "eyes": (2213, "sharedassets0_2213_mainmenu_eyes_0.png"),
    "wishlist_banner": (2228, "sharedassets0_2228_fake_wishlist_mainmenu_3.png"),
    "teeth": (2309, "sharedassets0_2309_mainmenu_teeth_11.png"),
    "mask_eyes": (2367, "sharedassets0_2367_mainmenu_mask_0.png"),
    "light_eyes": (1380, "sharedassets0_1380_mainmenu_light_0.png"),
    "mask_teeth": (1288, "sharedassets0_1288_mainmenu_mask_1.png"),
    "light_teeth": (2455, "sharedassets0_2455_mainmenu_light_1.png"),
}
DEFAULT_DESTINATION = ROOT / "reconstruction/android-current/app/src/main/assets"
LIBGDX_ROOT = ROOT / "tools/android-current/libgdx/1.14.2"
ANDROIDX_ROOT = ROOT / "tools/android-current/libgdx/androidx"

ROOM_IDS = {
    "Kitchen": 0,
    "Office": 1,
    "BigRoom": 2,
    "Bathroom": 3,
    "Pantry": 4,
    "Entrance": 5,
    "Bedroom": 6,
}

ENGINE_ARTIFACTS = [
    {
        "coordinate": "com.badlogicgames.gdx:gdx:1.14.2",
        "url": "https://repo.maven.apache.org/maven2/com/badlogicgames/gdx/gdx/1.14.2/gdx-1.14.2.jar",
        "sha256": "a835710bb135c2c687723b9474d5620f8158af90a96e07ce492f6169d7eee8cc",
        "type": "jar",
    },
    {
        "coordinate": "com.badlogicgames.gdx:gdx-backend-android:1.14.2",
        "url": "https://repo.maven.apache.org/maven2/com/badlogicgames/gdx/gdx-backend-android/1.14.2/gdx-backend-android-1.14.2.aar",
        "sha256": "a87d9cb6458580cc97c9e3c4ba45b7c09524315205999d3dadea6d1fac6eab1d",
        "type": "aar",
    },
    {
        "coordinate": "com.badlogicgames.gdx:gdx-jnigen-loader:2.5.2",
        "url": "https://repo.maven.apache.org/maven2/com/badlogicgames/gdx/gdx-jnigen-loader/2.5.2/gdx-jnigen-loader-2.5.2.jar",
        "sha256": "df81f23cfd6785c52d35e108eeaa3930f559d4d2770a6102e75ca7bfa6f9f27a",
        "type": "jar",
    },
    {
        "coordinate": "com.badlogicgames.gdx:gdx-platform:1.14.2:natives-arm64-v8a",
        "url": "https://repo.maven.apache.org/maven2/com/badlogicgames/gdx/gdx-platform/1.14.2/gdx-platform-1.14.2-natives-arm64-v8a.jar",
        "sha256": "222cabc63ba717d1f8937c4e2236eea48a6b5b66d98a40487f2065aea398dc5a",
        "type": "natives-jar",
    },
    {
        "coordinate": "com.badlogicgames.gdx:gdx-platform:1.14.2:natives-x86_64",
        "url": "https://repo.maven.apache.org/maven2/com/badlogicgames/gdx/gdx-platform/1.14.2/gdx-platform-1.14.2-natives-x86_64.jar",
        "sha256": "d8a573ef6350008ac44e1231d0499b848d64cf3b468f663189ad94f0d51fc3fe",
        "type": "natives-jar",
    },
    {
        "coordinate": "androidx.core:core:1.17.0",
        "url": "https://dl.google.com/dl/android/maven2/androidx/core/core/1.17.0/core-1.17.0.aar",
        "sha256": "e1bd22bbcf5cee3a992dedb7d2d3c3b31c9f761c01e56d00ea443c8aaa981182",
        "type": "aar",
    },
    {
        "coordinate": "androidx.collection:collection-jvm:1.4.2",
        "url": "https://dl.google.com/dl/android/maven2/androidx/collection/collection-jvm/1.4.2/collection-jvm-1.4.2.jar",
        "sha256": "984ce9bd780055eafb8a105aca3f514686bf7b1b6272ec7c645a98ce40fc7db4",
        "type": "jar",
    },
    {
        "coordinate": "androidx.versionedparcelable:versionedparcelable:1.1.1",
        "url": "https://dl.google.com/dl/android/maven2/androidx/versionedparcelable/versionedparcelable/1.1.1/versionedparcelable-1.1.1.aar",
        "sha256": "57e8d93260d18d5b9007c9eed3c64ad159de90c8609ebfc74a347cbd514535a4",
        "type": "aar",
    },
    {
        "coordinate": "org.jetbrains.kotlin:kotlin-stdlib:2.0.21",
        "url": "https://repo.maven.apache.org/maven2/org/jetbrains/kotlin/kotlin-stdlib/2.0.21/kotlin-stdlib-2.0.21.jar",
        "sha256": "f31cc53f105a7e48c093683bbd5437561d1233920513774b470805641bedbc09",
        "type": "jar",
    },
    {
        "coordinate": "androidx.lifecycle:lifecycle-runtime:2.6.2",
        "url": "https://dl.google.com/dl/android/maven2/androidx/lifecycle/lifecycle-runtime/2.6.2/lifecycle-runtime-2.6.2.aar",
        "sha256": "4867fd5279742fba8388821930cb2affe06d81a52814e7e41e70392ea0ef887c",
        "type": "aar",
    },
    {
        "coordinate": "androidx.lifecycle:lifecycle-common:2.6.2",
        "url": "https://dl.google.com/dl/android/maven2/androidx/lifecycle/lifecycle-common/2.6.2/lifecycle-common-2.6.2.jar",
        "sha256": "f34831b6c71cd844e1d35d1be49d5e79447c5ab856346531b1e8676fda7374b1",
        "type": "jar",
    },
    {
        "coordinate": "androidx.core:core-viewtree:1.0.0",
        "url": "https://dl.google.com/dl/android/maven2/androidx/core/core-viewtree/1.0.0/core-viewtree-1.0.0.aar",
        "sha256": "dc1b678d58ebcf2bfa1587be68ff826694ce3d221251b9ef30d4d4b36297e6de",
        "type": "aar",
    },
    {
        "coordinate": "org.jetbrains.kotlinx:kotlinx-coroutines-core-jvm:1.8.1",
        "url": "https://repo.maven.apache.org/maven2/org/jetbrains/kotlinx/kotlinx-coroutines-core-jvm/1.8.1/kotlinx-coroutines-core-jvm-1.8.1.jar",
        "sha256": "f3d4f5de1c391bbcc20f3b3435ccbac013521e76b6902d7d59635ec15c1f797e",
        "type": "jar",
    },
]


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def minified_json(source: Path, destination: Path, data=None) -> None:
    if data is None:
        data = read_json(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    temporary.replace(destination)


def safe_sprite_filename(source_file: str, path_id: int) -> str:
    # Keep names ASCII and unambiguous across sharedassets0/sharedassets1.
    stem = re.sub(r"[^A-Za-z0-9]+", "_", Path(source_file).stem).strip("_")
    if not stem:
        raise ValueError(f"cannot derive a sprite filename from {source_file!r}")
    return f"{stem}_{int(path_id)}.png"


def copy_export(export_root: Path, entry: dict, destination: Path) -> None:
    source = export_root / entry["output"]
    if not source.is_file():
        raise FileNotFoundError(f"missing exported image: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def stage_third_party_notices(destination: Path) -> dict:
    license_root = destination / "licenses"
    rust_root = license_root / "rust"
    rust_root.mkdir(parents=True, exist_ok=True)
    nlohmann_license = ROOT / "reconstruction/native-game/third_party/nlohmann/LICENSE.MIT"
    shutil.copyfile(nlohmann_license, license_root / "nlohmann-json-LICENSE-MIT.txt")
    apache_license = Path("/usr/share/common-licenses/Apache-2.0")
    if not apache_license.is_file():
        raise FileNotFoundError("official Apache-2.0 license text is not available on this build host")
    shutil.copyfile(apache_license, license_root / "apache-2.0-LICENSE.txt")

    android_x_notices = license_root / "androidx"
    android_x_notices.mkdir(parents=True, exist_ok=True)
    for artifact, member in (
        (ANDROIDX_ROOT / "core-1.17.0.aar", "META-INF/androidx/core/core/LICENSE.txt"),
    ):
        target = android_x_notices / f"{artifact.stem}-LICENSE.txt"
        with zipfile.ZipFile(artifact) as archive, archive.open(member) as source, target.open("wb") as output:
            shutil.copyfileobj(source, output)

    lock = tomllib.loads((ROOT / "reconstruction/native-game/bridge/Cargo.lock").read_text(encoding="utf-8"))
    registries = list((ROOT / "tools/cargo/registry/src").glob("*"))
    copied = []
    for package in lock.get("package", []):
        if not package.get("source", "").startswith("registry+"):
            continue
        name, version = package["name"], package["version"]
        package_dirs = [registry / f"{name}-{version}" for registry in registries]
        package_dir = next((candidate for candidate in package_dirs if candidate.is_dir()), None)
        if package_dir is None:
            continue  # Host-only procedural-macro crates are not linked into the APK.
        license_files = sorted(
            file for file in package_dir.iterdir()
            if file.is_file() and file.name.upper().startswith(("LICENSE", "COPYING"))
        )
        for source in license_files:
            target = rust_root / f"{name}-{version}-{source.name}.txt"
            shutil.copyfile(source, target)
        if license_files:
            copied.append({"crate": name, "version": version, "files": [f.name for f in license_files]})

    notice = [
        "Third-party notices for the Port Inicio Android preview APK.",
        "nlohmann/json is distributed under the MIT License; see nlohmann-json-LICENSE-MIT.txt.",
        "Rust crate notices below are copied from the matching local Cargo registry source packages.",
        "Only dependencies with locally retained license text are listed; host-only proc-macro crates are not linked into the APK.",
        "libGDX 1.14.2, AndroidX runtime components, Kotlin stdlib 2.0.21, and kotlinx-coroutines 1.8.1 are licensed under Apache License 2.0; see apache-2.0-LICENSE.txt and licenses/androidx/.",
        "",
    ]
    notice.extend(
        f"{entry['crate']} {entry['version']}: {', '.join(entry['files'])}"
        for entry in copied
    )
    (license_root / "THIRD_PARTY_NOTICES.txt").write_text("\n".join(notice) + "\n", encoding="utf-8")
    return {"nlohmann_notice": True, "rust_crate_license_copies": len(copied)}


def clean_owned_outputs(destination: Path) -> None:
    # These four generated outputs belong to this script. Other assets in the
    # app tree, if any, are preserved.
    for name in ("narrative", "presentation", "sprites", "licenses", "intro", "menu", "world", "ui", "music"):
        path = destination / name
        if path.exists():
            shutil.rmtree(path)
    (destination / "music_manifest.json").unlink(missing_ok=True)
    assets_json = destination / "assets.json"
    if assets_json.exists():
        assets_json.unlink()


def stage_music_assets(destination: Path) -> dict:
    source_manifest=MUSIC_SOURCE / "music_manifest.json"
    manifest=read_json(source_manifest)
    if manifest.get("errors"):
        raise RuntimeError("Music export contains errors")
    tracks=manifest["tracks"]
    if not {"main_menu","night1","ambience_house"}.issubset({row["key"] for row in tracks}):
        raise RuntimeError("Opening music export is incomplete")
    total=0
    for row in tracks:
        relative=Path(row["extracted_asset"])
        target_relative=Path(row["asset"])
        if any(path.is_absolute() or ".." in path.parts or not path.parts for path in (relative,target_relative)):
            raise RuntimeError("Unsafe music source or target path")
        source=MUSIC_SOURCE / relative
        if sha256_file(source)!=row["ogg"]["sha256"]:
            raise RuntimeError(f"Music source hash mismatch: {relative}")
        target=destination / target_relative
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_suffix(".ogg.stage-tmp")
        shutil.copyfile(source,temporary)
        temporary.replace(target)
        total+=target.stat().st_size
    minified_json(source_manifest,destination / "music_manifest.json",manifest)
    return {"manifest":"music_manifest.json","track_count":len(tracks),"bytes":total}


def stage_world_assets(destination: Path) -> dict:
    """Copy verified meshes and make deterministic <=1024px Android textures."""
    source_manifest = WORLD_SOURCE / "world_manifest.json"
    if not source_manifest.is_file():
        raise FileNotFoundError(f"world export is not ready: {source_manifest}")
    manifest = read_json(source_manifest)
    if manifest.get("errors"):
        raise RuntimeError(f"world export has errors: {manifest['errors'][:3]}")
    meshes = manifest.get("meshes", [])
    textures = manifest.get("textures", [])
    if len(meshes) != 100 or len(textures) != 42:
        raise RuntimeError(f"expected 100 world meshes and 42 textures, got {len(meshes)} and {len(textures)}")
    world_out = destination / "world"
    if world_out.exists():
        shutil.rmtree(world_out)
    world_out.mkdir(parents=True, exist_ok=True)
    mesh_bytes = 0
    for row in meshes:
        relative = Path(row.get("mesh_asset", row.get("asset", row.get("path", ""))))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise RuntimeError(f"unsafe world mesh path: {relative}")
        source = WORLD_SOURCE / relative
        digest = sha256_file(source)
        expected = row.get("sha256") or row.get("buffer_sha256")
        if expected and digest != expected:
            raise RuntimeError(f"world mesh hash mismatch: {relative}")
        target = world_out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        row["source_sha256"] = digest
        row["android_asset"] = f"world/{relative.as_posix()}"
        mesh_bytes += target.stat().st_size

    texture_bytes = 0
    for index, row in enumerate(textures):
        relative = Path(row.get("asset", row.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise RuntimeError(f"unsafe world texture path: {relative}")
        source = WORLD_SOURCE / relative
        digest = sha256_file(source)
        expected = row.get("sha256") or row.get("source_sha256")
        if expected and digest != expected:
            raise RuntimeError(f"world texture hash mismatch: {relative}")
        with Image.open(source) as original:
            original.load()
            source_size = list(original.size)
            image = original.copy()
        image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        target_relative = Path("textures_android") / f"{index:03d}_{relative.stem}.png"
        target = world_out / target_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary=target.with_suffix(".png.stage-tmp")
        image.save(temporary, format="PNG", optimize=False, compress_level=9)
        with Image.open(temporary) as check:
            check.verify()
        with Image.open(temporary) as check:
            check.load()
        temporary.replace(target)
        row.update({
            "source_asset": relative.as_posix(), "source_sha256": digest,
            "source_dimensions": source_size,
            "android_asset": f"world/{target_relative.as_posix()}",
            "android_sha256": sha256_file(target),
            "android_dimensions": list(image.size), "max_edge": 1024,
        })
        row["asset"] = f"world/{target_relative.as_posix()}"
        texture_bytes += target.stat().st_size
    if texture_bytes > 64 * 1024 * 1024:
        raise RuntimeError(f"Android texture variants exceed 64 MiB: {texture_bytes}")
    manifest["android_staging"] = {"max_texture_edge": 1024, "texture_bytes": texture_bytes,
                                   "mesh_bytes": mesh_bytes, "mesh_count": len(meshes),
                                   "texture_count": len(textures),
                                   "source_manifest_sha256": sha256_file(source_manifest)}
    minified_json(source_manifest, world_out / "world_manifest.json", manifest)
    return manifest["android_staging"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stage_ui_assets(destination: Path) -> dict:
    source_manifest = UI_SOURCE / "ui_manifest.json"
    if not source_manifest.is_file():
        raise FileNotFoundError(f"game UI export is not ready: {source_manifest}")
    manifest = read_json(source_manifest)
    image_table = manifest.get("sprites", manifest.get("images", []))
    image_rows = list(image_table.values()) if isinstance(image_table, dict) else image_table
    font_rows = manifest.get("fonts", [])
    if len(image_rows) != 119 or len(font_rows) != 5:
        raise RuntimeError(f"expected 119 original UI sprites and 5 fonts, got {len(image_rows)} and {len(font_rows)}")
    for row in image_rows:
        rel = Path(row.get("output", row.get("path", row.get("asset", ""))))
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            raise RuntimeError(f"unsafe UI image path: {rel}")
        source = UI_SOURCE / rel
        target_rel = Path("ui/exported_images") / source.name
        if not source.is_file():
            raise FileNotFoundError(source)
        expected = row.get("sha256") or row.get("exported_sha256")
        digest = sha256_file(source)
        if expected and digest != expected:
            raise RuntimeError(f"UI sprite hash mismatch: {source.name}")
        target = destination / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        row["asset"] = target_rel.as_posix()
        row["android_asset"] = target_rel.as_posix()
    for row in font_rows:
        embedded = row.get("embedded_ttf") or {}
        rel = Path(row.get("output", row.get("path", row.get("asset", embedded.get("path", "")))))
        source = UI_SOURCE / rel
        expected = row.get("sha256") or row.get("exported_sha256") or embedded.get("sha256")
        digest = sha256_file(source)
        if expected and digest != expected:
            raise RuntimeError(f"UI font hash mismatch: {source.name}")
        target_rel = Path("ui/exported_fonts") / source.name
        target = destination / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        embedded["asset"] = target_rel.as_posix()
        embedded["android_asset"] = target_rel.as_posix()
        atlas = row.get("atlas")
        if atlas and atlas.get("path"):
            atlas_rel = Path(atlas["path"])
            atlas_source = UI_SOURCE / atlas_rel
            atlas_target_rel = Path("ui/exported_fonts") / atlas_rel.name
            if not atlas_source.is_file():
                raise FileNotFoundError(atlas_source)
            if sha256_file(atlas_source) != atlas.get("sha256"):
                raise RuntimeError(f"UI font atlas hash mismatch: {atlas_source.name}")
            atlas_target = destination / atlas_target_rel
            atlas_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(atlas_source, atlas_target)
            atlas["source_export_path"] = atlas_rel.as_posix()
            atlas["path"] = atlas_target_rel.as_posix()
            atlas["android_asset"] = atlas_target_rel.as_posix()
    minified_json(source_manifest, destination / "presentation/ui/ui_manifest.json", manifest)
    return {"manifest": "presentation/ui/ui_manifest.json", "sprites": len(image_rows), "fonts": len(font_rows),
            "source_sha256": sha256_file(source_manifest)}


def prepare(destination: Path) -> dict:
    char_manifest = read_json(CHARACTER_EXPORTS / "manifest.json")
    scene_manifest = read_json(SCENE_EXPORTS / "manifest.json")
    if char_manifest.get("errors"):
        raise RuntimeError(f"character asset export has errors: {char_manifest['errors'][:3]}")
    if scene_manifest.get("errors"):
        raise RuntimeError(f"scene asset export has errors: {scene_manifest['errors'][:3]}")

    character_images = [
        row for row in char_manifest["exports"]
        if row.get("object_type") in {"Sprite", "Texture2D"}
    ]
    if len(character_images) != 1200:
        raise RuntimeError(f"expected 1200 character Sprite/Texture2D exports, got {len(character_images)}")
    if len(scene_manifest["exports"]) != 10:
        raise RuntimeError(f"expected 10 supplemental scene sprites, got {len(scene_manifest['exports'])}")

    render_manifest = read_json(SCENE_RENDER)
    room_canvas = next(
        (
            scaler for scaler in render_manifest.get("canvas_scalers", [])
            if scaler.get("game_object_name") == "RoomDisplayer"
        ),
        None,
    )
    if not room_canvas or room_canvas.get("reference_resolution") != [1920.0, 1080.0]:
        raise RuntimeError("RoomDisplayer reference resolution is not the expected 1920x1080")
    reference_width, reference_height = room_canvas["reference_resolution"]

    destination.mkdir(parents=True, exist_ok=True)
    clean_owned_outputs(destination)
    world_summary = stage_world_assets(destination)
    music_summary = stage_music_assets(destination)
    ui_summary = stage_ui_assets(destination)

    intro_evidence = read_json(INTRO_EVIDENCE)
    intro_record = intro_evidence["ending"]
    intro_clip = intro_record["video"]
    intro_source = INTRO_DIR / INTRO_NAME
    intro_sha256 = hashlib.sha256(intro_source.read_bytes()).hexdigest()
    if intro_sha256 != INTRO_SHA256 or intro_sha256 != intro_clip["payload_sha256"]:
        raise RuntimeError(f"intro MP4 SHA-256 mismatch: {intro_sha256}")
    if intro_source.stat().st_size != intro_clip["stream_size"]:
        raise RuntimeError("intro MP4 size does not match the recovered VideoClip metadata")
    intro_relative = f"intro/{INTRO_NAME}"
    (destination / intro_relative).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(intro_source, destination / intro_relative)

    menu_evidence = read_json(MENU_EVIDENCE)
    menu_manifest_by_id = {int(row["path_id"]): row for row in menu_evidence["menu_art"]}
    menu_images: dict[str, str] = {}
    menu_references = {}
    for role, (path_id, filename) in MENU_EXPORTS.items():
        source = MENU_DIR / filename
        art = menu_manifest_by_id.get(path_id)
        if art is None or not source.is_file():
            raise FileNotFoundError(f"missing recovered menu art {path_id}: {source}")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != art.get("exported_sha256"):
            raise RuntimeError(f"menu art SHA-256 mismatch for {filename}: {digest}")
        relative = f"menu/{filename}"
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        menu_images[role] = relative
        menu_references[role] = {
            "file_id": 2,
            "path_id": path_id,
            "name": art["name"],
            "width": art["width"],
            "height": art["height"],
            "sha256": digest,
        }
    # The current C++ preview state returns this exact path for its background.
    background_alias = destination / "menu/mainMenu_bg.png"
    shutil.copyfile(destination / menu_images["background"], background_alias)

    focus_names = {
        "Peephole", "House", "Logo", "Eyes", "Teeth", "EyesMask", "TeethMask",
        "Light", "CR", "Trioskaz", "NewGame", "Continue", "Settings", "Collection", "Quit",
    }
    scene_objects = [
        {
            "name": row.get("name"),
            "rect_transform": row.get("rect_transform"),
            "game_object_path_id": row.get("game_object_path_id"),
        }
        for row in menu_evidence.get("scene", {}).get("selected_serialized_objects", [])
        if row.get("name") in focus_names
    ]

    image_map: dict[str, str] = {}
    copied = 0
    for export_root, rows in (
        (CHARACTER_EXPORTS, character_images),
        (SCENE_EXPORTS, scene_manifest["exports"]),
    ):
        for row in rows:
            name = safe_sprite_filename(row["source_file"], row["path_id"])
            relative = f"sprites/{name}"
            key = f"{row['source_file']}:{row['path_id']}"
            existing = image_map.get(key)
            if existing and existing != relative:
                raise RuntimeError(f"conflicting image mapping for {key}: {existing}, {relative}")
            if not existing:
                copy_export(export_root, row, destination / relative)
                image_map[key] = relative
                copied += 1

    backgrounds = []
    for row in scene_manifest["exports"]:
        for role in row.get("roles", []):
            if not role.startswith("room_background:"):
                continue
            room_name = role.split(":", 1)[1]
            if room_name not in ROOM_IDS:
                raise RuntimeError(f"unknown ERoom background role: {room_name}")
            backgrounds.append({
                "room": ROOM_IDS[room_name],
                "name": room_name,
                "asset": f"sprites/{safe_sprite_filename(row['source_file'], row['path_id'])}",
            })
    backgrounds.sort(key=lambda row: row["room"])
    if len(backgrounds) != 7 or {row["name"] for row in backgrounds} != set(ROOM_IDS):
        raise RuntimeError(f"expected one background for each ERoom value, got {backgrounds}")

    room_layout: dict[str, dict] = {}
    room_layout_by_room: dict[str, dict] = {}
    for row in render_manifest.get("room_character_instances", []):
        room_name = row.get("room")
        if room_name not in ROOM_IDS:
            raise RuntimeError(f"unknown room in scene render manifest: {room_name!r}")
        transform = row.get("game_object", {}).get("transform")
        if not transform:
            raise RuntimeError(f"room character has no RectTransform: {row.get('character')}")
        anchored = transform["anchored_position"]
        size = transform["size_delta"]
        pivot = transform["pivot"]
        character_name = row["character"]["name"]
        if character_name in room_layout:
            raise RuntimeError(f"duplicate character name in scene layout: {character_name!r}")
        layout = {
            "room": room_name,
            "room_enum": ROOM_IDS[room_name],
            "size": [size["x"], size["y"]],
            "pivot": [pivot["x"], pivot["y"]],
            "order": int(row["order_in_room"]),
            "scene_order": int(row["order_in_room"]),
            "anchored_position": [anchored["x"], anchored["y"]],
            "normalized_layout": {
                # Unity's anchored position is the RectTransform pivot point;
                # y is flipped to top-left image coordinates for Android.
                "anchor_position": [
                    0.5 + anchored["x"] / reference_width,
                    0.5 - anchored["y"] / reference_height,
                ],
                "size": [size["x"] / reference_width, size["y"] / reference_height],
                "pivot": [pivot["x"], pivot["y"]],
            },
        }
        room_layout[character_name] = layout
        room_key = str(ROOM_IDS[room_name])
        room_layout_by_room.setdefault(room_key, {"room": room_name, "characters": {}})
        room_layout_by_room[room_key]["characters"][character_name] = layout
    if not {entry["room"] for entry in room_layout.values()}.issubset(set(ROOM_IDS)):
        raise RuntimeError("scene render manifest contains an unknown ERoom layout")

    tables = read_json(PT_BR)["tables"]
    localized_text: dict[str, str] = {}
    localized_by_line_key: dict[str, str] = {}
    for table_name, entries in tables.items():
        for entry in entries:
            key = str(entry["id"])
            text = entry["text"]
            if key in localized_text and localized_text[key] != text:
                raise RuntimeError(f"conflicting Portuguese text for localization ID {key}")
            localized_text[key] = text
            line_key = entry.get("key")
            if line_key:
                if line_key in localized_by_line_key and localized_by_line_key[line_key] != text:
                    raise RuntimeError(f"conflicting Portuguese text for Yarn line key {line_key}")
                localized_by_line_key[line_key] = text

    line_metadata = read_json(LINE_METADATA).get("line_metadata", {})
    missing_line_keys = sorted(set(line_metadata) - set(localized_by_line_key))
    if missing_line_keys:
        raise RuntimeError(
            f"Portuguese tables are missing {len(missing_line_keys)} recovered Yarn line keys; "
            f"examples: {missing_line_keys[:5]}"
        )

    minified_json(PROGRAM, destination / "narrative/program.json")
    minified_json(LINE_METADATA, destination / "narrative/line_metadata.json")
    minified_json(
        PT_BR,
        destination / "narrative/texts_ptbr.json",
        {"locale": "pt-BR", "texts": localized_by_line_key, "ids": localized_text},
    )
    manifest = {
        "images": image_map,
        "backgrounds": backgrounds,
        "room_layout": room_layout,
        "room_layout_by_room": room_layout_by_room,
        "room_layout_reference_resolution": [reference_width, reference_height],
        "engine_artifacts": ENGINE_ARTIFACTS,
        "intro": {
            "video": intro_relative,
            "sha256": intro_sha256,
            "size_bytes": intro_source.stat().st_size,
            "width": intro_clip["width"],
            "height": intro_clip["height"],
            "frame_rate": intro_clip["frame_rate"],
            "frame_count": intro_clip["frame_count"],
            "audio_channel_count": sum(int(value) for value in intro_clip["audio_channels"]),
            "audio_sample_rate": max(int(value) for value in intro_clip["audio_sample_rates"]),
            "first_yarn_node": intro_record["subtitles"][0]["node"],
            "subtitle_timeline": intro_record["subtitles"],
            "subtitle_schedule_total_seconds": intro_record["total_timeline_seconds"],
            "video_asset": intro_relative,
            "can_skip": True,
        },
        "menu": {
            "images": menu_images,
            "background_asset": "menu/mainMenu_bg.png",
            "house_asset": menu_images["house"],
            "logo_asset": menu_images["logo"],
            "eyes_asset": menu_images["eyes"],
            "teeth_asset": menu_images["teeth"],
            "button_asset": menu_images["button"],
            "peephole_asset": menu_images["peephole"],
            "masks": [menu_images["mask_eyes"], menu_images["mask_teeth"]],
            "lights": [menu_images["light_eyes"], menu_images["light_teeth"]],
            "references": menu_references,
            "source_files": menu_evidence["source_files"],
            "scene": {
                "build_index": menu_evidence["scene"]["build_index"],
                "scene_file": menu_evidence["scene"]["scene_file"],
                "name": menu_evidence["scene"]["name"],
                "objects": scene_objects,
            },
        },
        "world_manifest": "world/world_manifest.json",
        "world": world_summary,
        "music": music_summary,
        "game_ui": ui_summary,
    }
    minified_json(PROGRAM, destination / "presentation/assets.json", manifest)
    licenses = stage_third_party_notices(destination)

    return {
        "output_dir": str(destination),
        "character_sprite_texture_exports": len(character_images),
        "scene_sprite_exports": len(scene_manifest["exports"]),
        "copied_unique_images": copied,
        "image_mappings": len(image_map),
        "room_backgrounds": len(backgrounds),
        "room_character_layouts": len(room_layout),
        "intro_video_bytes": intro_source.stat().st_size,
        "intro_video_sha256": intro_sha256,
        "menu_image_count": len(menu_images),
        "world_mesh_count": world_summary["mesh_count"],
        "world_texture_count": world_summary["texture_count"],
        "world_android_texture_bytes": world_summary["texture_bytes"],
        "game_ui_sprite_count": ui_summary["sprites"],
        "game_ui_font_count": ui_summary["fonts"],
        "pt_br_text_ids": len(localized_text),
        "pt_br_yarn_line_keys": len(localized_by_line_key),
        "validated_line_metadata_keys": len(line_metadata),
        "program_bytes": (destination / "narrative/program.json").stat().st_size,
        "line_metadata_bytes": (destination / "narrative/line_metadata.json").stat().st_size,
        "audio_included": True,
        "third_party_licenses": licenses,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_DESTINATION,
        help=f"Android assets staging directory (default: {DEFAULT_DESTINATION})",
    )
    parser.add_argument("--music-only", action="store_true",
                        help="stage validated music into an existing asset tree without rebuilding other assets")
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    if args.music_only:
        result = stage_music_assets(destination)
        presentation = destination / "presentation/assets.json"
        if presentation.is_file():
            metadata = read_json(presentation)
            metadata["music"] = result
            minified_json(presentation, presentation, metadata)
    else:
        result = prepare(destination)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
