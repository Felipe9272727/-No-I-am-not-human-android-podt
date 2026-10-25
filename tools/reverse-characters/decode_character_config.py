#!/usr/bin/env python3
"""Decode all serialized CharacterSOData fields and the managed-reference registry boundary."""
import json,math,re,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
INPUT=ROOT/'reconstruction/assets/gameplay_data/production_configs.json'
OUTPUT=ROOT/'reconstruction/reverse-characters/character_configs.json'
RAW=ROOT/'reconstruction/assets/gameplay_data'
CS=ROOT/'reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code'
def enum(path):return {int(v):k for k,v in re.findall(r'^\s*(\w+)\s*=\s*(-?\d+)\s*,?$',path.read_text(),re.M)}
ENUMS={
 'character_type':enum(CS/'Characters/ECharacterType.cs'),
 'room_people_state':enum(CS/'Rooms/ERoomPeopleState.cs'),
 'room':enum(CS/'Rooms/ERoom.cs'),
 'place':enum(CS/'Characters/ECharacterPlace.cs'),
 'sound':enum(CS/'Infrastructure/Sound/ESound.cs'),
 'emotion':enum(CS/'Characters/EDialogEmotionState.cs'),
 'animation_cycle':enum(CS/'Menues/HUD/Animations/EAnimationCyclingType.cs'),
}
class Reader:
 def __init__(self,b):self.b=b;self.o=0
 def need(self,n):
  if n<0 or self.o+n>len(self.b):raise ValueError(f'field crosses object end at {self.o:#x}')
 def align4(self):self.o=(self.o+3)&~3
 def i32(self):self.need(4);v=struct.unpack_from('<i',self.b,self.o)[0];self.o+=4;return v
 def i64(self):self.need(8);v=struct.unpack_from('<q',self.b,self.o)[0];self.o+=8;return v
 def f32(self):
  self.need(4);v=struct.unpack_from('<f',self.b,self.o)[0];self.o+=4
  if not math.isfinite(v):raise ValueError(f'non-finite float at {self.o-4:#x}')
  return v
 def boolean(self):
  self.need(1);v=self.b[self.o];self.o+=1
  if v not in (0,1):raise ValueError(f'invalid boolean {v} at {self.o-1:#x}')
  self.align4();return bool(v)
 def pptr(self):
  start=self.o;self.need(12);fid,pid=struct.unpack_from('<iq',self.b,self.o);self.o+=12
  return {'file_id':fid,'path_id':pid,'offset':start}
 def string(self):
  start=self.o;n=self.i32()
  if n<0 or n>65536:raise ValueError(f'invalid UTF8 string size {n} at {start:#x}')
  self.need(n)
  try:s=self.b[self.o:self.o+n].decode('utf8')
  except UnicodeDecodeError as e:raise ValueError(f'invalid UTF8 at {self.o:#x}: {e}')
  self.o+=n;self.align4();return s
 def count(self,label,lim=4096):
  at=self.o;n=self.i32()
  if n<0 or n>lim:raise ValueError(f'invalid {label} count {n} at {at:#x}')
  return n
 def vec2(self):return [self.f32(),self.f32()]
 def vec3(self):return [self.f32(),self.f32(),self.f32()]
 def localized(self):
  start=self.o;table=self.string();key_id=self.i64();key=self.string();fallback=self.i32();wait=self.boolean();n=self.count('localized local-variable')
  variables=[]
  for _ in range(n):variables.append({'name':self.string(),'id':self.i64()})
  return {'table_reference':table,'entry_key_id':key_id,'entry_key':key,'fallback_state_value':fallback,'wait_for_completion':wait,'local_variables':variables,'offset':start}
 def animation(self):
  start=self.o;cycle=self.i32();n=self.count('animation frame')
  frames=[self.pptr() for _ in range(n)];fps=self.i32()
  return {'cycling_type_value':cycle,'cycling_type':ENUMS['animation_cycle'].get(cycle,f'Unknown({cycle})'),'frames':frames,'frames_per_second':fps,'offset':start}
 def eye(self):
  start=self.o;white=self.pptr();iris=self.pptr();ease=self.i32();distance=self.f32();min_duration=self.f32();max_duration=self.f32()
  return {'white':white,'iris':iris,'easing_value':ease,'distance_multiplier':distance,'min_move_duration':min_duration,'max_move_duration':max_duration,'offset':start}
 def array_int(self,label):return [self.i32() for _ in range(self.count(label))]
 def array_vec3(self,label):return [self.vec3() for _ in range(self.count(label))]

def parse_registry(b,start,expected_ids):
 o=start;version,count=struct.unpack_from('<ii',b,o);o+=8
 if version!=2 or count!=len(expected_ids):raise ValueError('managed registry header mismatch')
 entries=[]
 for _ in range(count):
  begin=o;rid=struct.unpack_from('<q',b,o)[0];o+=8
  def readstr():
   nonlocal o
   n=struct.unpack_from('<i',b,o)[0];o+=4
   if n<0 or n>1024:raise ValueError('registry metadata string invalid')
   v=b[o:o+n].decode('utf8');o=(o+n+3)&~3;return v
  cls=readstr();namespace=readstr();assembly=readstr();emotion=struct.unpack_from('<i',b,o)[0];o+=4
  if emotion not in ENUMS['emotion']:raise ValueError(f'unknown emotion value {emotion}')
  if cls=='CharacterBaseSpriteByEmotionData':
   fields={'sprite':{'file_id':struct.unpack_from('<i',b,o)[0],'path_id':struct.unpack_from('<q',b,o+4)[0],'offset':o}};o+=12
  elif cls=='CharacterAnimatedSpriteByEmotion':
   cycle,n=struct.unpack_from('<ii',b,o);o+=8
   if cycle not in (0,1,2) or n<0 or n>4096:raise ValueError('invalid animated emotion payload')
   frames=[]
   for _ in range(n):frames.append({'file_id':struct.unpack_from('<i',b,o)[0],'path_id':struct.unpack_from('<q',b,o+4)[0],'offset':o});o+=12
   fps=struct.unpack_from('<i',b,o)[0];o+=4
   if fps<0 or fps>300:raise ValueError('invalid animated emotion frame rate')
   fields={'cycling_type_value':cycle,'frame_sprites':frames,'frames_per_second':fps}
  else:raise ValueError(f'unsupported registry type {cls}')
  entries.append({'rid':rid,'class':cls,'namespace':namespace,'assembly':assembly,'emotion_value':emotion,'emotion_name':ENUMS['emotion'][emotion],'record_offset':begin,'payload_end_offset':o,'fields':fields})
 if o!=len(b):raise ValueError(f'registry end {o:#x} != object end {len(b):#x}')
 if len({x['rid'] for x in entries})!=len(entries) or {x['rid'] for x in entries}!=set(expected_ids):raise ValueError('registry RID vector mismatch')
 return entries

def parse_row(old):
 b=(RAW/old['raw_dump']).read_bytes()
 if len(b)!=old['raw_bytes']:raise ValueError('raw object byte length mismatch')
 name=old['name'];name_end=32+((len(name.encode('utf8'))+3)&~3)
 r=Reader(b);r.o=name_end
 char_type_off=r.o;ctype=r.i32()
 if ctype!=old['character_type_value']:raise ValueError('character enum differs from retained parse')
 pose_count=r.count('pose',128);poses=[]
 if pose_count!=len(old['poses']):raise ValueError('pose count differs from retained parse')
 for i in range(pose_count):
  begin=r.o;state=r.i32();sprite=r.pptr();position=r.vec2();scale=r.vec2();cannot=r.boolean()
  retained=old['poses'][i]
  if state!=retained['name_value'] or sprite['path_id']!=retained['sprite']['path_id']:raise ValueError('raw pose disagrees with retained typed prefix')
  poses.append({'name_value':state,'name':ENUMS['room_people_state'].get(state,f'Unknown({state})'),'sprite':sprite,'position_shift':position,'scale_shift':scale,'cannot_interact':cannot,'offset':begin})
 emotion_count_offset=r.o;emotion_count=r.count('managed-reference ID',1024);emotion_ids_offset=r.o;emotion_ids=[r.i64() for _ in range(emotion_count)]
 if emotion_count!=old['emotions_count_at_next_serialized_field']:raise ValueError('emotion count differs from retained prefix')
 offsets={'character_type':char_type_off,'emotion_ids_count':emotion_count_offset,'emotion_ids':emotion_ids_offset}
 n=r.count('emotion override');overrides=[]
 for _ in range(n):
  start=r.o;state=r.i32();pos=r.vec3();scale=r.vec3()
  if state not in ENUMS['emotion']:raise ValueError(f'unknown override emotion {state}')
  overrides.append({'emotion_value':state,'emotion':ENUMS['emotion'][state],'position':pos,'scale':scale,'offset':start})
 room_offset=r.o;room=r.i32();localized_name=r.localized();assets={}
 assets['corpse_mask']=r.pptr();assets['hands_sprite_human']=r.pptr();assets['eye_sprite_human']=r.eye();assets['teeth_sprite_human']=r.pptr();assets['ear_human']=r.animation();assets['armpit_human']=r.animation();assets['photo_human']=r.pptr()
 assets['hands_sprite_imposter']=r.pptr();assets['eye_sprite_imposter']=r.eye();assets['teeth_sprite_imposter']=r.pptr();assets['ear_imposter']=r.animation();assets['armpit_imposter']=r.animation();assets['photo_imposter']=r.pptr()
 knock_offset=r.o;knock=r.i32();theme=r.i32();assets['night_room_sound']=r.pptr();offsets['is_imposter']=r.o;imposter=r.boolean();entrance=r.f32();room_scale=r.f32();can_exile=r.boolean();is_preset=r.boolean();place_offset=r.o;place=r.i32();random_status=r.boolean()
 offsets.update({'room':room_offset,'knock_sound':knock_offset,'place':place_offset})
 visits=[]
 for _ in range(r.count('visit')):visits.append({'day_number':r.i32(),'guest_number':r.i32()})
 allowed=r.array_int('allowed day');minimum=r.i32();quote=r.localized();pos_bias=r.vec2();scale_bias=r.vec2();fema=r.f32();extra_pos=r.array_vec3('extra position');extra_rot=r.array_vec3('extra rotation');extra_scale=r.array_vec3('extra scale');dialog_pos=r.vec2();dialog_scale=r.f32()
 registry_offset=r.o;offsets['registry']=registry_offset
 ids_start=offsets['emotion_ids'];ids_end=ids_start+8*emotion_count
 # Find the unique v2 registry suffix at the exact ordinary-field cursor.
 entries=parse_registry(b,registry_offset,emotion_ids)
 return {'name':name,'source_file':old['source_file'],'path_id':old['path_id'],'raw_dump':old['raw_dump'],'raw_bytes':len(b),
  'character_type_value':ctype,'character_type':ENUMS['character_type'].get(ctype,f'Unknown({ctype})'),'poses':poses,
  'emotion_ids':{'count':emotion_count,'values':emotion_ids,'offset':ids_start},'emotion_overrides':overrides,
  'room_value':room,'room':ENUMS['room'].get(room,f'Unknown({room})'),'name_localization':localized_name,'assets':assets,
  'knock_sound_value':knock,'knock_sound':ENUMS['sound'].get(knock,f'Unknown({knock})'),'entrance_theme_value':theme,'entrance_theme':ENUMS['sound'].get(theme,f'Unknown({theme})'),
  'is_imposter':imposter,'entrance_scale':entrance,'room_scale':room_scale,'can_exile':can_exile,'is_preset':is_preset,
  'place_value':place,'place':ENUMS['place'].get(place,f'Unknown({place})'),'randomly_generated_status':random_status,
  'visits':visits,'allowed_days':allowed,'minimum_games_completed_to_appear':minimum,'quote':quote,
  'gacha_pos_bias':pos_bias,'gacha_scale_bias':scale_bias,'fema_rating_bonus':fema,
  'extra_position':extra_pos,'extra_rotation':extra_rot,'extra_scale':extra_scale,'dialog_position':dialog_pos,'dialog_scale':dialog_scale,
  'parse_offsets':offsets,'managed_reference_registry':{'offset':registry_offset,'version':2,'count':len(entries)},'raw_registry_entries':entries}

def main():
 src=json.loads(INPUT.read_text());rows=[];errors=[]
 for row in src['character_records']:
  try:rows.append(parse_row(row))
  except Exception as e:errors.append({'name':row.get('name'),'error':repr(e)})
 out={'method':'Full raw static parse of all serialized CharacterSOData fields using exact Cpp2IL field layouts; success requires ordinary cursor == managed registry start, then exact registry end == raw object end and RID/enum/layout checks.','records':rows,'errors':errors}
 OUTPUT.parent.mkdir(parents=True,exist_ok=True);OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print(f'records={len(rows)} errors={len(errors)}')
 if errors:print(json.dumps(errors,ensure_ascii=False,indent=2));raise SystemExit(1)
 if len(rows)!=73:raise SystemExit('expected 73 production character records')
 a=next(x for x in rows if x['name']=='Alkonost')
 assert a['raw_bytes']==1388 and a['emotion_ids']['offset']-4==156 and a['parse_offsets']['is_imposter']==636 and a['parse_offsets']['place']==656 and a['managed_reference_registry']['offset']==880
 assert a['is_imposter'] is True and a['place']=='LivingRoomSofaRight' and a['allowed_days']==[1,2,3,4,5,6]
 print('Alkonost known-offset checks passed')
if __name__=='__main__':main()
