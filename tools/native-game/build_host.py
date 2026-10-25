#!/usr/bin/env python3
"""Compile and run reconstructed C++ regressions; never executes game code."""
import hashlib, json, os, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
NATIVE=ROOT/'reconstruction/native-game'
BUILD=NATIVE/'build';BUILD.mkdir(parents=True,exist_ok=True)
subprocess.run([os.environ.get('CARGO','/root/.cargo/bin/cargo'),'build','--locked','--release','--manifest-path',str(NATIVE/'bridge/Cargo.toml')],check=True)
rust_library=str(NATIVE/'bridge/target/release/libninah_yarn_bridge.a')
for generator in ('native-game/generate_production_data.py',
                  'reverse-phone/generate_phone_provider.py',
                  'reverse-localization/generate_line_metadata_provider.py',
                  'reverse-scenes/generate_presentation_provider.py'):
    subprocess.run(['python3',str(ROOT/'tools'/generator)],check=True)
flags=['-std=c++17','-Wall','-Wextra','-Werror','-pedantic','-fsanitize=address,undefined','-fno-omit-frame-pointer','-g','-I'+str(NATIVE/'include'),'-I'+str(NATIVE/'generated')]
def fingerprint():
    digest=hashlib.sha256()
    for folder in ('include','generated','src','tests'):
        for path in sorted((NATIVE/folder).rglob('*')):
            if path.is_file():
                digest.update(str(path.relative_to(NATIVE)).encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()
source_fingerprint=fingerprint()
def require_stable_sources():
    if fingerprint()!=source_fingerprint:
        raise RuntimeError('C++ sources changed during compilation; rerun after edits finish before executing mixed objects.')
objects=[]
for source in sorted((NATIVE/'src').glob('*.cpp')):
    out=BUILD/(source.stem+'.o')
    subprocess.run(['g++',*flags,'-c',str(source),'-o',str(out)],check=True)
    objects.append(str(out))
require_stable_sources()
tests=[]
for source in sorted((NATIVE/'tests').glob('*_tests.cpp')):
    out=BUILD/source.stem
    subprocess.run(['g++',*flags,*objects,str(source),rust_library,'-ldl','-lpthread','-lm','-o',str(out)],check=True)
    require_stable_sources()
    env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'}
    result=subprocess.run([str(out)],env=env,capture_output=True,text=True)
    if result.returncode:
        print(result.stdout,flush=True)
        print(result.stderr,flush=True)
        result.check_returncode()
    tests.append({'test':source.name,'passed':True,'output':result.stdout.strip()})
    print(source.name+': passed',flush=True)
require_stable_sources()
report={'original_game_executed':False,'cpp_sources_sha256':source_fingerprint,'host_cpp_sanitizers':['AddressSanitizer','UndefinedBehaviorSanitizer'],'regression_binaries':tests,'android_execution_tested':False}
(NATIVE/'HOST_VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n')
