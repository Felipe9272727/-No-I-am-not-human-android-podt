#!/usr/bin/env python3
import hashlib,json,struct
from pathlib import Path
root=Path(__file__).resolve().parents[2]/'reconstruction/reverse-world';d=json.loads((root/'world_manifest.json').read_text())
for m in d['meshes']:
 b=(root/m['mesh_asset']).read_bytes();assert hashlib.sha256(b).hexdigest()==m['sha256'];assert len(b)==m['vertex_count']*32+m['index_count']*4
 ix=struct.unpack_from('<'+'I'*m['index_count'],b,m['vertex_count']*32);assert not ix or max(ix)<m['vertex_count']
for t in d['textures']:assert hashlib.sha256((root/t['asset']).read_bytes()).hexdigest()==t['sha256']
for r in d['renderers']:
 if r['mesh_index'] is not None:assert len(r['material_indices'])==len(d['meshes'][r['mesh_index']]['submeshes'])
assert not d['errors'],d['errors']
print('validated',len(d['meshes']),'meshes,',len(d['textures']),'textures,',len(d['renderers']),'renderers')
