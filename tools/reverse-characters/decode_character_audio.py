#!/usr/bin/env python3
"""Preserve original FSB resources and decode character-referenced AudioClips to verified WAV."""
import hashlib,io,json,re,wave
from pathlib import Path
from collections import defaultdict
import gc
import UnityPy
from UnityPy.helpers.ResourceReader import get_resource_data
ROOT=Path(__file__).resolve().parents[2]
GAME=ROOT/'malware-review/No.Im.not.a.Human.v1.3.18/No.Im.not.a.Human.v1.3.18/NoImNotAHuman_Data'
ASSET_MANIFEST=ROOT/'reconstruction/reverse-characters/exported_character_assets/manifest.json'
OUT=ROOT/'reconstruction/reverse-characters/exported_audio'
def safe(x):return re.sub(r'[^A-Za-z0-9._-]+','_',str(x)).strip('._')[:90] or 'unnamed'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 manifest=json.loads(ASSET_MANIFEST.read_text());clips=[e for e in manifest['exports'] if e['object_type']=='AudioClip']
 by_source=defaultdict(list)
 for item in clips:by_source[item['source_file']].append(item)
 (OUT/'original_fsb').mkdir(parents=True,exist_ok=True);(OUT/'decoded_wav').mkdir(parents=True,exist_ok=True);rows=[];errors=[]
 for source,source_clips in sorted(by_source.items()):
  # The same two source files back the character configs; retain only one
  # UnityPy environment at a time to cap peak memory.
  env=UnityPy.load(str(GAME/source));objects={o.path_id:o for o in env.objects}
  for item in source_clips:
   pid=item['path_id'];obj=objects.get(pid)
   if obj is None:errors.append({'source_file':source,'path_id':pid,'error':'AudioClip pathID missing'});continue
   data=obj.read();stem=f'{Path(source).stem}_{pid}_{safe(item["name"])}'
   row={'source_file':source,'path_id':pid,'name':item['name'],'unity_length_seconds':float(data.m_Length),'unity_channels':data.m_Channels,'unity_frequency_hz':data.m_Frequency,'unity_compression_format':data.m_CompressionFormat}
   try:
    if data.m_AudioData:original=bytes(data.m_AudioData)
    elif data.m_Resource:
     r=data.m_Resource;original=get_resource_data(r.m_Source,data.object_reader.assets_file,r.m_Offset,r.m_Size)
    else:original=b''
    if original:
     ext='.fsb' if original[:4]==b'FSB5' else '.audio.bin';p=OUT/'original_fsb'/f'{stem}{ext}';p.write_bytes(original)
     row['original']={'path':str(p.relative_to(OUT)),'bytes':len(original),'sha256':sha(original),'magic_hex':original[:8].hex(),'format':'FSB5' if original[:4]==b'FSB5' else 'raw-unidentified'}
    else:row['original']=None
   except Exception as e:row['original_error']=repr(e)
   try:
    samples=data.samples
    if len(samples)!=1:raise ValueError(f'expected one decoded sample, got {len(samples)}')
    sample_name,sample=next(iter(samples.items()))
    if not sample.startswith(b'RIFF') or sample[8:12]!=b'WAVE':raise ValueError('decoder output is not a RIFF/WAVE stream')
    with wave.open(io.BytesIO(sample),'rb') as w:
     actual={'duration_seconds':w.getnframes()/w.getframerate(),'channels':w.getnchannels(),'sample_rate_hz':w.getframerate(),'sample_width_bytes':w.getsampwidth(),'frames':w.getnframes()}
    if actual['channels']!=data.m_Channels or actual['sample_rate_hz']!=data.m_Frequency:raise ValueError('WAV channel/sample-rate mismatch')
    if abs(actual['duration_seconds']-float(data.m_Length))>0.002:raise ValueError('WAV duration differs from Unity metadata')
    p=OUT/'decoded_wav'/f'{stem}.wav';p.write_bytes(sample)
    row['decoded']={'path':str(p.relative_to(OUT)),'source_sample_name':sample_name,'bytes':len(sample),'sha256':sha(sample),'metadata_match':True,**actual}
   except Exception as e:row['decode_error']=repr(e);errors.append({'source_file':source,'path_id':pid,'name':item['name'],'error':repr(e)})
   rows.append(row)
  del objects,env
  gc.collect()
 report={'method':'UnityPy static AudioClip.samples decoding to WAV with independent duration/sample-rate/channel validation; exact original referenced resource bytes and SHA256 preserved. Owner asset files loaded one at a time. No original executable code was run.','audio_clip_count':len(clips),'exported_count':len(rows),'decoded_wav_count':sum('decoded' in r for r in rows),'original_fsb_count':sum(r.get('original',{}).get('format')=='FSB5' for r in rows),'errors':errors,'records':rows,'validation_samples':[r['name'] for r in rows if r.get('decoded')][:3]}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps({k:report[k] for k in ('audio_clip_count','exported_count','decoded_wav_count','original_fsb_count','errors')},ensure_ascii=False))
 if errors or len(rows)!=len(clips):raise SystemExit(1)
if __name__=='__main__':main()
