#!/usr/bin/env python3
"""Structural/source-ID validation for scene_render_manifest.json."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'reconstruction/reverse-scenes/scene_render_manifest.json'
d=json.loads(p.read_text()); errors=[]
def require(ok,msg):
    if not ok: errors.append(msg)
require(d.get('schema_version')==1,'schema_version must be 1')
require(len(d.get('room_character_instances',[]))==d.get('counts',{}).get('room_character_instances'),'room instance count mismatch')
require(len(d.get('characters',[]))==d.get('counts',{}).get('unique_characters'),'character count mismatch')
seen=set()
for r in d.get('room_character_instances',[]):
    key=(r['room'],r['component']['path_id']); require(key not in seen,f'duplicate room component {key}');seen.add(key)
    require(r['component']['class']=='_Code.Rooms.CharacterRoomObjectView',f"wrong component class for {key}")
    pose=r.get('initial_pose'); require(pose is not None,f'missing initial pose for {key}')
    if pose: require(pose['state_value']==r['component']['start_state_value'],f'initial pose mismatch for {key}')
    require(len(r['poses'])>0,f'no pose rows for {key}')
require(d['counts']['dialog_views']==len(d['dialog_views']),'dialog view count mismatch')
require(d['counts']['dialog_signs_views']==len(d['dialog_signs_views']),'sign view count mismatch')
for x in d['dialog_signs_views']:
    require(len(x['serialized_fields'])==8,'DialogSignsView must have eight scene refs')
    require(x['serialized_end_offset']==x['raw_size'],'DialogSignsView serialized size not fully consumed')
for x in d['dialog_views']:
    require(x['serialized_fields']['reserve_camera']['path_id'] in {c['path_id'] for c in d['cameras']},'DialogView reserve camera unresolved')
    require(x['serialized_fields']['character_animated_image']['class']=='_Code.Utils.UI.ImageAnimating.AnimatedImage','dialog character component unresolved')
for s in d['canvas_scalers']:
    require(s['raw_size']==80,f"unexpected CanvasScaler size at {s['component_path_id']}")
    require(len(s['reference_resolution'])==2,'CanvasScaler reference resolution malformed')
assets_path=ROOT/'reconstruction/reverse-characters/exported_character_assets/manifest.json'
if assets_path.exists():
    assets=json.loads(assets_path.read_text())
    exported={(x['source_file'],int(x['file_id']),int(x['path_id'])) for x in assets['exports']}
    refs=set()
    def harvest(value,source):
        if isinstance(value,dict):
            if {'file_id','path_id'}<=set(value) and value.get('path_id'):
                refs.add((source,int(value['file_id']),int(value['path_id'])))
            else:
                for v in value.values():harvest(v,source)
        elif isinstance(value,list):
            for v in value:harvest(v,source)
    for c in d['characters']:
        harvest(c.get('examination_assets',{}),c['source']['file'])
        harvest(c.get('emotions',[]),c['source']['file'])
    for r in d['room_character_instances']:
        harvest(r['poses'],'sharedassets0.assets')
    missing=refs-exported
    require(not missing,f'{len(missing)} character room/examination PPtrs have no exported asset; sample={sorted(missing)[:5]}')
scene_assets=ROOT/'reconstruction/reverse-scenes/exported_scene_assets/manifest.json'
if scene_assets.exists():
    extra=json.loads(scene_assets.read_text())
    require(not extra.get('errors'),f"scene Sprite extraction has errors: {extra.get('errors')[:3]}")
    require(extra.get('exported_count')==len(extra.get('exports',[])),'scene Sprite export count mismatch')
if errors:
    print('\n'.join(errors));sys.exit(1)
print(json.dumps({'status':'ok','room_character_instances':len(d['room_character_instances']),'unique_characters':len(d['characters']),'dialog_views':len(d['dialog_views']),'sign_views':len(d['dialog_signs_views']),'canvas_scalers':len(d['canvas_scalers']),'character_asset_refs_validated':len(refs) if assets_path.exists() else None},indent=2))
