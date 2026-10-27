#!/usr/bin/env python3
"""Isolated GLES2 capture proving the original cat preview is debug-gated."""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QA = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gles_suite", QA / "run_gles_test.py")
gles = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gles)


def main() -> None:
    deps = sorted(gles.DEPS.glob("*.jar"))
    expected = [name for _, _, name in gles.ARTIFACTS]
    missing = [name for name in expected if not (gles.DEPS / name).is_file()]
    if missing:
        raise FileNotFoundError(f"GLES dependencies are missing: {missing}")
    cp = os.pathsep.join(map(str, deps))
    source = ROOT / "reconstruction/android-current/app/src/main/java/org/reconstruction/current"
    build = Path("/tmp/ninah-cat3d-gles-classes")
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)
    java = [
        source / "RoomEngine.java", source / "RoomComposition.java", source / "HouseSceneData.java", source / "WorldRenderer.java",
        source / "TombstoneSummary.java", source / "RenderResolution.java", source / "FrameSequence.java",
        source / "DoorMotion.java", source / "SleepTransition.java", QA / "SleepTransitionTest.java",
        QA / "DoorMotionTest.java", QA / "FrameSequenceTest.java", QA / "RoomCompositionTest.java",
        source / "SaveFileStore.java", source / "NativeJson.java", QA / "SaveFileStoreTest.java",
        QA / "WorldPreviewGLES.java",
    ]
    subprocess.run([
        "java", "-jar", str(ROOT / "tools/android-current/java/ecj-3.38.0.jar"), "-17", "-nowarn",
        "-classpath", cp, "-d", str(build), *map(str, java),
    ], cwd=ROOT, check=True)

    assets = ROOT / "reconstruction/android-current/app/src/main/assets"
    capture = Path("/tmp/ninah-cat3d-preview-on.png")
    command = [
        "java", "-Xmx256m", "-Dorg.lwjgl.opengles.libname=/lib/x86_64-linux-gnu/libGL.so.1",
        "-Dorg.lwjgl.egl.libname=/lib/x86_64-linux-gnu/libEGL.so.1",
        "-cp", str(build) + os.pathsep + cp, "WorldPreviewGLES", str(assets), str(capture), "0",
        "none", "34", "-5.27", "2.0", "-7.26", "none", "none", "none", "none", "cat-preview",
    ]
    env = os.environ.copy()
    env.update(EGL_PLATFORM="surfaceless", MESA_GLES_VERSION_OVERRIDE="2.0", LIBGL_ALWAYS_SOFTWARE="1")
    result = subprocess.run(command, cwd=ROOT, env=env, check=True, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(result.stdout)
    report = ROOT / "reconstruction/android-current/qa/cat3d_gles_qa.json"
    if not report.is_file() or not capture.is_file():
        raise RuntimeError("GLES preview did not produce its report and capture")
    print(f"QA_REPORT={report}")
    print(f"ENABLED_CAPTURE={capture}")
    print(f"DISABLED_CAPTURE={capture.with_name(capture.name.replace('-on.png', '-off.png'))}")


if __name__ == "__main__":
    main()
