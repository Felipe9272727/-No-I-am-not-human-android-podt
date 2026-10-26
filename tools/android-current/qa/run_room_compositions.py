#!/usr/bin/env python3
"""Compare seven real GLES room captures with independently composed source layers.

Uses the current build-gles classes produced by run_gles_test.py. This verifies
host rendering, not an Android device or the original Unity runtime.
"""
import json
import os
from pathlib import Path
import subprocess
from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[3]
QA = Path(__file__).resolve().parent
ASSETS = ROOT / 'reconstruction/android-current/app/src/main/assets'
OUTPUT = ROOT / 'reconstruction/android-current/qa/rooms-v09'


def reference(room):
    canvas = Image.new('RGBA', (1280, 720), (0, 0, 0, 255))
    for layer in sorted(room['layers'], key=lambda row: row['draw_order']):
        with Image.open(ASSETS / layer['asset']) as source:
            source.load()
            sprite = source.convert('RGBA')
        x, y, width, height = [v * 2 / 3 for v in layer['rect']]
        if layer['preserve_aspect']:
            scale = min(width / sprite.width, height / sprite.height)
            w, h = sprite.width * scale, sprite.height * scale
            x += (width - w) / 2
            y += (height - h) / 2
            width, height = w, h
        channels = sprite.split()
        color = layer['color']
        sprite = Image.merge('RGBA', tuple(channel.point([round(i * color[index]) for i in range(256)]) for index, channel in enumerate(channels)))
        sx, sy = sprite.width / width, sprite.height / height
        positioned = sprite.transform(canvas.size, Image.Transform.AFFINE,
                (sx, 0, -x * sx, 0, sy, -y * sy), Image.Resampling.BILINEAR)
        canvas = Image.alpha_composite(canvas, positioned)
    return canvas.convert('RGB')


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cp = os.pathsep.join([str(QA / 'build-gles')] + [str(p) for p in sorted((QA / 'deps').glob('*.jar')) if not p.name.endswith('-sources.jar')])
    env = dict(os.environ, EGL_PLATFORM='surfaceless', MESA_GLES_VERSION_OVERRIDE='2.0', LIBGL_ALWAYS_SOFTWARE='1')
    command = ['java', '-Xmx256m', '-Dorg.lwjgl.opengles.libname=/lib/x86_64-linux-gnu/libGL.so.1',
               '-Dorg.lwjgl.egl.libname=/lib/x86_64-linux-gnu/libEGL.so.1', '-cp', cp,
               'WorldPreviewGLES', str(ASSETS), str(OUTPUT / 'rooms.png'), '0', 'room-compositions']
    completed = subprocess.run(command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (OUTPUT / 'render.log').write_text(completed.stdout)
    print(completed.stdout, flush=True)
    completed.check_returncode()
    presentation = json.loads((ASSETS / 'presentation/assets.json').read_text())
    manifest = json.loads((ASSETS / presentation['room_layers_manifest']).read_text())
    metrics = []
    for room in manifest['rooms']:
        path = OUTPUT / f"room-{room['id']}.png"
        with Image.open(path) as screenshot:
            screenshot.verify()
        with Image.open(path) as screenshot:
            screenshot.load()
            actual = screenshot.convert('RGB')
        expected = reference(room)
        expected.save(OUTPUT / f"room-{room['id']}-reference.png")
        difference = ImageChops.difference(actual, expected)
        mean = sum(ImageStat.Stat(difference).mean) / 3
        metrics.append({'room': room['id'], 'layers': len(room['layers']), 'mean_absolute_rgb_error': mean})
        if mean > 5:
            raise AssertionError(f"Room {room['id']} diverges from source composition: {mean:.3f}")
    report = {'host_gles2': True, 'android_execution': False, 'rooms': metrics}
    target = ROOT / 'reconstruction/android-current/room_layers_v09_validation.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
