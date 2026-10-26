#!/usr/bin/env python3
"""Build the current C++ Android gameplay host with ASan/UBSan, without JNI.

Uses the new Rust bridge compiled from this repository. Original executable
material is never loaded. This checks rules and snapshots, not Android execution.
"""
from pathlib import Path
import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
NATIVE = ROOT / 'reconstruction/native-game'
ANDROID = ROOT / 'reconstruction/android-current'


def sources_hash():
    digest = hashlib.sha256()
    paths = list((NATIVE / 'include').rglob('*.hpp')) + list((NATIVE / 'generated').glob('*.hpp'))
    paths += list((NATIVE / 'src').glob('*.cpp')) + list((ANDROID / 'native').glob('*.cpp'))
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version-code',type=int,default=11)
    args=parser.parse_args()
    # Independent diagnostic invocations must not truncate each other's objects.
    BUILD=Path(tempfile.mkdtemp(prefix='build-campaign-host-',dir=ANDROID))
    BUILD.mkdir(parents=True, exist_ok=True)
    rust = NATIVE / 'bridge/target/release/libninah_yarn_bridge.a'
    if not rust.is_file():
        raise RuntimeError('Compile the locked host Rust bridge release before this test')
    fingerprint = sources_hash()
    flags = ['-std=c++17', '-O0', '-g1', '-Wall', '-Wextra', '-Werror', '-pedantic',
             '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
             '-I' + str(NATIVE / 'include'), '-I' + str(NATIVE / 'generated')]
    sources = sorted((NATIVE / 'src').glob('*.cpp')) + [ANDROID / 'native/current_game.cpp', ANDROID / 'native/host_test.cpp']

    def compile_one(source):
        output = BUILD / (source.stem + '.o')
        subprocess.run(['g++', *flags, '-c', str(source), '-o', str(output)], check=True, cwd=ROOT)
        if not output.is_file() or output.stat().st_size==0:
            raise RuntimeError('Compiler produced an empty object: '+str(source))
        return output

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        objects = list(pool.map(compile_one, sources))
    if sources_hash() != fingerprint:
        raise RuntimeError('Sources changed during compilation; refusing to run mixed objects')
    executable = BUILD / 'current-host-test'
    subprocess.run(['g++', *flags, *map(str, objects), str(rust), '-ldl', '-lpthread', '-lm', '-o', str(executable)], check=True, cwd=ROOT)
    result = subprocess.run([str(executable), str(ROOT / 'reconstruction')], cwd=ROOT,
            env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0'), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = ANDROID / ('qa/v%d-native-host.log'%args.version_code)
    output.write_text(result.stdout)
    print(result.stdout, flush=True)
    result.check_returncode()
    report = {'passed': True, 'cpp_sources_sha256': fingerprint, 'host_sanitizers': ['AddressSanitizer', 'UndefinedBehaviorSanitizer'],
              'source_tv_node': 'tv_1_necessary', 'source_tv_lines': 7, 'day1_energy': 2,
              'transition_and_dialogue_save_restore': True, 'android_device_execution_tested': False,
              'fresh_context_snapshot_import': True, 'invalid_import_preserves_existing_save': True,
              'save_content_identity_encoding': 'hex string (Android JSONObject compatible)',
              'full_campaign_implemented': False, 'original_executables_loaded': False}
    (ANDROID / ('host_validation_v%d.json'%args.version_code)).write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
