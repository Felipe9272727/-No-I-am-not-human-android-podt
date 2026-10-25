#!/usr/bin/env python3
"""Extract native x86-64 method listings from Cpp2IL ISIL text output."""
from pathlib import Path
import re
root=Path('reconstruction/logic/cpp2il_isil_target/IsilDump/Assembly-CSharp')
out=Path('reconstruction/logic/selected_native_disassembly.txt')
want={
'DialogCommandsInstance':{'GetEnergy','CanOrderCourier','IsImposter','IsCharacterPlaceEmpty','GetCharacterOnPlace','GetInnocentsCount','TryGiveResource','GetItemCount','IsAlive','IsNobodyHome','PerformEvent'},
'DialogCommandsInstance_NestedType___c__DisplayClass214_0':{'<IsImposter>b__0'},
'DialogCommandsInstance_NestedType___c__DisplayClass223_0':{'<IsCharacterPlaceEmpty>b__0','<IsCharacterPlaceEmpty>b__1'},
'DialogCommandsInstance_NestedType___c__DisplayClass224_0':{'<GetCharacterOnPlace>b__0','<GetCharacterOnPlace>b__1'},
'DialogCommandsInstance_NestedType___c':{'<GetInnocentsCount>b__219_0'},
'DayNightController':{'AddEnergy','RefillEnergy','RemoveExtraEnergySlotsForTomorrow','get_MaxDayActions','ActAll','Change','HasCompletedDaytimeGoal','get_DayActions'},
'GameEventsManager':{'CheckOtherEvents','CheckDingDongEvents'},
'CharactersManager':{'IsCharacterAliveInside','GetPlace','LetIn','Refuse'},
'CharacterSOData':{'get_IsImposter','get_Place','get_CharacterType'},
'NodeNameGetter':{'Init','GetNodeName','IncrementNode','ResetDay'},
}
out.parent.mkdir(parents=True,exist_ok=True)
with out.open('w') as dst:
    dst.write('Static x86-64 disassembly, emitted by official Cpp2IL ISIL output format.\n')
    dst.write('Source: GameAssembly.dll; no game code was executed. Function listings may include compiler helper calls.\n')
    for file in sorted(root.rglob('*.txt')):
        stem=file.stem
        if stem not in want: continue
        text=file.read_text(errors='replace')
        type_line=next((x for x in text.splitlines() if x.startswith('Type: ')),f'Type: {stem}')
        lines=text.splitlines(); matches=[]
        i=0
        while i<len(lines):
            if lines[i].startswith('Method: '):
                header=lines[i]
                m=re.search(r'([^ ]+)\([^)]*\)(?:\s|$)',header.removeprefix('Method: '))
                name=m.group(1) if m else ''
                j=i+1
                while j<len(lines) and not lines[j].startswith('Method: '): j+=1
                if name in want[stem]:
                    body=lines[i:j]
                    try: isil=body.index('ISIL:')
                    except ValueError: isil=len(body)
                    # Keep native instructions only, omitting the verbose symbolic ISIL interpretation.
                    native=body[:isil]
                    matches.append('\n'.join(native))
                i=j
            else:i+=1
        if matches:
            dst.write('\n\n'+'='*76+'\n'+type_line+'\n')
            dst.write('\n\n'.join(matches))
            dst.write('\n')
print(out)
