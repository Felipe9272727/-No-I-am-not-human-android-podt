#!/usr/bin/env python3
"""Export only Sprite/Texture2D/AudioClip PPtrs present in recovered character data."""
import json,re
from collections import Counter,defaultdict
from pathlib import Path
import gc
import UnityPy
ROOT=Path(__file__).resolve().parents[2]
GAME=ROOT/'malware-review/No.Im.not.a.Human.v1.3.18/No.Im.not.a.Human.v1.3.18/NoImNotAHuman_Data'
CONFIG=ROOT/'reconstruction/reverse-characters/character_configs.json'
EMOTIONS=ROOT/'reconstruction/reverse-characters/emotion_registry.json'
OUT=ROOT/'reconstruction/reverse-characters/exported_character_assets'
def safe(x):return re.sub(r'[^A-Za-z0-9._-]+','_',str(x)).strip('._')[:90] or 'unnamed'
def harvest(value,source,roles,refs):
 if isinstance(value,dict):
  if {'file_id','path_id'}<=set(value) and value.get('path_id'):
   refs[(source,int(value['file_id']),int(value['path_id']))].update(roles);return
  for key,v in value.items():harvest(v,source,roles+(key,),refs)
 elif isinstance(value,list):
  for v in value:harvest(v,source,roles,refs)
def main():
 config=json.loads(CONFIG.read_text()); emotion=json.loads(EMOTIONS.read_text());refs=defaultdict(set)
 for row in config['records']:
  harvest(row.get('poses',[]),row['source_file'],('character',row['name'],'pose'),refs)
  harvest(row.get('assets',{}),row['source_file'],('character',row['name'],'asset'),refs)
 for row in emotion['records']:
  harvest(row.get('fields',{}),row['source_file'],('character',row['character'],'emotion',row['emotion_name']),refs)
 (OUT/'images').mkdir(parents=True,exist_ok=True);exports=[];errors=[];counts=Counter()
 source_files=sorted({r[0] for r in refs})
 by_source=defaultdict(list)
 for key,roles in refs.items():by_source[key[0]].append((key,roles))
 for source in source_files:
  # Character data references live in two shared asset files. Load one owner
  # file at a time so extraction does not retain both UnityPy object graphs.
  env=UnityPy.load(str(GAME/source));objects={o.path_id:o for o in env.objects}
  for (ref_source,fid,pid),roles in sorted(by_source[source]):
   if fid!=0:
    errors.append({'source_file':ref_source,'file_id':fid,'path_id':pid,'roles':sorted(roles),'error':'external PPtr not mapped'});continue
   obj=objects.get(pid)
   if obj is None:
    errors.append({'source_file':ref_source,'file_id':fid,'path_id':pid,'roles':sorted(roles),'error':'pathID missing in owner file'});continue
   typ=obj.type.name
   if typ not in ('Sprite','Texture2D','AudioClip'):
    errors.append({'source_file':ref_source,'path_id':pid,'object_type':typ,'roles':sorted(roles),'error':'referenced type is not a supported image/audio object'});continue
   name=obj.peek_name() or f'{typ}_{pid}';entry={'source_file':ref_source,'file_id':fid,'path_id':pid,'object_type':typ,'name':name,'roles':sorted(roles)}
   if typ=='AudioClip':
    data=obj.read();entry.update({'length_seconds':float(data.m_Length),'channels':data.m_Channels,'frequency':data.m_Frequency,'audio_manifest':'../exported_audio/manifest.json'})
   else:
    image=obj.read().image;dest=OUT/'images'/f'{Path(ref_source).stem}_{pid}_{safe(name)}.png';image.save(dest)
    entry.update({'output':str(dest.relative_to(OUT)),'width':image.width,'height':image.height,'bytes':dest.stat().st_size,'format':'PNG'})
   counts[typ]+=1;exports.append(entry)
  del objects,env
  gc.collect()
 report={'method':'Recursive harvest of all character-config and emotion-registry PPtrs, then UnityPy static extraction of only directly referenced Sprite, Texture2D, and AudioClip objects. Owner asset files are loaded one at a time; no game code executed. AudioClip samples and original resource bytes are handled by decode_character_audio.py.','source_files':source_files,'references_unique':len(refs),'exported_count':len(exports),'exported_by_type':dict(counts),'exports':exports,'errors':errors,'caveats':['PNG is UnityPy-decoded texture/sprite image data, not a mesh re-render.','AudioClip records link to a separately verified audio manifest.']}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps({'references_unique':len(refs),'exported':len(exports),'by_type':dict(counts),'errors':len(errors),'output':str(OUT)}))
 if errors:print(json.dumps(errors[:10],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
