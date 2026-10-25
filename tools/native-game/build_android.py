#!/usr/bin/env python3
"""Cross-build the recovered core and Yarn bridge, without running game binaries.

This produces shared-library components, not an APK or a playable campaign.
Use the pinned official NDK r27c (27.2.12479018) and Rust 1.85.1.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / 'reconstruction/native-game'
TARGETS = {
    'arm64-v8a': ('aarch64-linux-android', 'AArch64'),
    'x86_64': ('x86_64-linux-android', 'Advanced Micro Devices X86-64'),
}


def run(argv, **kwargs):
    return subprocess.run([str(value) for value in argv], check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', type=Path, default=ROOT / 'tools/android/android-ndk-r27c')
    parser.add_argument('--cargo', default=os.environ.get('CARGO', '/root/.cargo/bin/cargo'))
    parser.add_argument('--abi', choices=TARGETS, action='append')
    args = parser.parse_args()
    properties = (args.ndk / 'source.properties').read_text()
    if 'Pkg.Revision = 27.2.12479018' not in properties:
        raise SystemExit('Expected pinned Android NDK 27.2.12479018.')
    llvm = args.ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin'
    run(['python3', ROOT / 'tools/native-game/generate_production_data.py'])
    run(['python3', ROOT / 'tools/reverse-phone/generate_phone_provider.py'])
    run(['python3', ROOT / 'tools/reverse-localization/generate_line_metadata_provider.py'])
    run(['python3', ROOT / 'tools/reverse-scenes/generate_presentation_provider.py'])
    exports = NATIVE / 'build-android/exports.map'
    exports.parent.mkdir(parents=True, exist_ok=True)
    exports.write_text('NINAH_1 { global: ninah_yarn_*; local: *; };\n')
    results = []
    for abi in args.abi or TARGETS:
        target, machine = TARGETS[abi]
        build = NATIVE / 'build-android' / abi
        build.mkdir(parents=True, exist_ok=True)
        compiler = llvm / f'{target}23-clang++'
        env = dict(os.environ)
        env['CARGO_TARGET_' + target.upper().replace('-', '_') + '_LINKER'] = str(compiler)
        run([args.cargo, 'build', '--locked', '--release', '--target', target,
             '--manifest-path', NATIVE / 'bridge/Cargo.toml'], env=env)
        flags = ['-std=c++17', '-O2', '-fPIC', '-fvisibility=hidden',
                 '-ffunction-sections', '-fdata-sections', '-Wall', '-Wextra',
                 '-Werror', '-pedantic', '-I' + str(NATIVE / 'include'),
                 '-I' + str(NATIVE / 'generated')]
        objects = []
        for source in sorted((NATIVE / 'src').glob('*.cpp')):
            obj = build / (source.stem + '.o')
            run([compiler, *flags, '-c', source, '-o', obj])
            objects.append(obj)
        rust = NATIVE / 'bridge/target' / target / 'release/libninah_yarn_bridge.a'
        cpp_archive = build / 'libninah_gameplay.a'
        # Preserve every C++ module for the future Android/JNI host. The current
        # public shared-library ABI exposes the Yarn bridge only; it is not yet
        # the Android presentation layer or a self-contained game host.
        run([llvm / 'llvm-ar', 'rcs', cpp_archive, *objects])
        output = build / 'libninah_core.so'
        run([compiler, '-shared', '-static-libstdc++', '-Wl,--no-undefined',
             '-Wl,-z,relro,-z,now,-z,noexecstack', '-Wl,--gc-sections',
             '-Wl,-soname,libninah_core.so', '-Wl,--version-script=' + str(exports),
             *objects, '-Wl,--whole-archive', rust, '-Wl,--no-whole-archive',
             '-ldl', '-lm', '-llog', '-o', output])
        run([llvm / 'llvm-strip', '--strip-unneeded', output])
        header = run([llvm / 'llvm-readelf', '-h', output], capture_output=True, text=True).stdout
        if machine not in header or 'DYN (Shared object file)' not in header:
            raise RuntimeError('Unexpected Android shared library architecture.')
        dynamic = run([llvm / 'llvm-readelf', '--dynamic', output], capture_output=True, text=True).stdout
        needed = [line.split('[')[1].split(']')[0] for line in dynamic.splitlines()
                  if '(NEEDED)' in line]
        symbols = run([llvm / 'llvm-readelf', '--dyn-syms', output], capture_output=True, text=True).stdout
        public_api = ['ninah_yarn_' + suffix for suffix in
                      ('create', 'load_line_metadata', 'start', 'advance', 'choose', 'dump_snapshot', 'restore_snapshot', 'free_string', 'destroy')]
        for symbol in public_api:
            if symbol not in symbols:
                raise RuntimeError('Missing C ABI export: ' + symbol)
        result = {'abi': abi, 'rust_target': target, 'minimum_android_api': 23,
                  'machine': machine, 'source_translation_units': len(objects),
                  'cpp_archive': str(cpp_archive.relative_to(ROOT)),
                  'cpp_archive_bytes': cpp_archive.stat().st_size,
                  'cpp_archive_sha256': hashlib.sha256(cpp_archive.read_bytes()).hexdigest(),
                  'needed_libraries': needed, 'c_abi_exports': public_api,
                  'output': str(output.relative_to(ROOT)), 'bytes': output.stat().st_size,
                  'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
        results.append(result)
        print(json.dumps(result), flush=True)
    report = {'ndk_version': '27.2.12479018', 'original_game_executed': False,
              'android_execution_tested': False, 'full_playable_apk': False,
              'scope': 'C++ gameplay static archive plus linked shared-library Rust Yarn C ABI. The shared library currently exports only Yarn functions; Android/JNI host, presentation and full campaign integration remain incomplete.',
              'components': results}
    (NATIVE / 'ANDROID_BUILD_VALIDATION.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
