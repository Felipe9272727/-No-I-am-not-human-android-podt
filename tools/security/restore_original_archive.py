#!/usr/bin/env python3
"""Reassemble preserved input parts and verify identity; never execute input."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

EXPECTED = 'f8e6a46efbd41452266790a1350bbec3cfd6027470282171b912df80b08489f1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parts_directory', type=Path)
    parser.add_argument('output_zip', type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.parts_directory / 'NINAH-Original-Manifest.json').read_text())
    if manifest['sha256'] != EXPECTED or manifest['size_bytes'] != 1042955341:
        raise ValueError('Unexpected original input manifest.')
    args.output_zip.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output_zip.with_suffix(args.output_zip.suffix + '.partial')
    whole = hashlib.sha256()
    offset = 0
    with temporary.open('wb') as output:
        for part in manifest['parts']:
            if Path(part['file_name']).name != part['file_name'] or part['offset'] != offset:
                raise ValueError('Unsafe or unordered part manifest.')
            digest = hashlib.sha256()
            length = 0
            with zipfile.ZipFile(args.parts_directory / part['file_name']) as archive:
                info = archive.getinfo(part['member'])
                if info.file_size != part['bytes']:
                    raise ValueError('Unexpected part length.')
                with archive.open(info) as source:
                    while block := source.read(1024 * 1024):
                        output.write(block)
                        digest.update(block)
                        whole.update(block)
                        length += len(block)
            if length != part['bytes'] or digest.hexdigest() != part['sha256']:
                raise ValueError('Original input part hash mismatch.')
            offset += length
    if offset != manifest['size_bytes'] or whole.hexdigest() != EXPECTED:
        raise ValueError('Reassembled original archive hash mismatch.')
    temporary.replace(args.output_zip)
    print(json.dumps({'output': str(args.output_zip), 'size_bytes': offset,
                      'sha256': whole.hexdigest(), 'original_code_executed': False}))


if __name__ == '__main__':
    main()
