#!/usr/bin/env python3
"""Generate C++ catalogue and day data from validated recovered JSON records."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'reconstruction';OUT=BASE/'native-game/generated';OUT.mkdir(parents=True,exist_ok=True)
configs=json.loads((BASE/'assets/gameplay_data/production_configs.json').read_bytes())
day,=configs['day_night_controller_records']
assert day['parsed_bytes_end']==day['raw_bytes'] and day['unparsed_tail_bytes']==0
actions=','.join(map(str,day['max_day_actions_by_days']))
(OUT/'production_data.hpp').write_text('// Generated from fully decoded DayNightControllerSOData.\n#pragma once\n#include "ninah/core.hpp"\nnamespace ninah::production {\ninline DayConfig day_config(){return DayConfig{{'+actions+'}};}\ninline constexpr std::int32_t last_day='+str(day['last_day'])+';\n}\n')
chars=json.loads((BASE/'reverse-characters/character_configs.json').read_bytes());assert not chars['errors']
rows=chars['records'];assert len(rows)==73
byref={(r['source_file'],r['path_id']):r for r in rows}
mother,=configs['resource_mother_records'];ordered=[]
for ref in mother['references']['characters_data']:
 assert ref['file_id']==0
 ordered.append(byref[(mother['source_file'],ref['path_id'])])
assert len(ordered)==72
def cppbool(v):assert type(v)is bool;return str(v).lower()
def charcpp(r):
 visits=','.join('{'+str(v['day_number'])+','+str(v['guest_number'])+'}' for v in r['visits'])
 return 'CharacterData{'+','.join([str(r['character_type_value']),json.dumps(r['character_type']),str(r['room_value']),str(r['place_value']),cppbool(r['is_imposter']),cppbool(r['can_exile']),cppbool(r['is_preset']),cppbool(r['randomly_generated_status']),'{'+','.join(map(str,r['allowed_days']))+'}','{'+visits+'}',str(r['minimum_games_completed_to_appear'])])+'}'
(OUT/'production_characters.hpp').write_text('// Generated in ResourceMother order from 72 of 73 validated records.\n#pragma once\n#include "ninah/characters.hpp"\nnamespace ninah::production {\ninline CharacterCatalog character_catalog(){return CharacterCatalog({\n'+',\n'.join(charcpp(r) for r in ordered)+'\n});}\n}\n')
emotions=json.loads((BASE/'reverse-characters/emotion_registry.json').read_bytes());assert not emotions['errors']
byname={r['name']:r for r in rows};entries=[]
for e in emotions['records']:
 f=e['fields']
 if e['class']=='CharacterAnimatedSpriteByEmotion':cycle,fps,frames=f['cycling_type_value'],f['frames_per_second'],f['frame_sprites']
 else:assert e['class']=='CharacterBaseSpriteByEmotionData';cycle,fps,frames=2,8,[f['sprite']]
 refs=','.join('SpriteRef{'+json.dumps(e['source_file'])+','+str(s['file_id'])+','+str(s['path_id'])+'}' for s in frames)
 entries.append('EmotionEntry{'+str(byname[e['character']]['character_type_value'])+','+str(e['emotion_value'])+','+json.dumps(e['emotion_name'])+',AnimationSpec{static_cast<AnimationCycling>('+str(cycle)+'),{'+refs+'},'+str(fps)+',false}}')
(OUT/'production_emotions.hpp').write_text('// Generated from 275 byte-validated emotion records.\n#pragma once\n#include "ninah/emotions.hpp"\nnamespace ninah::production {\ninline EmotionCatalog emotion_catalog(){return EmotionCatalog({\n'+',\n'.join(entries)+'\n});}\n}\n')
print(json.dumps({'day_entries':len(day['max_day_actions_by_days']),'character_records':len(rows),'production_provider_records':len(ordered),'emotion_records':len(entries)}))
