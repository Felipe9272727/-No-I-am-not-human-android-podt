#!/usr/bin/env python3
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
lines=subprocess.check_output([str(ROOT/'reconstruction/native-game/build/yarn-integration'),str(ROOT/'reconstruction/narrative/program.json'),str(ROOT/'reconstruction/reverse-localization/line_metadata.json')],text=True).splitlines()
assert lines[0]=='energy=4' and lines[2]=='energy=0'
yes,no,rejected=[json.loads(lines[i]) for i in (1,3,4)]
assert [o['enabled'] for o in yes['options']]==[True,True]
assert [o['enabled'] for o in no['options']]==[True,False]
assert rejected['type']=='error' and 'disabled' in rejected['error']
assert lines[5]=='povistka=1' and lines[8]=='povistka=0'
before,command,after=[json.loads(lines[i]) for i in (6,7,9)]
assert before['options'][2]['line_id']=='line:talk_alt_1_08c0bd1'
assert [o['enabled'] for o in before['options']]==[True,True,True]
assert [o['enabled'] for o in after['options']]==[True,True,False]
assert command=={'type':'command','command':'Sound Consum_postcard'}
metadata=json.loads((ROOT/'reconstruction/reverse-localization/line_metadata.json').read_text())['line_metadata']
for event in (yes,no,before,after):
 for option in event['options']:
  source=metadata[option['line_id']]['metadata'][0]
  assert option['metadata']=={key:source[key] for key in ('node_name','tags')}
assert 'energy' in yes['options'][1]['metadata']['tags']
assert 'give_item' in before['options'][2]['metadata']['tags']
print('Original energy and item-give routes use real C++ state and exact source metadata: passed')
