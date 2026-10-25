#!/usr/bin/env python3
"""Generate fixed subscriber numbers from fully parsed OtherGameSOData JSON."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'reconstruction/assets/gameplay_data/other_game_data.json'
OUTPUT=ROOT/'reconstruction/native-game/generated/production_phone_data.hpp'
r=json.loads(SOURCE.read_bytes());assert r['parsed_bytes_end']==r['raw_bytes'] and r['unparsed_tail_bytes']==0
values=r['values']['phone_numbers'];names={2:'FEMA',4:'Psychics',11:'PhoneRoulette'}
assert len(values)==3
for x in values:assert names.get(x['subscriber_value'])==x['subscriber'] and len(x['number'])==6 and x['number'].isdigit()
rows=',\n        '.join(f'{{static_cast<PhoneSubscriber>({x["subscriber_value"]}), {json.dumps(x["number"])} }}' for x in values)
OUTPUT.parent.mkdir(parents=True,exist_ok=True)
OUTPUT.write_text(f'''// Generated from fully parsed OtherGameSOData pathID {r['path_id']}.\n// Input SHA256: {hashlib.sha256(SOURCE.read_bytes()).hexdigest()}\n#pragma once\n#include "ninah/phone.hpp"\nnamespace ninah::production {{\ninline FixedPhoneNumbers fixed_phone_numbers() {{ return FixedPhoneNumbers{{\n        {rows}\n}}; }}\n}}\n''')
print(str(OUTPUT))
