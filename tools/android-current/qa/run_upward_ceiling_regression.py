#!/usr/bin/env python3
"""Reproduce and regress the clipped ceiling at the recovered Unity camera pose.

Run after run_gles_test.py, which compiles WorldPreviewGLES and its pinned deps.
The center ray must hit source renderer 2124/material 28 and the linear/HDR/Neutral
path must retain texture detail in the center region.
"""
from pathlib import Path
import hashlib
import os
import re
import struct
import subprocess
import zlib

ROOT=Path(__file__).resolve().parents[3]
QA=Path(__file__).resolve().parent
DEPS=QA/'deps'
BUILD=QA/'build-gles'
ASSETS=ROOT/'reconstruction/android-current/app/src/main/assets'
FIXTURES=QA/'fixtures'
BASELINE=FIXTURES/'upward-ceiling-before.png'
OUTPUT=FIXTURES/'upward-ceiling-after.png'
BASELINE_SHA='649ac64f86e6411c7dbd037c8d304da747eed5383b6fbb016bf65602931a46ed'

def check_png(path):
    data=path.read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or not data.endswith(b'IEND\xaeB`\x82'):
        raise AssertionError('incomplete PNG: '+str(path))
    offset=8
    while offset<len(data):
        size=struct.unpack_from('>I',data,offset)[0]
        chunk=data[offset+4:offset+8+size]
        if offset+size+12>len(data) or zlib.crc32(chunk)!=struct.unpack_from('>I',data,offset+8+size)[0]:
            raise AssertionError('invalid PNG chunk: '+str(path))
        offset+=size+12

def main():
    if not BUILD.is_dir() or not any(DEPS.glob('gdx-*.jar')):
        raise SystemExit('Run tools/android-current/qa/run_gles_test.py first to compile the host preview.')
    if hashlib.sha256(BASELINE.read_bytes()).hexdigest()!=BASELINE_SHA:
        raise AssertionError('before-render evidence changed')
    cp=os.pathsep.join([str(BUILD),*(str(p) for p in sorted(DEPS.glob('*.jar')))])
    env=os.environ.copy();env.update(EGL_PLATFORM='surfaceless',MESA_GLES_VERSION_OVERRIDE='2.0',LIBGL_ALWAYS_SOFTWARE='1')
    command=['java','-Xmx256m','-Dorg.lwjgl.opengles.libname=/lib/x86_64-linux-gnu/libGL.so.1',
        '-Dorg.lwjgl.egl.libname=/lib/x86_64-linux-gnu/libEGL.so.1','-cp',cp,'WorldPreviewGLES',
        str(ASSETS),str(OUTPUT),'0','','-75','-4','1.584','-10','ray-hit','expect-ceiling-detail']
    result=subprocess.run(command,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    print(result.stdout,end='')
    result.check_returncode()
    if 'CENTER_RAY_HIT=renderer=2124 name=Потолок materials=[28]' not in result.stdout:
        raise AssertionError('camera center no longer reproduces the source ceiling/material')
    match=re.search(r'CEILING_DETAIL clipped=([0-9.]+) uniquePixels=(\d+)',result.stdout)
    if not match or float(match.group(1))>.20 or int(match.group(2))<100:
        raise AssertionError('ceiling detail regression did not pass')
    check_png(OUTPUT)
    print('Upward ceiling regression: PASS (source hit, unclipped texture detail, PNG integrity)')

if __name__=='__main__':main()
