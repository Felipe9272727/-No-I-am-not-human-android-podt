#!/usr/bin/env python3
"""Export only referenced room backgrounds and dialog overlay Sprite PPtrs."""
import json,re,gc,argparse
from collections import defaultdict
from pathlib import Path
import UnityPy
ROOT=Path(__file__).resolve().parents[2]
def safe(s):return re.sub(r'[^A-Za-z0-9._-]+','_',str(s)).strip('._')[:90] or 'unnamed'
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',type=Path,required=True);ap.add_argument('--out',type=Path,default=ROOT/'reconstruction/reverse-scenes/exported_scene_assets');a=ap.parse_args()
    rooms=json.loads((ROOT/'reconstruction/reverse-rooms/room_manifest.json').read_text())
    scene=json.loads((ROOT/'reconstruction/reverse-scenes/scene_render_manifest.json').read_text())
    char_assets=json.loads((ROOT/'reconstruction/reverse-characters/exported_character_assets/manifest.json').read_text())
    present={(x['source_file'],int(x['file_id']),int(x['path_id'])) for x in char_assets['exports']}
    refs=defaultdict(set)
    for room in rooms['rooms']:
        for bg in room['background_images']:
            p=bg.get('sprite',{}).get('pointer',{});src=p.get('file')
            if src and p.get('path_id'):refs[(src,int(p.get('file_id',0)),int(p['path_id']))].add('room_background:'+room['room'])
    for d in scene['dialog_views']:
        for ov in d['dialog_overlays']:
            p=ov['sprite'];src=p.get('file')
            if src and p.get('path_id'):refs[(src,int(p['file_id']),int(p['path_id']))].add('dialog_overlay:'+str(ov['array_index']))
    missing={k:v for k,v in refs.items() if k not in present}
    out=a.out.resolve();(out/'images').mkdir(parents=True,exist_ok=True); exports=[];errors=[]
    by_source=defaultdict(list)
    for key,roles in missing.items():by_source[key[0]].append((key,roles))
    for source in sorted(by_source):
        path=a.data/source
        if not path.is_file():errors.append({'source_file':source,'error':'owner asset file missing'});continue
        env=UnityPy.load(str(path)); objects={int(o.path_id):o for o in env.objects}
        for (src,fid,pid),roles in sorted(by_source[source]):
            obj=objects.get(pid)
            if obj is None:errors.append({'source_file':src,'file_id':fid,'path_id':pid,'roles':sorted(roles),'error':'Sprite PPtr unresolved'});continue
            if obj.type.name!='Sprite':errors.append({'source_file':src,'file_id':fid,'path_id':pid,'roles':sorted(roles),'object_type':obj.type.name,'error':'referenced object is not Sprite'});continue
            data=obj.read(); name=str(data.m_Name); dest=out/'images'/f'{Path(src).stem}_{pid}_{safe(name)}.png';data.image.save(dest)
            exports.append({'source_file':src,'file_id':fid,'path_id':pid,'name':name,'object_type':'Sprite','roles':sorted(roles),'output':str(dest.relative_to(out)),'width':data.image.width,'height':data.image.height,'bytes':dest.stat().st_size})
        del objects,env;gc.collect()
    result={'method':'UnityPy static Sprite extraction of exact room background and DialogView overlay PPtrs missing from exported_character_assets; each owner asset loaded sequentially; no game PE executed.','source_files':sorted(by_source),'missing_from_character_export':len(missing),'exported_count':len(exports),'exports':exports,'errors':errors}
    out.mkdir(parents=True,exist_ok=True);(out/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'missing_from_character_export':len(missing),'exported':len(exports),'errors':len(errors),'output':str(out/'manifest.json')},indent=2))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
