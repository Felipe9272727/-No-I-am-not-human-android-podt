#!/usr/bin/env python3
"""Regress the Android missing-shader failure without a desktop resource fallback.

GDX classes come from a jar stripped of all resources. The sole source for
classpath data is the provided APK, using libGDX's real Classpath FileHandle.
With --render, render 120 GLES2 frames using the same isolated classpath.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
QA=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk',type=Path)
    parser.add_argument('--expect-missing',action='store_true')
    parser.add_argument('--render',action='store_true')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    apk=args.apk.resolve()
    sys.path.insert(0,str(ROOT/'tools/android-current'))
    spec=importlib.util.spec_from_file_location('apk_builder',ROOT/'tools/android-current/build_apk.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    work=QA/'build-apk-shaders';work.mkdir(parents=True,exist_ok=True)
    core=builder.GDX_ROOT/'gdx-1.14.2.jar'
    stripped=work/'gdx-classes-only.jar'
    with zipfile.ZipFile(core) as source,zipfile.ZipFile(stripped,'w',zipfile.ZIP_DEFLATED) as out:
        for entry in source.infolist():
            if entry.filename.endswith('.class'):out.writestr(entry,source.read(entry))
    with zipfile.ZipFile(apk) as archive:
        try:resources=builder.validate_gdx_java_resources(archive);package_error=None
        except RuntimeError as error:resources=[];package_error=str(error)
    classes=work/'classes'
    subprocess.run(['java','-jar',str(ROOT/'tools/android-current/java/ecj-3.38.0.jar'),'-8','-nowarn',
        '-classpath',str(stripped),'-d',str(classes),str(QA/'ClasspathShaderProbe.java')],check=True,cwd=ROOT)
    cp=os.pathsep.join(map(str,[classes,stripped,apk]))
    probe=subprocess.run(['java','-cp',cp,'ClasspathShaderProbe',str(apk)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=ROOT)
    digest=hashlib.sha256()
    with apk.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    result={'apk':str(apk),'package_resource_validation_error':package_error,'classpath_probe_exit_code':probe.returncode,
        'classpath_probe_output':probe.stdout,'resources':resources,'desktop_gdx_resources_on_classpath':False,
        'android_execution_tested':False,'apk_sha256':digest.hexdigest()}
    print(probe.stdout,flush=True)
    if args.expect_missing:
        if not package_error or probe.returncode==0 or 'default.vertex.glsl' not in probe.stdout:
            raise AssertionError('old APK did not reproduce the reported missing default.vertex.glsl failure')
        result['status']='reported_device_failure_reproduced'
    else:
        if package_error:raise AssertionError(package_error)
        probe.check_returncode()
        result['status']='apk_classpath_resources_verified'
        if args.render:
            deps=[p for p in (QA/'deps').glob('*.jar') if not p.name.startswith('gdx-')]
            # Lwjgl3Files/GLES20 adapters are in backend jars, which contain no GDX core shaders.
            deps+=[QA/'deps/gdx-backend-lwjgl3-1.14.2.jar',QA/'deps/gdx-lwjgl3-angle-1.14.2.jar',
                QA/'deps/gdx-platform-1.14.2-natives-desktop.jar',QA/'deps/gdx-jnigen-loader-2.5.2.jar']
            for jar in deps:
                with zipfile.ZipFile(jar) as archive:
                    if set(archive.namelist())&set(builder.REQUIRED_GDX_SHADERS):raise AssertionError('desktop shader leak: '+str(jar))
                    if 'META-INF/MANIFEST.MF' in archive.namelist() and b'Class-Path:' in archive.read('META-INF/MANIFEST.MF'):
                        raise AssertionError('uncontrolled transitive classpath: '+str(jar))
            cp=os.pathsep.join(map(str,[QA/'build-gles',stripped,apk,*deps]))
            env=os.environ.copy();env.update(EGL_PLATFORM='surfaceless',MESA_GLES_VERSION_OVERRIDE='2.0',LIBGL_ALWAYS_SOFTWARE='1')
            screenshot=ROOT/'reconstruction/android-current/qa/apk-only-gles2.png'
            run=subprocess.run(['java','-Xmx256m','-Dorg.lwjgl.opengles.libname=/lib/x86_64-linux-gnu/libGL.so.1',
                '-Dorg.lwjgl.egl.libname=/lib/x86_64-linux-gnu/libEGL.so.1','-cp',cp,'WorldPreviewGLES',
                str(ROOT/'reconstruction/android-current/app/src/main/assets'),str(screenshot),'0'],
                cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            print(run.stdout,flush=True);run.check_returncode()
            result['isolated_gles2_render']={'frames':120,'status':'passed','log':run.stdout,'screenshot':str(screenshot)}
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'])

if __name__=='__main__':main()
