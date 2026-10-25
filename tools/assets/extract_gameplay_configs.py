#!/usr/bin/env python3
"""Statically inspect serialized Unity ScriptableObjects using local Cpp2IL layouts.
Only raw asset parsing; no game executable or native library is executed.
"""
import glob, json, re, struct, sys
from pathlib import Path
import UnityPy

GAME=Path(sys.argv[1]).resolve()
OUT=Path(sys.argv[2]).resolve(); RAW=OUT/'raw'; RAW.mkdir(parents=True,exist_ok=True)
DATA=GAME/'NoImNotAHuman_Data'

# globalgamemanagers.assets is external fileID 1 for sharedassets files and contains MonoScript class names.
manager=UnityPy.load(str(DATA/'globalgamemanagers.assets'))
script_by_id={}
for o in manager.objects:
    if o.type.name=='MonoScript':
        try:
            d=o.read(); script_by_id[o.path_id]={'class':d.m_ClassName,'namespace':d.m_Namespace,'assembly':d.m_AssemblyName,'name':d.m_Name}
        except Exception: pass

def pptr(b,off):
    fid=struct.unpack_from('<i',b,off)[0]
    path=struct.unpack_from('<q',b,off+4)[0]
    return {'file_id':fid,'path_id':path}
def base_header(o):
    b=o.get_raw_data()
    fid=struct.unpack_from('<i',b,16)[0]; script_id=struct.unpack_from('<q',b,20)[0]
    n=struct.unpack_from('<I',b,28)[0]
    if n>len(b)-32: raise ValueError('invalid m_Name length')
    name=b[32:32+n].decode('utf-8','replace')
    start=(32+n+3)&~3
    sd=script_by_id.get(script_id,{}) if fid==1 else {}
    return b,name,start,{'class_id':o.class_id,'type_id':o.type_id,'script_ref':{'file_id':fid,'path_id':script_id},'script':sd}
def arr_int(b,off):
    n=struct.unpack_from('<i',b,off)[0]; off+=4
    if n<0 or n>(len(b)-off)//4: raise ValueError(f'invalid int array length {n} at {off-4}')
    a=list(struct.unpack_from('<'+'i'*n,b,off)) if n else []
    return a,off+4*n
def arr_float(b,off):
    n=struct.unpack_from('<i',b,off)[0]; off+=4
    if n<0 or n>(len(b)-off)//4: raise ValueError(f'invalid float array length {n} at {off-4}')
    a=list(struct.unpack_from('<'+'f'*n,b,off)) if n else []
    return a,off+4*n

def read_enum(path):
    txt=Path(path).read_text(encoding='utf8')
    return {int(v):k for k,v in re.findall(r'^\s*(\w+)\s*=\s*(-?\d+)\s*,?\s*$',txt,re.M)}
root=Path('/workspace/scratch/ad0b61c5ef81/reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code')
enums={
 'character_type':read_enum(root/'Characters/ECharacterType.cs'),
 'room':read_enum(root/'Rooms/ERoom.cs'),
 'character_place':read_enum(root/'Characters/ECharacterPlace.cs'),
 'room_people_state':read_enum(root/'Rooms/ERoomPeopleState.cs'),
 'time_of_day':read_enum(root/'Events/ETimeOfDay.cs'),
}
# Core asset names for resolving local fileID=0 refs.
asset_by_file={}
component_by_file={}
for fp in [DATA/'sharedassets0.assets',DATA/'sharedassets1.assets']:
    try:
        env=UnityPy.load(str(fp)); asset_by_file[fp.name]={}; component_by_file[fp.name]={}
        for obj in env.objects:
            if obj.type.name=='MonoBehaviour':
                try:
                    rb=obj.get_raw_data(); nf=struct.unpack_from('<I',rb,28)[0]; nm=rb[32:32+nf].decode('utf-8','replace')
                    sf=struct.unpack_from('<i',rb,16)[0]; sp=struct.unpack_from('<q',rb,20)[0]; sc=script_by_id.get(sp,{}) if sf==1 else {}
                    component_by_file[fp.name][obj.path_id]={'type':(sc.get('namespace','')+'.'+sc.get('class','')).strip('.'),'name':nm}
                except Exception:pass
            if obj.type.name in ('Sprite','Material','AudioClip','Texture2D'):
                try: asset_by_file[fp.name][obj.path_id]={'type':obj.type.name,'name':obj.peek_name()}
                except Exception: pass
    except Exception: pass

def refinfo(ref,file):
    result=dict(ref); result['resolved']=None
    if ref['file_id']==0: result['resolved']=component_by_file.get(file,{}).get(ref['path_id']) or asset_by_file.get(file,{}).get(ref['path_id'])
    elif ref['file_id']==1: result['resolved']=script_by_id.get(ref['path_id'])
    return result

objects=[]; chars=[]; dayconfigs=[]; simple_configs=[]; resource_mothers=[]; unknown_event_objects=[]
for fp in sorted(glob.glob(str(DATA/'sharedassets*.assets'))+glob.glob(str(DATA/'level*'))):
    try: env=UnityPy.load(fp)
    except Exception: continue
    for o in env.objects:
        if o.type.name!='MonoBehaviour': continue
        try: b,name,cursor,meta=base_header(o)
        except Exception: continue
        cls=meta['script'].get('class','')
        namespace=meta['script'].get('namespace','')
        fq=f'{namespace}.{cls}'
        if cls not in {'CharacterSOData','DayNightControllerSOData','GameEventsManagerSOData','RandomGenerationSettingsSOData','ResourceMother'}:
            if ('Event' in cls or 'Event' in namespace) and len(b)>60:
                unknown_event_objects.append({'source_file':Path(fp).name,'path_id':o.path_id,'name':name,'class':fq,'raw_bytes':len(b)})
            continue
        rawdest=RAW/f'{Path(fp).stem}_{o.path_id}_{name}.bin'
        rawdest.write_bytes(b)
        common={'source_file':Path(fp).name,'path_id':o.path_id,'name':name,'class':fq,'raw_bytes':len(b),'raw_dump':str(rawdest.relative_to(OUT)),'script_ref':meta['script_ref']}
        try:
            if cls=='CharacterSOData':
                # CharacterSOData serialized prefix from Cpp2IL declaration: enum, RoomObjectState<ERoomPeopleState>[];
                val=struct.unpack_from('<i',b,cursor)[0]; cursor+=4
                count=struct.unpack_from('<i',b,cursor)[0]; cursor+=4
                if count<0 or count>128 or cursor+36*count>len(b): raise ValueError(f'invalid _poses array count {count}')
                poses=[]
                for _ in range(count):
                    state=struct.unpack_from('<i',b,cursor)[0]; cursor+=4
                    sprite=pptr(b,cursor); cursor+=12
                    pos=struct.unpack_from('<2f',b,cursor); cursor+=8
                    scale=struct.unpack_from('<2f',b,cursor); cursor+=8
                    cannot=bool(b[cursor]); cursor=(cursor+4)&~3
                    poses.append({'name_value':state,'name':enums['room_people_state'].get(state,f'Unknown({state})'),'sprite':refinfo(sprite,Path(fp).name),'position_shift':list(pos),'scale_shift':list(scale),'cannot_interact':cannot})
                emotions_count=struct.unpack_from('<i',b,cursor)[0] if cursor+4<=len(b) else None
                chars.append({**common,'character_type_value':val,'character_type':enums['character_type'].get(val,f'Unknown({val})'),'poses':poses,'emotions_count_at_next_serialized_field':emotions_count,'parsed_through':'_poses','unparsed_field_boundary':'_emotions is [SerializeReference]; all following fields are preserved in raw_dump but not decoded'})
            elif cls=='DayNightControllerSOData':
                data={}
                n=struct.unpack_from('<i',b,cursor)[0];cursor+=4
                if n<0 or n>32 or cursor+24*n>len(b):raise ValueError(f'invalid _volumeProfiles length {n}')
                profiles=[]
                for _ in range(n):
                    t=struct.unpack_from('<i',b,cursor)[0];cursor+=4
                    ptr=pptr(b,cursor);cursor+=12
                    light=bool(b[cursor]);cursor=(cursor+4)&~3
                    actions=bool(b[cursor]);cursor=(cursor+4)&~3
                    profiles.append({'time_of_day_value':t,'time_of_day':enums['time_of_day'].get(t,f'Unknown({t})'),'volume_profile':refinfo(ptr,Path(fp).name),'has_light':light,'has_actions_count':actions})
                data['volume_profiles']=profiles
                mats=[]
                for field in ['light_beam_night_material','light_beam_day_material','fullscreen_effect_material','window_material']:
                    ptr=pptr(b,cursor);cursor+=12;mats.append({'field':field,**refinfo(ptr,Path(fp).name)})
                data['material_refs']=mats
                data['max_day_actions_by_days'],cursor=arr_int(b,cursor)
                data['lens_distortion_by_days'],cursor=arr_float(b,cursor)
                data['colors_count_by_days'],cursor=arr_int(b,cursor)
                fields=['last_day','baby_ending_day','killer_ending_day','fema_ending_day','coffee_boost_days']
                for field in fields:data[field]=struct.unpack_from('<i',b,cursor)[0];cursor+=4
                data['parsed_bytes_end']=cursor;data['unparsed_tail_bytes']=len(b)-cursor
                dayconfigs.append({**common,**data})
            elif cls=='ResourceMother':
                # ResourceMother is the production wiring asset; its field order is explicit in Cpp2IL.
                names=['day_night_controller_data','game_events_manager_data','other_game_data']
                refs={}
                for field in names: refs[field]=refinfo(pptr(b,cursor),Path(fp).name); cursor+=12
                def ref_array(field):
                    nonlocal_cursor=None
                    nonlocal_dummy=0
                    nonlocal_cursor=0
                    return None
                count=struct.unpack_from('<i',b,cursor)[0];cursor+=4
                if count<0 or count>512 or cursor+count*12>len(b):raise ValueError(f'invalid characters data array count {count}')
                characters=[]
                for i in range(count):
                    ref=refinfo(pptr(b,cursor),Path(fp).name);cursor+=12;ref['order']=i;characters.append(ref)
                refs['characters_data']=characters
                for field in ['cursor_data','random_generation_settings_data','windows_data']:
                    refs[field]=refinfo(pptr(b,cursor),Path(fp).name);cursor+=12
                count=struct.unpack_from('<i',b,cursor)[0];cursor+=4
                if count<0 or count>256 or cursor+count*12>len(b):raise ValueError(f'invalid endings array count {count}')
                refs['ending_views_data']=[refinfo(pptr(b,cursor+i*12),Path(fp).name) for i in range(count)];cursor+=count*12
                refs['endings_data']=refinfo(pptr(b,cursor),Path(fp).name);cursor+=12
                count=struct.unpack_from('<i',b,cursor)[0];cursor+=4
                if count<0 or count>256 or cursor+count*12>len(b):raise ValueError(f'invalid cutscenes array count {count}')
                refs['cutscenes_data']=[refinfo(pptr(b,cursor+i*12),Path(fp).name) for i in range(count)];cursor+=count*12
                refs['random_sounds_emitter_data']=refinfo(pptr(b,cursor),Path(fp).name);cursor+=12
                refs['music_data']=refinfo(pptr(b,cursor),Path(fp).name);cursor+=12
                resource_mothers.append({**common,'references':refs,'parsed_bytes_end':cursor,'unparsed_tail_bytes':len(b)-cursor})
            elif cls=='GameEventsManagerSOData':
                names=['min_delay_before_ding_dong_first_guest','max_delay_before_ding_dong_first_guest','min_delay_before_ding_dong_guest','max_delay_before_ding_dong_guest']
                vals=list(struct.unpack_from('<4f',b,cursor));simple_configs.append({**common,**dict(zip(names,vals)),'parsed_through':'all declared primitive fields','unparsed_tail_bytes':len(b)-cursor-16})
            elif cls=='RandomGenerationSettingsSOData':
                arr,cursor=arr_int(b,cursor);minp=struct.unpack_from('<f',b,cursor)[0];maxp=struct.unpack_from('<f',b,cursor+4)[0];cursor+=8
                simple_configs.append({**common,'random_guests_number_by_nights':arr,'min_imposters_percent':minp,'max_imposters_percent':maxp,'parsed_through':'all declared primitive fields','unparsed_tail_bytes':len(b)-cursor})
        except Exception as e:
            objects.append({**common,'parse_error':repr(e)})

report={'method':'Raw Unity serialized object decoding using MonoBehaviour base header and local Cpp2IL-generated field/type declarations; UnityPy used to enumerate files and asset references only. No binary execution.','source_data_file':'NoImNotAHuman_Data/sharedassets*.assets and level*','schema_sources':['_Code/Characters/CharacterSOData.cs','_Code/Infrastructure/DayNightControllerSOData.cs','_Code/Infrastructure/Randomization/RandomGenerationSettingsSOData.cs','_Code/Infrastructure/GameEvents/GameEventsManagerSOData.cs'],'enum_sources':['_Code/Characters/ECharacterType.cs','_Code/Characters/ECharacterPlace.cs','_Code/Rooms/ERoom.cs','_Code/Rooms/ERoomPeopleState.cs','_Code/Events/ETimeOfDay.cs'],'character_records':chars,'day_night_controller_records':dayconfigs,'simple_config_records':simple_configs,'resource_mother_records':resource_mothers,'parse_errors':objects,'ui_components_matching_event_substring':unknown_event_objects,'serialized_gameplay_events_found':[],'gameplay_event_config_objects_found':0,'limitations':['CharacterSOData extraction currently decodes exact character type and pose array fields; SerializeReference emotion data, SerializedDictionary, LocalizedString and later fields are stored in per-object raw dumps and are not represented in the normalized JSON.','No separate initial-character list or top-level event-condition asset type has been identified yet; event object inventory records candidate class names and raw sizes.']}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'production_configs.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'characters':len(chars),'day_configs':len(dayconfigs),'simple_configs':len(simple_configs),'resource_mothers':len(resource_mothers),'errors':len(objects),'event_candidates':len(unknown_event_objects),'resource_mother_chars': [len(x['references']['characters_data']) for x in resource_mothers],'day_values':[{k:v for k,v in x.items() if k in ('name','max_day_actions_by_days','last_day','baby_ending_day','killer_ending_day','fema_ending_day','coffee_boost_days')} for x in dayconfigs]},ensure_ascii=False))
