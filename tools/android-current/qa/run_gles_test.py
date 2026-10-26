#!/usr/bin/env python3
"""Render the real staged world under Mesa OpenGL ES 2, plus shader fallback QA.

This is a host graphics test, not Android device/emulator execution.
Downloads pinned-version official Maven artifacts, verified with their checksums.
"""
from pathlib import Path
import concurrent.futures
import hashlib
import os
import subprocess
import struct
import urllib.request
import zlib

ROOT=Path(__file__).resolve().parents[3]
QA=Path(__file__).resolve().parent
DEPS=QA/'deps'
MAVEN='https://repo.maven.apache.org/maven2/'
ARTIFACTS=[
    ('com/badlogicgames/gdx/gdx','1.14.2','gdx-1.14.2.jar'),
    ('com/badlogicgames/gdx/gdx-backend-lwjgl3','1.14.2','gdx-backend-lwjgl3-1.14.2.jar'),
    ('com/badlogicgames/gdx/gdx-lwjgl3-angle','1.14.2','gdx-lwjgl3-angle-1.14.2.jar'),
    ('com/badlogicgames/gdx/gdx-platform','1.14.2','gdx-platform-1.14.2-natives-desktop.jar'),
    ('com/badlogicgames/gdx/gdx-jnigen-loader','2.5.2','gdx-jnigen-loader-2.5.2.jar'),
    ('org/json/json','20250517','json-20250517.jar'),
]
for module in ['lwjgl','lwjgl-egl','lwjgl-opengles','lwjgl-opengl','lwjgl-glfw']:
    ARTIFACTS.append(('org/lwjgl/'+module,'3.3.3',module+'-3.3.3.jar'))
    if module!='lwjgl-egl':ARTIFACTS.append(('org/lwjgl/'+module,'3.3.3',module+'-3.3.3-natives-linux.jar'))

def download(row):
    group,version,name=row
    url=MAVEN+group+'/'+version+'/'+name
    expected=urllib.request.urlopen(url+'.sha1',timeout=60).read().decode().strip().split()[0]
    path=DEPS/name
    if not path.is_file() or hashlib.sha1(path.read_bytes()).hexdigest()!=expected:
        data=urllib.request.urlopen(url,timeout=120).read()
        if hashlib.sha1(data).hexdigest()!=expected:raise RuntimeError('checksum mismatch: '+name)
        path.write_bytes(data)
    return name

def main():
    DEPS.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for name in pool.map(download,ARTIFACTS):print('Verified',name,flush=True)
    cp=os.pathsep.join(str(p) for p in sorted(DEPS.glob('*.jar')) if not p.name.endswith('-sources.jar'))
    source=ROOT/'reconstruction/android-current/app/src/main/java/org/reconstruction/current'
    build=QA/'build-gles'
    java=[source/'RoomEngine.java',source/'WorldRenderer.java',source/'TombstoneSummary.java',source/'RenderResolution.java',source/'FrameSequence.java',source/'DoorMotion.java',QA/'DoorMotionTest.java',QA/'FrameSequenceTest.java',
          QA/'WorldPreviewGLES.java',QA/'WorldMathTest.java',QA/'WorldGeometryTest.java',QA/'WorldVisibilityTest.java',QA/'WorldInteractionTest.java',QA/'RenderLoopPolicyTest.java',QA/'RenderResolutionTest.java',QA/'TombstoneSummaryTest.java']
    subprocess.run(['java','-jar',str(ROOT/'tools/android-current/java/ecj-3.38.0.jar'),'-17','-nowarn','-classpath',cp,'-d',str(build),*[str(p) for p in java]],check=True,cwd=ROOT)
    cp=str(build)+os.pathsep+cp
    subprocess.run(['java','-cp',cp,'org.reconstruction.current.FrameSequenceTest'],check=True,cwd=ROOT)
    subprocess.run(['java','-cp',cp,'org.reconstruction.current.DoorMotionTest'],check=True,cwd=ROOT)
    subprocess.run(['java','-cp',cp,'org.reconstruction.current.WorldMathTest'],check=True,cwd=ROOT)
    subprocess.run(['java','-cp',cp,'org.reconstruction.current.WorldGeometryTest'],check=True,cwd=ROOT)
    subprocess.run(['java','-cp',cp,'org.reconstruction.current.WorldVisibilityTest'],check=True,cwd=ROOT)
    subprocess.run(['java','-cp',cp,'org.reconstruction.current.WorldInteractionTest'],check=True,cwd=ROOT)
    subprocess.run(['java','-cp',cp,'org.reconstruction.current.RenderLoopPolicyTest'],check=True,cwd=ROOT)
    subprocess.run(['java','-cp',cp,'org.reconstruction.current.RenderResolutionTest'],check=True,cwd=ROOT)
    subprocess.run(['java','-cp',cp,'org.reconstruction.current.TombstoneSummaryTest'],check=True,cwd=ROOT)
    env=os.environ.copy();env.update(EGL_PLATFORM='surfaceless',MESA_GLES_VERSION_OVERRIDE='2.0',LIBGL_ALWAYS_SOFTWARE='1')
    output=ROOT/'reconstruction/android-current/qa';output.mkdir(exist_ok=True)
    for label,extra in [('gles2',[]),('gles2-fallback',['inject-shader-failure'])]:
        command=['java','-Xmx256m','-Dorg.lwjgl.opengles.libname=/lib/x86_64-linux-gnu/libGL.so.1',
            '-Dorg.lwjgl.egl.libname=/lib/x86_64-linux-gnu/libEGL.so.1','-cp',cp,'WorldPreviewGLES',
            str(ROOT/'reconstruction/android-current/app/src/main/assets'),str(output/(label+'.png')),'0',*extra]
        result=subprocess.run(command,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (output/(label+'.log')).write_text(result.stdout)
        print(result.stdout,flush=True)
        result.check_returncode()
        png=(output/(label+'.png')).read_bytes()
        if not png.startswith(b'\x89PNG\r\n\x1a\n') or not png.endswith(b'IEND\xaeB`\x82'):
            raise RuntimeError('incomplete screenshot: '+label)
        offset=8
        while offset<len(png):
            size=struct.unpack_from('>I',png,offset)[0]
            chunk=png[offset+4:offset+8+size]
            if offset+size+12>len(png) or zlib.crc32(chunk)!=struct.unpack_from('>I',png,offset+8+size)[0]:
                raise RuntimeError('invalid PNG chunk: '+label)
            offset+=size+12

if __name__=='__main__':main()
