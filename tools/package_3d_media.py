#!/usr/bin/env python3
"""Package referenced original world/UI data; source code is backed up in Git."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'deliverables/NINAH-Recursos-3D-UI.zip'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    world_root = ROOT / 'reconstruction/reverse-world'
    ui_root = ROOT / 'reconstruction/reverse-ui'
    world_path, ui_path = world_root / 'world_manifest.json', ui_root / 'ui_manifest.json'
    world, ui = json.loads(world_path.read_text()), json.loads(ui_path.read_text())
    refs = [(world_root / x['mesh_asset'], x['sha256']) for x in world['meshes']]
    refs += [(world_root / x['asset'], x['sha256']) for x in world['textures']]
    refs += [(ui_root / x['path'], x['sha256']) for x in ui['sprites'].values()]
    for font in ui['fonts']:
        for key in ('atlas', 'embedded_ttf'):
            item = font.get(key)
            if item and item.get('path'):
                refs.append((ui_root / item['path'], item['sha256']))
    for path, expected in refs:
        assert path.is_file() and not path.is_symlink(), path
        assert digest(path) == expected, path
    files = sorted({p for p, _ in refs} | {world_path, ui_path})
    entries = []
    OUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUT.with_suffix('.zip.partial')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            assert path.suffix.lower() in {'.bin', '.png', '.ttf', '.otf', '.json'}, path
            with path.open('rb') as stream:
                magic = stream.read(4)
            assert magic[:2] != b'MZ' and magic != b'\x7fELF', path
            relative = str(path.relative_to(ROOT))
            entries.append({'path': relative, 'bytes': path.stat().st_size, 'sha256': digest(path)})
            archive.write(path, relative)
        archive.writestr('MEDIA_MANIFEST.json', json.dumps({'files': entries,
            'contains_original_programs': False,
            'restore': 'Extract into the source root without replacing newer code.'},
            ensure_ascii=False, indent=2) + '\n')
    with zipfile.ZipFile(temporary) as archive:
        assert archive.testzip() is None
    temporary.replace(OUT)
    result = {'file_name': OUT.name, 'bytes': OUT.stat().st_size, 'sha256': digest(OUT),
              'files': len(files), 'source_bytes': sum(x['bytes'] for x in entries),
              'contains_original_programs': False, 'extract_at_source_root': True,
              'metadata_included': ['world_manifest.json', 'ui_manifest.json']}
    (ROOT / 'reconstruction/security/PORT_3D_MEDIA_RECOVERY.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
