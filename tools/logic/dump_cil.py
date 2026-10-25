#!/usr/bin/env python3
"""Print selected recovered Assembly-CSharp method bodies from Cpp2IL's IL recovery DLL."""
import sys
import dnfile
from dncil.cil.body import CilMethodBody
from dncil.cil.body.reader import CilMethodBodyReaderBytes

path=sys.argv[1] if len(sys.argv)>1 else 'reconstruction/logic/cpp2il_il/Assembly-CSharp.dll'
p=dnfile.dnPE(path)
rows={i+1:r for i,r in enumerate(p.net.mdtables.MethodDef.rows)}
fields={i+1:r for i,r in enumerate(p.net.mdtables.Field.rows)}
refs={i+1:r for i,r in enumerate(p.net.mdtables.MemberRef.rows)}
types={i+1:r for i,r in enumerate(p.net.mdtables.TypeDef.rows)}
typerefs={i+1:r for i,r in enumerate(p.net.mdtables.TypeRef.rows)}
owners={}
for t in types.values():
    for m in t.MethodList: owners[m.row]=f'{t.TypeNamespace}.{t.TypeName}'
def owner_name(coded):
    try:
        table=coded.table; row=table.rows[coded.row_index-1]
        if hasattr(row,'TypeName'): return f'{row.TypeNamespace}.{row.TypeName}'
        if hasattr(row,'Name'): return str(row.Name)
    except Exception: pass
    return str(coded)
def resolve(tok):
    v=tok.value; tab=v>>24; idx=v&0xffffff
    if tab==0x70:
        try: return '"'+str(p.net.user_strings.get(idx))+'"'
        except Exception: return str(tok)
    if tab==0x06 and idx in rows:
        r=rows[idx]; return f'{owners.get(r,"?")}::{r.Name}'
    if tab==0x0a and idx in refs:
        r=refs[idx]; return f'{owner_name(r.Class)}::{r.Name}'
    if tab==0x04 and idx in fields: return str(fields[idx].Name)
    if tab==0x02 and idx in types:
        r=types[idx]; return f'{r.TypeNamespace}.{r.TypeName}'
    if tab==0x01 and idx in typerefs:
        r=typerefs[idx]; return f'{r.TypeNamespace}.{r.TypeName}'
    return str(tok)
focus={
'_Code.Utils.CustomYarnReading.CustomYarnReader':{'GetNodeContent','GetNodesCountContainsString'},
'_Code.Utils.CustomYarnReading.NodeNameGetter':{'Init','GetNodeName','IncrementNode','ResetDay'},
'_Code.DialogSystem.DialogManager':{'RunDialog','AddTalk','SetToLastTalk','GetCurrentDialogIndexForCharacter','RefreshSignChecks','OnSignShowed','OnStoppedShowingSign','OnDialogEnded','OnSaveDataLoad'},
'_Code.DialogSystem.DialogCommandsInstance':None,
'_Code.Infrastructure.DayNight.DayNightController':{'Change','InitNewNight','InitNewDay','Act','ActAll','HasCompletedDaytimeGoal','SetDayForEnding','AddEnergy','RefillEnergy','RemoveExtraEnergySlotsForTomorrow','OnSaveDataLoad'},
'_Code.Infrastructure.GameEvents.GameEventsManager':{'CheckOtherEvents','CheckDingDongEvents','CheckProphetToRemove','CheckPriestToRemove','CheckMushroomeaterToRemove'},
'_Code.DialogSystem.Commands.DialogCommandsInstance':{'IsAlive','IsImposter','IsCharacterPlaceEmpty','GetCharacterOnPlace','IsNobodyHome','GetInnocentsCount','LetCharacterIn','AggressiveLetCharacterIn','RefuseCharacter','KillCharacter','KillCharacterWithNoGun','KillRoom','KillTomorrow','ExileCharacter','ExileAfterTomorrow','RefuseOldLetInNew','TryGiveResource','CanOrderCourier','GetEnergy','HasCompletedMushroomCondition','GetItemCount','GetItem','PerformEvent','GoToLocation','ChangePose','ChangePoseTomorrow','ChangeState','OrderCourier','IsNeedToGetDeficitItem','PeekDeficitItem','GetCourierOrder','GetPhoneNumber','HasSeenDream','ShowSign','ShowPlayerSign','SetEmotion','SetUpGun','CallFEMATonight','BeginCultists','SaveCultists','UnlockDeathEnding','UnlockKillerEnding','UnlockMushroomEnding','UnlockPhoneNumber'},
'_Code.Infrastructure.Locations.LocationsManager':{'GoToLocation'},
}
for t in p.net.mdtables.TypeDef.rows:
    tn=f'{t.TypeNamespace}.{t.TypeName}'
    if tn not in focus: continue
    for m in t.MethodList:
        r=m.row; name=str(r.Name)
        if focus[tn] is not None and name not in focus[tn]: continue
        if not r.Rva: continue
        try:
            off=p.get_offset_from_rva(r.Rva)
            body=CilMethodBody(CilMethodBodyReaderBytes(p.__data__[off:off+100000]))
        except Exception as e:
            print(f'\n### {tn}::{name} [BODY PARSE ERROR {e}]'); continue
        print(f'\n### {tn}::{name} [RVA 0x{r.Rva:X}, {body.code_size} bytes]')
        for ins in body.instructions:
            op=ins.operand
            if hasattr(op,'value') and op.__class__.__name__ in ('Token','StringToken'): op=resolve(op)
            print(f'{ins.offset:04x}: {ins.mnemonic:<14} {op if op is not None else ""}')
