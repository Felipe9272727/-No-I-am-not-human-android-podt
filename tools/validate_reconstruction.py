#!/usr/bin/env python3
"""Validate recovered narrative joins and APK contents without running game code."""
import argparse
import hashlib
import json
import re
import struct
import zipfile
from pathlib import Path


def check(root: Path, apk: Path | None):
    program = json.loads((root / 'narrative/program.json').read_text())
    nodes = program['nodes']
    line_ids = set()
    instruction_count = 0
    for name, node in nodes.items():
        instructions = node['instructions']
        instruction_count += len(instructions)
        for label, target in node['labels'].items():
            assert isinstance(target, int) and 0 <= target <= len(instructions), (name, label, target)
        for instruction in instructions:
            opcode, operands = instruction['opcode'], instruction['operands']
            assert isinstance(opcode, int) and 0 <= opcode <= 16, (name, opcode)
            assert isinstance(operands, list)
            assert all(v is None or isinstance(v, (str, bool, int, float)) for v in operands)
            if opcode in (0, 10):
                assert operands[0] in node['labels'], (name, operands[0])
            if opcode in (2, 4):
                assert isinstance(operands[0], str)
                line_ids.add(operands[0])

    result = {
        'source_execution': 'No original game executable, DLL, or installer was run.',
        'nodes': len(nodes), 'instructions': instruction_count,
        'initial_values': len(program['initial_values']),
        'distinct_line_and_option_ids': len(line_ids), 'localization': {},
    }
    for locale in ('english_en_', 'portuguese_brazil_pt-br_'):
        source = json.loads((root / f'assets/localization/{locale}.json').read_text())
        texts = {}
        duplicates = 0
        for entries in source['tables'].values():
            for row in entries:
                key = row.get('key')
                if not key:
                    continue
                assert isinstance(row['text'], str)
                if key in texts:
                    if key in line_ids:
                        assert texts[key] == row['text'], ('conflicting dialogue translation', locale, key)
                    duplicates += 1
                texts[key] = row['text']
        missing = sorted(line_ids - texts.keys())
        assert not missing, (locale, missing[:20])
        result['localization'][locale] = {
            'mapped_dialogue_and_option_ids': len(line_ids),
            'missing': len(missing), 'duplicate_records': duplicates,
        }

    if apk:
        binaries = []
        apk_localization = {}
        with zipfile.ZipFile(apk) as archive:
            names = archive.namelist()
            assert 'AndroidManifest.xml' in names and 'classes.dex' in names
            for item in archive.infolist():
                assert not item.filename.lower().endswith(('.exe', '.dll', '.rne', '.msi', '.url'))
                with archive.open(item) as stream:
                    head = stream.read(64)
                assert not head.startswith(b'MZ'), ('Windows binary in APK', item.filename)
                if item.filename.startswith('lib/') and item.filename.endswith('.so'):
                    assert head.startswith(b'\x7fELF'), item.filename
                    machine = struct.unpack_from('<H', head, 18)[0]
                    abi = item.filename.split('/')[1]
                    assert machine == {'arm64-v8a': 183, 'x86_64': 62}[abi], (abi, machine)
                    binaries.append({'path': item.filename, 'elf_machine': machine})
            assert any('arm64-v8a' in b['path'] for b in binaries), 'ARM64 native code missing'
            java = (root / 'mobile-runtime/app/src/main/java/org/reconstruction/viewer/MainActivity.java').read_text()
            image_block = java.split('String[] IMAGES = {', 1)[1].split('};', 1)[0]
            referenced_images = re.findall(r'"([^\"]+\.png)"', image_block)
            for name in referenced_images:
                assert 'assets/images/' + name in names, ('APK missing referenced image', name)
            assert json.loads(archive.read('assets/narrative/program.json')) == program, 'APK bytecode differs from validated source'
            for locale in ('english_en_', 'portuguese_brazil_pt-br_'):
                packed = json.loads(archive.read(f'assets/localization/{locale}.json'))
                source = json.loads((root / f'assets/localization/{locale}.json').read_text())
                assert packed == source, ('APK localization differs from validated source', locale)
                mapped = {row['key']: row['text'] for rows in packed['tables'].values() for row in rows if row.get('key')}
                assert not line_ids - mapped.keys(), ('APK missing dialogue text keys', locale)
                apk_localization[locale] = {'mapped_dialogue_and_option_ids': len(line_ids), 'missing': 0}
        result['apk'] = {
            'file': apk.name, 'bytes': apk.stat().st_size,
            'sha256': hashlib.file_digest(apk.open('rb'), 'sha256').hexdigest(),
            'native_libraries': binaries, 'windows_binaries_found': 0,
            'localization': apk_localization,
            'referenced_images_present': len(referenced_images),
            'device_test': 'Not performed; no Android device or working emulator was available.',
        }
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1] / 'reconstruction')
    parser.add_argument('--apk', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = check(args.root, args.apk)
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(encoded + '\n')
    print(encoded)
