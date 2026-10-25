#!/usr/bin/env python3
"""Extract printable strings from the statically serialized Yarn MonoBehaviour blob."""
import json, re, sys
from pathlib import Path
import UnityPy
src=Path(sys.argv[1]).resolve(); out=Path(sys.argv[2]).resolve(); out.mkdir(parents=True,exist_ok=True)
env=UnityPy.load(str(src))
rows=[]
for o in env.objects:
 if o.type.name!='MonoBehaviour': continue
 raw=o.get_raw_data()
 if b'Yarn.Internal.' not in raw and b'YarnProject' not in raw: continue
 strings=[]
 for m in re.finditer(rb'[\x20-\x7e]{4,}',raw):
  s=m.group().decode('utf-8','replace')
  strings.append({'offset':m.start(),'text':s})
 blob=out/f'monobehaviour_{o.path_id}.bin'; blob.write_bytes(raw)
 dest=out/f'monobehaviour_{o.path_id}_strings.json'; dest.write_text(json.dumps(strings,ensure_ascii=False,indent=2),encoding='utf8')
 rows.append({'path_id':o.path_id,'type':o.type.name,'serialized_bytes':len(raw),'raw_blob':blob.name,'string_dump':dest.name,'printable_strings':len(strings),'unique_printable_strings':len(set(r['text'] for r in strings))})
(out/'manifest.json').write_text(json.dumps({'source':str(src),'method':'Static printable-string extraction from Unity serialized objects; raw data preserved; no game code run','objects':rows,'limitations':'This preserves embedded strings and raw compiled bytes but does not decode Yarn bytecode/instruction operands into a fully validated executable graph.'},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(rows,indent=2))
