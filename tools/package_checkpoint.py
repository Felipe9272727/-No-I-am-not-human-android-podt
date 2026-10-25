#!/usr/bin/env python3
"""Package recovered data and source, excluding Windows programs and build caches."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'deliverables/NINAH-Reconstrucao-Rust-Checkpoint.zip'
SKIP_DIRS = {'target', 'build', '.gradle', '.git', '__pycache__', 'jniLibs'}
FORBIDDEN = {'.exe', '.dll', '.rne', '.msi', '.url', '.apk', '.so', '.a', '.o', '.keystore', '.jks', '.pyc', '.class', '.dex', '.jar'}


def eligible(path):
    relative = path.relative_to(ROOT)
    return (path.is_file() and not path.is_symlink()
            and not ('exported_intro' in relative.parts and path.suffix.lower() == '.mp4')
            and not ('android-current' in relative.parts and 'assets' in relative.parts)
            and not any(part in SKIP_DIRS or part.startswith('build-') for part in relative.parts)
            and not any(part.startswith('.') and part != '.gitignore' for part in relative.parts)
            and path.suffix.lower() not in FORBIDDEN)


def main():
    files = set()
    for name in ('assets', 'narrative', 'security', 'mobile-runtime', 'yarn-runtime', 'game-state',
                 'native-game', 'reverse-characters', 'reverse-endings', 'reverse-progression',
                 'reverse-occupants', 'reverse-phone', 'reverse-rooms', 'reverse-events', 'reverse-services',
                 'reverse-localization', 'reverse-bootstrap', 'reverse-scenes', 'android-current'):
        files.update(p for p in (ROOT / 'reconstruction' / name).rglob('*') if eligible(p))
    for name in ('LEIA-ME.md', 'TESTES.md', 'VALIDATION.json'):
        files.add(ROOT / 'reconstruction' / name)
    logic = ROOT / 'reconstruction/logic'
    files.update(p for p in logic.iterdir() if eligible(p) and p.suffix in ('.md', '.il', '.txt', '.json'))
    files.update(p for p in (logic / 'cpp2il_cs/DiffableCs/Assembly-CSharp').rglob('*.cs') if eligible(p))
    files.update(p for p in (logic / 'recovered_isil/Assembly-CSharp').rglob('*.txt') if eligible(p))
    for name in ('assets', 'logic', 'narrative', 'security', 'native-game', 'reverse-characters',
                 'reverse-endings', 'reverse-progression', 'reverse-occupants', 'reverse-phone',
                 'reverse-rooms', 'reverse-events', 'reverse-services', 'reverse-localization',
                 'reverse-bootstrap', 'reverse-scenes', 'android-current'):
        files.update(p for p in (ROOT / 'tools' / name).glob('*.py') if eligible(p))
    for name in ('package_checkpoint.py', 'validate_reconstruction.py'):
        files.add(ROOT / 'tools' / name)

    entries = []
    OUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUT.with_suffix('.zip.partial')
    with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr('README.md', '# Reconstrução Android em C++ e Rust\n\nLeia `reconstruction/LEIA-ME.md` e `reconstruction/native-game/RECUPERACAO.md` para o estado real do trabalho. Este checkpoint preserva os módulos C++ recuperados após o reinício do ambiente; ainda não contém um APK completo jogável.\n')
        for path in sorted(files):
            with path.open('rb') as stream:
                prefix = stream.read(4)
                assert prefix[:2] != b'MZ', ('Windows PE excluded from checkpoint', path)
                assert prefix != b'\x7fELF', ('Prebuilt native executable excluded from checkpoint', path)
            relative = str(path.relative_to(ROOT))
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            entries.append({'path': relative, 'bytes': path.stat().st_size, 'sha256': digest})
            archive.write(path, relative)
        archive.writestr('CHECKPOINT_MANIFEST.json', json.dumps({'files': entries, 'contains_original_windows_programs': False}, ensure_ascii=False, indent=2) + '\n')
    with zipfile.ZipFile(temporary) as archive:
        failure = archive.testzip()
        assert failure is None, ('Archive failed CRC verification', failure)
    temporary.replace(OUT)
    print(json.dumps({'file': str(OUT), 'files': len(entries), 'source_bytes': sum(e['bytes'] for e in entries), 'zip_bytes': OUT.stat().st_size}, ensure_ascii=False))


if __name__ == '__main__':
    main()
