#!/usr/bin/env python3
"""Restore damaged staged world PNGs from the hash-locked original media export."""
import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'reconstruction/android-current/app/src/main/assets'
BUNDLE_SHA = 'ce0245d3206a8119a8883158fe99290c15b95ccfda03df848c4b9428809286dc'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def validate(data):
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        image.load()

def repair(bundle, assets):
    assert sha(bundle.read_bytes()) == BUNDLE_SHA, 'Unexpected source media bundle'
    manifest = json.loads((assets / 'world/world_manifest.json').read_text())
    fixed = []
    with zipfile.ZipFile(bundle) as archive:
        for row in manifest['textures']:
            relative = Path(row['android_asset'])
            assert not relative.is_absolute() and '..' not in relative.parts
            target = assets / relative
            data = target.read_bytes()
            if sha(data) == row['android_sha256']:
                validate(data)
                continue
            original = archive.read('reconstruction/reverse-world/' + row['source_asset'])
            assert sha(original) == row['source_sha256'], 'Source texture hash mismatch'
            with Image.open(io.BytesIO(original)) as image:
                image.load()
                resized = image.copy()
            resized.thumbnail((1024,1024), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            resized.save(output, format='PNG', optimize=False, compress_level=9)
            restored = output.getvalue()
            validate(restored)
            assert sha(restored) == row['android_sha256'], 'Non-reproducible texture output'
            temporary = target.with_suffix('.png.stage-tmp')
            temporary.write_bytes(restored)
            temporary.replace(target)
            fixed.append({'asset':relative.as_posix(),'damaged_sha256':sha(data),'restored_sha256':sha(restored)})
    pngs = list(assets.rglob('*.png'))
    for path in pngs:
        validate(path.read_bytes())
    return {'repaired':fixed,'fully_decoded_png_count':len(pngs),'invalid_png_count':0}

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle',type=Path)
    parser.add_argument('--assets',type=Path,default=ASSETS)
    parser.add_argument('--report',type=Path,default=ROOT/'reconstruction/android-current/texture_repair_report.json')
    args=parser.parse_args()
    result=repair(args.bundle,args.assets)
    args.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
