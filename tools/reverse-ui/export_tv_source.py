#!/usr/bin/env python3
"""Emit compact TV/dialogue fidelity evidence from static Unity extraction outputs.

The source binary is read only as bytes. The normalized values are joined from
static UnityPy/Cpp2IL extraction manifests and are checked against raw offsets.
"""
from __future__ import annotations
import argparse, hashlib, json, struct, math, zipfile
import UnityPy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
def load(p): return json.loads(p.read_text())
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--raw-tv', type=Path, default=ROOT.parent/'recovery/checkpoint/reconstruction/assets/gameplay_data/raw/sharedassets0_2666_TV.bin')
    ap.add_argument('--characters', type=Path, default=ROOT.parent/'recovery/checkpoint/reconstruction/reverse-characters/character_configs.json')
    ap.add_argument('--rooms', type=Path, default=ROOT/'reconstruction/reverse-rooms/room_manifest.json')
    ap.add_argument('--scene', type=Path, default=ROOT.parent/'recovery/checkpoint/reconstruction/reverse-scenes/scene_render_manifest.json')
    ap.add_argument('--level1', type=Path, default=ROOT.parent/'recovery/unity-data/level1')
    ap.add_argument('--original-zip', type=Path, default=ROOT.parent/'recovery/original-v1.3.18.zip')
    ap.add_argument('--out', type=Path, default=ROOT/'reconstruction/reverse-ui/tv_source_manifest.json')
    a=ap.parse_args(); raw=a.raw_tv.read_bytes(); chars=load(a.characters); rooms=load(a.rooms); scene=load(a.scene)
    tv=next(x for x in chars['records'] if x['name']=='TV')
    assert len(raw)==tv['raw_bytes']==5656
    # Source Cpp2IL layout: pose sprite PPtr at byte 48, position at 60, scale at 68.
    assert struct.unpack_from('<iq',raw,48)==(0,1740)
    assert all(math.isclose(x,y,rel_tol=1e-6,abs_tol=1e-6) for x,y in zip(struct.unpack_from('<2f',raw,60),tv['poses'][0]['position_shift']))
    assert all(math.isclose(x,y,rel_tol=1e-6,abs_tol=1e-6) for x,y in zip(struct.unpack_from('<2f',raw,68),tv['poses'][0]['scale_shift']))
    base=next(x for x in tv['raw_registry_entries'] if x['emotion_name']=='Base')
    assert base['emotion_value']==-1966747463 and base['fields']['frames_per_second']==8
    assert [x['path_id'] for x in base['fields']['frame_sprites']]==[2449,2429,1322,1534]
    # Static PE read only: map the IL2CPP VA referenced by Bedroom.StartTVDialog
    # through the PE section table and verify the literal f32. Never load/execute it.
    dll_name='No.Im.not.a.Human.v1.3.18/No.Im.not.a.Human.v1.3.18/GameAssembly.dll'
    with zipfile.ZipFile(a.original_zip) as zf:
        dll=zf.read(dll_name)
    pe=struct.unpack_from('<I',dll,0x3c)[0]
    assert dll[pe:pe+4]==b'PE\0\0'
    coff=pe+4
    _,nsections,_,_,_,optional_size,_=struct.unpack_from('<HHIIIHH',dll,coff)
    optional=coff+20
    magic=struct.unpack_from('<H',dll,optional)[0]
    image_base=struct.unpack_from('<Q',dll,optional+24)[0] if magic==0x20b else struct.unpack_from('<I',dll,optional+28)[0]
    va=0x1837F2D40; rva=va-image_base; raw_offset=None; sections=[]
    for i in range(nsections):
        sh=optional+optional_size+40*i
        name=dll[sh:sh+8].split(b'\0')[0].decode('ascii')
        virtual_size,virtual_address,raw_size,raw_ptr=struct.unpack_from('<IIII',dll,sh+8)
        sections.append({'name':name,'virtual_address':virtual_address,'virtual_size':virtual_size,'raw_pointer':raw_ptr,'raw_size':raw_size})
        if virtual_address<=rva<virtual_address+max(virtual_size,raw_size): raw_offset=raw_ptr+rva-virtual_address
    assert raw_offset is not None
    tv_panel_x=struct.unpack_from('<f',dll,raw_offset)[0]
    assert tv_panel_x==-575.0
    bedroom_cs=(ROOT.parent/'recovery/checkpoint/reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Rooms/Bedroom.cs').read_text()
    dialog_cs=(ROOT.parent/'recovery/checkpoint/reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/DialogSystem/DialogView.cs').read_text()
    dialog_isil=(ROOT.parent/'recovery/checkpoint/reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/DialogSystem/DialogView.txt').read_text()
    assert 'private const float X_DIALOG_POSITION = -575;' in bedroom_cs
    assert 'private const float USUAL_DIALOG_X_POSITION = 385;' in dialog_cs
    assert 'Move [rdi+16], 0x43C08000' in dialog_isil
    assert struct.unpack('<f',struct.pack('<I',0x43C08000))[0]==385.0
    rooms_tv=next(x for x in rooms['rooms'] if x.get('room')=='Bedroom')
    tvgo=next(x for x in rooms_tv['hierarchy'] if x.get('game_object_path_id')==1337)
    # Read live Transform.m_Children order from the supplied raw scene.
    env=UnityPy.Environment(); env.load_file(str(a.level1)); level=next(f for f in env.files.values() if Path(f.name).name=='level1')
    gos={}; transforms={}
    for obj in level.objects.values():
        if obj.type.name=='GameObject': gos[int(obj.path_id)]=obj.read_typetree()
        elif obj.type.name in ('Transform','RectTransform'): transforms[int(obj.path_id)]=obj.read_typetree()
    tr_by_go={int(t['m_GameObject']['m_PathID']):(tid,t) for tid,t in transforms.items()}
    go_by_transform={tid:gid for gid,(tid,_) in tr_by_go.items()}
    canvas=tr_by_go[529][1]; canvas_children=[]
    for idx,ptr in enumerate(canvas['m_Children']):
        child_go=next(g for g,(tid,_) in tr_by_go.items() if tid==int(ptr['m_PathID']))
        canvas_children.append({'sibling_index':idx,'game_object_path_id':child_go,'name':gos[child_go]['m_Name']})
    assert [(x['sibling_index'],x['game_object_path_id']) for x in canvas_children if x['game_object_path_id'] in (858,492,1083,348)]==[(2,858),(3,492),(4,1083),(6,348)]
    def rect_fields(go_id):
        t=tr_by_go[go_id][1]
        return {'anchored_position':t.get('m_AnchoredPosition'),'local_position':t.get('m_LocalPosition'),'size_delta':t.get('m_SizeDelta')}
    view=next(x for x in scene['dialog_views'])
    fake_runner_raw=level.objects[4471].get_raw_data()
    line_count=struct.unpack_from('<i',fake_runner_raw,192)[0]
    assert line_count==4
    line_view_content_pointers=[]
    for i in range(line_count):
        off=196+i*12
        file_id,path_id=struct.unpack_from('<iq',fake_runner_raw,off)
        assert file_id==0 and path_id in go_by_transform
        go_id=go_by_transform[path_id]
        line_view_content_pointers.append({'array_index':i,'serialized_byte_offset':off,'file_id':file_id,'transform_path_id':path_id,'game_object_path_id':go_id,'name':gos[go_id]['m_Name'],'anchored_position':transforms[path_id].get('m_AnchoredPosition')})
    assert [x['game_object_path_id'] for x in line_view_content_pointers]==[1129,1187,1098,1206]
    result={
      'schema_version':1,
      'provenance':{
        'method':'Static raw-byte assertions against supplied Unity CharacterSOData plus joins to retained UnityPy scene manifests; no original PE executed.',
        'raw_source':'recovery/checkpoint/reconstruction/assets/gameplay_data/raw/sharedassets0_2666_TV.bin',
        'raw_sha256':hashlib.sha256(raw).hexdigest(),
        'character_manifest':'recovery/checkpoint/reconstruction/reverse-characters/character_configs.json',
        'room_manifest':'ninah-port/reconstruction/reverse-rooms/room_manifest.json',
        'dialog_manifest':'recovery/checkpoint/reconstruction/reverse-scenes/scene_render_manifest.json',
        'raw_scene':'recovery/unity-data/level1',
        'raw_scene_sha256':hashlib.sha256(a.level1.read_bytes()).hexdigest(),
        'assembly_static_read':{'archive':'recovery/original-v1.3.18.zip','entry':dll_name,'assembly_sha256':hashlib.sha256(dll).hexdigest(),'pe_image_base':hex(image_base),'sections':sections,'no_execution':True},
        'assertions':['raw size 5656','raw level1 Transform child order asserted for portrait (GO 858), Line View (492), Options List View (1083), and Overlay (348)','FakeDialogRunner raw Transform[] count/PPtrs at bytes 192-244 resolve to DialogContent and sign containers','FullSize pose sprite PPtr (file 0,path 1740) at offset 48','pose position at 60 and scale at 68 equal normalized parsed values','Base emotion enum and 4 animation frame PPtrs/FPS agree with parsed raw registry','PE VA 0x1837F2D40 maps to f32 -575.0','DialogView default X immediate 0x43C08000 decodes to 385.0']},
      'conclusion':{
        'full_size_pose_is_original':True,
        'dialogue_tv_portrait_is_original':True,
        'reason':'TV is the Bedroom CharacterSOData participant. Its source Base emotion is a 4-frame animated presenter; DialogView.SetCharacterEmotion consumes CharacterSOData emotion data and authored DialogPosition/DialogScale.',
        'source_pose':tv['poses'][0],
        'dialog_position':tv['dialog_position'],'dialog_scale':tv['dialog_scale'],
        'base_emotion':{'enum_value':base['emotion_value'],'name':base['emotion_name'],'fps':base['fields']['frames_per_second'],'frames':base['fields']['frame_sprites']},
        'normal_room_transform':tvgo.get('rect_transform'),
        'dialog_view':{'component_path_id':view['component_path_id'],'parent_canvas':view['serialized_fields']['parent_canvas'],'character_animated_image':view['serialized_fields']['character_animated_image'],'dialog_panel_base':view['serialized_fields']['dialog_panel_base'],'dialog_panel_answers':view['serialized_fields']['dialog_panel_answers'],'fake_dialog_runner_component_path_id':4471,'line_view_contents':line_view_content_pointers},
        'room_behavior':'Bedroom.WatchMorningTV obtains the TV from IRoomView.CharacterViews, calls StartTVDialog(tv,true), and disables interaction. BedroomView.SetTVActive toggles the TV UIButton.',
        'video_audio':'TV GameObject has VideoPlayer component path 3773 and AudioSource 2501. Retained ISIL does not show WatchMorningTV wiring either component to the dialogue. The TV mask sprite resolves to sharedassets1.assets path 643 (tv_mask).',
        'dialogue_draw_order':{'source':'raw level1 Transform.m_Children order on Dialog Canvas GO 529','children':canvas_children,'portrait_before_text_and_options':True,'implication':'Unity UI sibling draw order places the Character portrait behind Line View and Options List View; Overlay is later at sibling 6.'}},
      'runtime':{
        'fixed_room_actors':[{'name':'TV','room':6,'component_path_id':5161,'game_object_path_id':1337,'authored_active_self':True,'initial_pose':0,'initial_pose_name':'FullSize','room_image_component_path_id':4593,'source_sprite':{'file':'sharedassets0.assets','path_id':1740,'name':'Livingroom2_obj2'}}],
        'dialogue':{'default_panel_x':385,'tv_panel_x':-575,'view_data_x':-575,'offset_from_default':-960,'portrait_before_text':True,
          'source_panel_positions':{'dialog_panel_base':rect_fields(1129),'dialog_panel_answers':rect_fields(571),'options_list_view':rect_fields(1083)},
          'view_data_target_in_source':'DialogView.StartDialog applies DialogViewData.XPosition to each FakeDialogRunner._lineViewContents Transform.localPosition.x. Raw serialized array resolves to DialogContent, EyeContainer, HandsContainer, and TeethContainer. It then copies the moved DialogContent world position to DialogContent2/options. Thus the source TV offset moves dialogue content/options.',
          'evidence':{'tv_position':{'method':'PE RVA mapped from Bedroom.StartTVDialog reference VA 0x1837F2D40','va':'0x1837F2D40','rva':hex(rva),'section':next(s['name'] for s in sections if s['virtual_address']<=rva<s['virtual_address']+max(s['virtual_size'],s['raw_size'])),'raw_file_offset':hex(raw_offset),'raw_bytes':dll[raw_offset:raw_offset+4].hex(),'f32':tv_panel_x,'assembly_entry':dll_name,'assembly_sha256':hashlib.sha256(dll).hexdigest()},'usual_position':{'source':'DialogView.StartDialog ISIL default DialogViewData XPosition immediate','bits':'0x43C08000','f32':385.0,'constant_source':'recovered Cpp2IL DialogView.cs USUAL_DIALOG_X_POSITION'},'tv_constant_source':'recovered Cpp2IL Bedroom.cs X_DIALOG_POSITION and Bedroom.StartTVDialog passes constructed DialogViewData into DialogManager.RunDialog'},
          'runtime_note':'Shift dialogue content, options and hit-testing by -960 for the authored TV dialogue fixture; source sibling order keeps the TV portrait behind text/options.'}}}
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(f'wrote {a.out}')
if __name__=='__main__': main()
