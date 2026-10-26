#!/usr/bin/env python3
"""Exercise source kitchen-door motion through RoomEngine on Mesa GLES2.

Run after run_gles_test.py compiles WorldPreviewGLES. Uses room 0 / renderer 2141
from the recovered level1 DoorTrigger, then verifies hinge, timing, pause, cancel,
close, and actual rendered-pixel movement.
"""
from pathlib import Path
import json
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
OUTPUT=FIXTURES/'door-room-0-final.png'

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
    FIXTURES.mkdir(parents=True,exist_ok=True)
    cp=os.pathsep.join([str(BUILD),*(str(p) for p in sorted(DEPS.glob('*.jar')))])
    env=os.environ.copy();env.update(EGL_PLATFORM='surfaceless',MESA_GLES_VERSION_OVERRIDE='2.0',LIBGL_ALWAYS_SOFTWARE='1')
    command=['java','-Xmx256m','-Dorg.lwjgl.opengles.libname=/lib/x86_64-linux-gnu/libGL.so.1',
        '-Dorg.lwjgl.egl.libname=/lib/x86_64-linux-gnu/libEGL.so.1','-cp',cp,'WorldPreviewGLES',
        str(ASSETS),str(OUTPUT),'159.2','','6.1','-3.985','1.584','-6.998','ray-hit','','','door-room:0']
    result=subprocess.run(command,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    print(result.stdout,end='')
    result.check_returncode()
    if 'CENTER_RAY_HIT=renderer=2141 ' not in result.stdout:
        raise AssertionError('Kitchen visual fixture camera did not hit source door renderer 2141')
    match=re.search(r'DOOR_GLES=(\{[^\n]+\})',result.stdout)
    if not match:raise AssertionError('door animation report missing')
    report=json.loads(match.group(1))
    if report['room']!=0 or report['renderer']!=2141 or abs(abs(report['openAngle'])-90)>.1:
        raise AssertionError('source kitchen door did not reach its authored endpoint: '+str(report))
    if report['midAngle']==0 or report['openComplete'] is not True or report['pauseFrozen'] is not True:
        raise AssertionError('open timing or pause report invalid: '+str(report))
    if report['cancelComplete'] is not False or abs(report['cancelAngle'])>.0001 or abs(report['closedAngle'])>.0001:
        raise AssertionError('cancel/close sequence failed: '+str(report))
    if report['hingeDrift']>.001 or report['changedPixels']<50:
        raise AssertionError('hinge/pixel movement check failed: '+str(report))
    for suffix in ['before','mid','open']:
        check_png(FIXTURES/f'door-room-0-{suffix}.png')
    check_png(OUTPUT)
    print('Door GLES regression: PASS (hinge, 1s open, pause, cancel, 0.5s close, rendered movement)')

if __name__=='__main__':main()
