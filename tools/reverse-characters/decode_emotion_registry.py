#!/usr/bin/env python3
"""Emit validated emotion entries from verified CharacterSOData registry suffixes."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'reconstruction/reverse-characters/character_configs.json'
OUTPUT=ROOT/'reconstruction/reverse-characters/emotion_registry.json'
def main():
 config=json.loads(SOURCE.read_text()); all_entries=[]; errors=[]
 for row in config['records']:
  try:
   entries=row['raw_registry_entries']; ids=row['emotion_ids']['values']
   if len(entries)!=len(ids) or {e['rid'] for e in entries}!=set(ids):raise ValueError('managed-reference IDs differ from host vector')
   byid={e['rid']:e for e in entries}
   if len(byid)!=len(entries):raise ValueError('duplicate managed-reference RID')
   for index,rid in enumerate(ids):
    entry=byid[rid]
    all_entries.append({'character':row['name'],'source_file':row['source_file'],'raw_dump':row['raw_dump'],'array_index':index,**entry})
  except Exception as exc:errors.append({'name':row['name'],'error':repr(exc)})
 report={'method':'Raw static parser for Unity 6 managed-reference registry v2; declared Cpp2IL concrete payload layouts, enum values cross-checked against EDialogEmotionState, and registry suffix required to end at exact raw-object length.','schema_sources':['ACharacterSpriteByEmotion.cs','CharacterBaseSpriteByEmotionData.cs','CharacterAnimatedSpriteByEmotion.cs','AnimationData.cs','EDialogEmotionState.cs'],'records':all_entries,'errors':errors}
 OUTPUT.write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(f'entries={len(all_entries)} errors={len(errors)}')
 if errors or len(all_entries)!=275:raise SystemExit(1)
if __name__=='__main__':main()
