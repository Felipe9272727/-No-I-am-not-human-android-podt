#!/usr/bin/env python3
"""Static UnityPy exporter for selected game art and localization tables.
Does not execute game binaries, assemblies, or installers."""
import json, os, re, sys
from pathlib import Path
import UnityPy

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
AA = ROOT / 'NoImNotAHuman_Data/StreamingAssets/aa/StandaloneWindows64'
LOC_OUT = OUT / 'localization'
IMG_OUT = OUT / 'images'
LOC_OUT.mkdir(parents=True, exist_ok=True)
IMG_OUT.mkdir(parents=True, exist_ok=True)

# Dump every localized string table from the 19 locale bundles.
loc_manifest = []
for fp in sorted(AA.glob('localization-string-tables-*_assets_all.bundle')):
    env = UnityPy.Environment()
    env.load_file(str(AA / 'localization-assets-shared_assets_all.bundle'))
    env.load_file(str(fp))
    tables = {}
    total = 0
    for obj in env.objects:
        if obj.type.name != 'MonoBehaviour':
            continue
        d = obj.read()
        name = getattr(d, 'm_Name', '')
        entries = getattr(d, 'm_TableData', None)
        if not name or entries is None:
            continue
        key_by_id = {}
        try:
            shared = d.m_SharedData.deref_parse_as_object()
            key_by_id = {int(x.m_Id): str(x.m_Key) for x in shared.m_Entries}
        except Exception:
            pass
        out_entries = []
        for e in entries:
            item = {'id': int(e.m_Id), 'text': str(e.m_Localized)}
            if int(e.m_Id) in key_by_id:
                item['key'] = key_by_id[int(e.m_Id)]
            out_entries.append(item)
        tables[name] = out_entries
        total += len(out_entries)
    locale = fp.name[len('localization-string-tables-'):-len('_assets_all.bundle')]
    dest = LOC_OUT / (re.sub(r'[^A-Za-z0-9._-]+', '_', locale) + '.json')
    dest.write_text(json.dumps({'source_bundle': fp.name, 'tables': tables}, ensure_ascii=False, indent=2), encoding='utf-8')
    loc_manifest.append({'locale': locale, 'source': str(fp.relative_to(ROOT)), 'output': str(dest.relative_to(OUT)), 'tables': len(tables), 'entries': total})

# Export actual sprites (UnityPy resolves sprite atlas/texture references and crops them).
shared = ROOT / 'NoImNotAHuman_Data/sharedassets0.assets'
env = UnityPy.load(str(shared))
selected = []
seen = set()
# Representative character portrait, TV cutaway, UI, and scene sprites. All extracted from actual Sprite objects.
patterns = [
    re.compile(r'^fake_(mother|neighbour|doctor|courier|teacher|tourist|vigilante|fortuneteller|prophet|volkodav|sanya|intruder|cold|tough|sunboy|bald|anger|nun|hunter|rocker|buddy|foreigner|undertaker|raskolnikov|esenin)\b.*_0$'),
    re.compile(r'^fake_tv_(firstday|weather1|ballet|fire|noise)_0$'),
    re.compile(r'^mainmenu_(teeth|eyes|mask|light)_0$'),
    re.compile(r'^Fake_collection_window_film_0$')]
for obj in env.objects:
    if obj.type.name != 'Sprite': continue
    d = obj.read(); nm = d.m_Name
    if nm in seen or not any(p.search(nm) for p in patterns): continue
    seen.add(nm)
    try:
        im = d.image
        if im is None: continue
        safe = re.sub(r'[^A-Za-z0-9._-]+', '_', nm)
        dest = IMG_OUT / (safe + '.png')
        im.save(dest)
        selected.append({'name': nm, 'path_id': obj.path_id, 'size': list(im.size), 'output': str(dest.relative_to(OUT)), 'source': str(shared.relative_to(ROOT))})
    except Exception as ex:
        selected.append({'name': nm, 'path_id': obj.path_id, 'error': repr(ex)})

manifest = {'method': 'UnityPy static asset parsing; no bundled executable or DLL was run', 'source_root': str(ROOT), 'localization': loc_manifest, 'exported_sprites': selected, 'source_sharedassets0_type_counts': {}}
from collections import Counter
manifest['source_sharedassets0_type_counts'] = dict(Counter(o.type.name for o in env.objects))
(OUT/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'locales': len(loc_manifest), 'localized_entries': sum(x['entries'] for x in loc_manifest), 'sprites': len(selected), 'files': [x['output'] for x in selected]}, ensure_ascii=False))
