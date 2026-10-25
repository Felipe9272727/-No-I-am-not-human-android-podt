#!/usr/bin/env python3
"""Static source-linked scene, pose, dialog and examination manifest exporter."""
from __future__ import annotations
import argparse, json, math, struct
from pathlib import Path
import UnityPy

ROOT=Path(__file__).resolve().parents[2]

def pp(raw, off):
    f,p=struct.unpack_from('<iq',raw,off); return {'file_id':int(f),'path_id':int(p)}
def vec(raw,off,n): return [float(x) for x in struct.unpack_from('<'+'f'*n,raw,off)]
def clean(x): return round(float(x),6) if math.isfinite(float(x)) else None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--data',type=Path,required=True); ap.add_argument('--out',type=Path,default=ROOT/'reconstruction/reverse-scenes/scene_render_manifest.json'); a=ap.parse_args()
    for name in ('level1','globalgamemanagers.assets'):
        if not (a.data/name).is_file(): raise SystemExit(f'missing Unity file: {a.data/name}')
    roomdoc=json.loads((ROOT/'reconstruction/reverse-rooms/room_manifest.json').read_text())
    charrows=json.loads((ROOT/'reconstruction/reverse-characters/character_configs.json').read_text())['records']
    emorows=json.loads((ROOT/'reconstruction/reverse-characters/emotion_registry.json').read_text())['records']
    char_by_id={int(c['path_id']):c for c in charrows}; emos={}
    for e in emorows: emos.setdefault(e['character'],[]).append(e)
    env=UnityPy.Environment(); env.load_file(str(a.data/'level1')); env.load_file(str(a.data/'globalgamemanagers.assets'))
    files={Path(f.name).name:f for f in env.files.values()}; scene=files['level1']; gm=files['globalgamemanagers.assets']
    external_files={i:Path(x.path).name for i,x in enumerate(scene.externals,start=1)}
    def source_ref(p,local='level1'):
        return {**p,'file':local if p['file_id']==0 and p['path_id'] else external_files.get(p['file_id'])}
    scripts={}
    for o in gm.objects.values():
        if o.type.name=='MonoScript':
            d=o.read(); ns=str(d.m_Namespace); scripts[int(o.path_id)]=f'{ns}.{d.m_ClassName}' if ns else str(d.m_ClassName)
    gos={}; comp_go={}; transforms={}
    for o in scene.objects.values():
        if o.type.name=='GameObject':
            d=o.read_typetree(); ids=[int(x['component']['m_PathID']) for x in d['m_Component']]; gos[int(o.path_id)]={'path_id':int(o.path_id),'name':str(d['m_Name']),'active_self':bool(d['m_IsActive']),'layer':int(d['m_Layer']),'component_path_ids':ids}
            for cid in ids: comp_go[cid]=int(o.path_id)
        elif o.type.name in ('Transform','RectTransform'): transforms[int(o.path_id)]=o.read_typetree()
    comps={}; native={}
    for o in scene.objects.values():
        if o.type.name in ('GameObject','MonoBehaviour'): continue
        gid=comp_go.get(int(o.path_id))
        native[int(o.path_id)]={'path_id':int(o.path_id),'class':o.type.name,'game_object_path_id':gid,'game_object_name':gos.get(gid,{}).get('name')}
    for o in scene.objects.values():
        if o.type.name!='MonoBehaviour': continue
        raw=o.get_raw_data(); sid=struct.unpack_from('<q',raw,20)[0]; cls=scripts.get(sid)
        if not cls: continue
        h=o.read_typetree(check_read=False); gid=int(h.get('m_GameObject',{}).get('m_PathID',0))
        comps[int(o.path_id)]={'path_id':int(o.path_id),'class':cls,'game_object_path_id':gid,'game_object_name':gos.get(gid,{}).get('name'),'enabled':bool(raw[12]),'raw':raw,'raw_size':len(raw)}
    def xform(gid):
        tid=next((t for t,d in transforms.items() if int(d['m_GameObject']['m_PathID'])==gid),None)
        if tid is None:return None
        d=transforms[tid]; return {'path_id':tid,'type':'RectTransform' if 'm_AnchorMin' in d else 'Transform','local_position':d.get('m_LocalPosition'),'local_rotation':d.get('m_LocalRotation'),'local_scale':d.get('m_LocalScale'),'anchored_position':d.get('m_AnchoredPosition'),'size_delta':d.get('m_SizeDelta'),'anchor_min':d.get('m_AnchorMin'),'anchor_max':d.get('m_AnchorMax'),'pivot':d.get('m_Pivot'),'parent_transform_path_id':int(d.get('m_Father',{}).get('m_PathID',0))}
    def resolved(p):
        c=comps.get(p['path_id']) if p['file_id']==0 else None
        if c:return {'class':c['class'],'game_object_path_id':c['game_object_path_id'],'game_object_name':c['game_object_name']}
        c=native.get(p['path_id']) if p['file_id']==0 else None
        if c:return {'class':c['class'],'game_object_path_id':c['game_object_path_id'],'game_object_name':c['game_object_name']}
        g=gos.get(p['path_id']) if p['file_id']==0 else None
        return {'class':None,'game_object_path_id':g['path_id'],'game_object_name':g['name']} if g else {'class':None,'game_object_path_id':None,'game_object_name':None}
    instances=[]; used={}
    for room in roomdoc['rooms']:
        hs={int(h['game_object_path_id']):h for h in room['hierarchy']}
        for cv in room['view']['character_views']:
            c=comps.get(int(cv['path_id']))
            if not c:continue
            raw=c['raw']; data=pp(raw,56); state=struct.unpack_from('<i',raw,68)[0]
            cfg=char_by_id.get(data['path_id']) if data['file_id']==3 else None
            if not cfg: continue
            pose_list=[]
            for p in cfg['poses']:
                pose_list.append({'state_value':p['name_value'],'state':p['name'],'sprite':{'file_id':p['sprite']['file_id'],'path_id':p['sprite']['path_id'],'file':'sharedassets0.assets' if p['sprite']['file_id']==0 else None},'position_shift':p['position_shift'],'scale_shift':p['scale_shift'],'cannot_interact':p['cannot_interact'],'source_offset':p['offset']})
            h=hs.get(c['game_object_path_id'],{}); initial=next((p for p in pose_list if p['state_value']==state),None)
            instances.append({'room':room['room'],'room_enum':room['enum_value'],'order_in_room':len([i for i in instances if i['room']==room['room']]),'component':{'file':'level1','path_id':c['path_id'],'class':c['class'],'raw_size':c['raw_size'],'data_offset':56,'data_reference':{**data,'file':'sharedassets0.assets'},'start_state_offset':68,'start_state_value':state,'corpse_shader_offset':72,'corpse_shader':pp(raw,72)},'character':{'name':cfg['name'],'source_file':cfg['source_file'],'path_id':cfg['path_id'],'is_imposter_default':cfg['is_imposter']},'game_object':{'path_id':c['game_object_path_id'],'name':c['game_object_name'],'active_self':h.get('active_self'),'active_in_hierarchy':h.get('active_in_hierarchy_from_serialized_ancestors'),'transform':xform(c['game_object_path_id'])},'button_reference':pp(raw,32),'image_reference':pp(raw,44),'initial_pose':initial,'poses':pose_list})
            used[cfg['name']]=cfg
    dialogs=[]; signs=[]; moves=[]; eyes=[]; anims=[]; scalers=[]
    for c in comps.values():
        r=c['raw']; n=c['class']; base={'component_path_id':c['path_id'],'game_object_path_id':c['game_object_path_id'],'game_object_name':c['game_object_name'],'raw_size':c['raw_size']}
        if n.endswith('.DialogView'):
            # PPtr fields are 12 bytes; the inline DialogOverlayData array and
            # AnimatedImage reference array are variable-length serialized fields.
            def ref_field(label,o):
                p=pp(r,o); return {'field':label,'offset':o,**p,**resolved(p)}
            overlay_count=struct.unpack_from('<i',r,56)[0]
            overlays=[]
            for i in range(overlay_count):
                o=60+i*40
                overlays.append({'array_index':i,'offset':o,'overlay_type_value':struct.unpack_from('<i',r,o)[0],'sprite':source_ref(pp(r,o+4)),'color':vec(r,o+16,4),'show_even_if_dialog_ended':bool(r[o+32]),'show_behind_texts_content':bool(r[o+33])})
            character_off=60+overlay_count*40
            bg_count=struct.unpack_from('<i',r,character_off+12)[0]
            bg_off=character_off+16
            bg_refs=[pp(r,bg_off+12*i) for i in range(bg_count)]
            tail=bg_off+12*bg_count
            fs={k:ref_field(k,o) for k,o in {'parent_canvas':32,'fake_dialog_runner':44,'character_animated_image':character_off,'overlay_image':tail,'raycast_blocker':tail+12,'dialog_panel_base':tail+24,'dialog_panel_answers':tail+36,'reserve_camera':tail+48}.items()}
            dialogs.append({**base,'serialized_fields':fs,'dialog_overlays':overlays,'background_characters':bg_refs,'array_offsets':{'dialog_overlays':56,'character':character_off,'background_characters':character_off+12}})
        elif n.endswith('.DialogSignsView'):
            names=['normal_text','text_container','eyes','hands','teeth','ear','armpit','photo']; fs=[]
            for i,k in enumerate(names):
                o=32+12*i;p=pp(r,o);fs.append({'field':k,'offset':o,**p,**resolved(p)})
            sound_arrays={}; off=128
            for k in ('eyes','teeth','hands','armpits','ear'):
                count=struct.unpack_from('<i',r,off)[0]
                if count<0 or count>1000: raise ValueError(f'invalid {k} sound array count {count} in {c["path_id"]}')
                sound_arrays[k]={'offset':off,'enum_values':list(struct.unpack_from('<'+'i'*count,r,off+4)) if count else []}
                off+=4+4*count
            signs.append({**base,'serialized_fields':fs,'sound_arrays':sound_arrays,'serialized_end_offset':off})
        elif n.endswith('.DialogSignElementViewMovingContent'):
            moves.append({**base,'content_image':pp(r,32),'start_position':vec(r,40,3),'end_position':vec(r,52,3),'ease_value':struct.unpack_from('<i',r,64)[0],'duration_seconds':clean(struct.unpack_from('<f',r,68)[0]),'before_delay_seconds':clean(struct.unpack_from('<f',r,72)[0])})
        elif n.endswith('.DialogSignElementViewEye'):
            eyes.append({**base,'content_image':pp(r,32),'animated_cover':pp(r,40),'white_image':pp(r,48),'iris_image':pp(r,56)})
        elif n.endswith('.AnimatedImage'):
            anims.append({**base,'image':pp(r,32),'play_from_awake':bool(r[44]),'animation_data_offset':45,'animation_data_decode':'variable-length struct; source CharacterSO animation data is in the character entries above'})
        elif n.endswith('.CanvasScaler'):
            # Unity UI CanvasScaler serialized field order; raw size 80 confirms
            # ten 4-byte fields after the standard 32-byte MonoBehaviour header.
            scalers.append({**base,'ui_scale_mode':struct.unpack_from('<i',r,32)[0],'reference_pixels_per_unit':clean(struct.unpack_from('<f',r,36)[0]),'scale_factor':clean(struct.unpack_from('<f',r,40)[0]),'reference_resolution':vec(r,44,2),'screen_match_mode':struct.unpack_from('<i',r,52)[0],'match_width_or_height':clean(struct.unpack_from('<f',r,56)[0]),'physical_unit':struct.unpack_from('<i',r,60)[0],'fallback_screen_dpi':clean(struct.unpack_from('<f',r,64)[0]),'default_sprite_dpi':clean(struct.unpack_from('<f',r,68)[0]),'dynamic_pixels_per_unit':clean(struct.unpack_from('<f',r,72)[0]),'field_offsets':{'ui_scale_mode':32,'reference_pixels_per_unit':36,'scale_factor':40,'reference_resolution':44,'screen_match_mode':52,'match_width_or_height':56,'physical_unit':60,'fallback_screen_dpi':64,'default_sprite_dpi':68,'dynamic_pixels_per_unit':72}})
    cameras=[]; canvases=[]
    for o in scene.objects.values():
        if o.type.name=='Camera':
            d=o.read_typetree(); gid=int(d['m_GameObject']['m_PathID']); cameras.append({'path_id':int(o.path_id),'game_object_path_id':gid,'game_object_name':gos.get(gid,{}).get('name'),'enabled':bool(d['m_Enabled']),'orthographic':bool(d['orthographic']),'orthographic_size':clean(d['orthographic size']),'field_of_view':clean(d['field of view']),'near_clip':d['near clip plane'],'far_clip':d['far clip plane'],'viewport':d['m_NormalizedViewPortRect']})
        elif o.type.name=='Canvas':
            d=o.read_typetree(); gid=int(d['m_GameObject']['m_PathID']); scaler=next((s for s in scalers if s['game_object_path_id']==gid),None); canvases.append({'path_id':int(o.path_id),'game_object_path_id':gid,'game_object_name':gos.get(gid,{}).get('name'),'enabled':bool(d['m_Enabled']),'render_mode':int(d['m_RenderMode']),'pixel_perfect':bool(d['m_PixelPerfect']),'plane_distance':float(d['m_PlaneDistance']),'sorting_order':int(d['m_SortingOrder']),'world_camera':d.get('m_Camera'),'resolved_world_camera':resolved({'file_id':0,'path_id':int(d.get('m_Camera',{}).get('m_PathID',0))}),'canvas_scaler':scaler})
    details=[]
    for name,cfg in sorted(used.items()):
        details.append({'character':name,'source':{'file':cfg['source_file'],'path_id':cfg['path_id']},'is_imposter_default':cfg['is_imposter'],'room_scale':cfg['room_scale'],'dialog_position':cfg['dialog_position'],'dialog_scale':cfg['dialog_scale'],'emotion_overrides':cfg['emotion_overrides'],'emotions':[e for e in emos.get(name,[])],'examination_assets':cfg['assets']})
    output={'schema_version':1,'provenance':{'method':'UnityPy static parsing of level1 and globalgamemanagers.assets; character and emotion records joined from decoded manifests; no game PE executed','source_manifests':['reconstruction/reverse-rooms/room_manifest.json','reconstruction/reverse-characters/character_configs.json','reconstruction/reverse-characters/emotion_registry.json'],'unity_files_read':['level1','globalgamemanagers.assets'],'level1_external_file_ids':{str(k):v for k,v in external_files.items()}},'counts':{'room_character_instances':len(instances),'unique_characters':len(used),'dialog_views':len(dialogs),'dialog_signs_views':len(signs),'moving_sign_components':len(moves),'eye_components':len(eyes),'animated_images':len(anims),'canvas_scalers':len(scalers),'cameras':len(cameras),'canvases':len(canvases)},'room_character_instances':instances,'characters':details,'dialog_views':dialogs,'dialog_signs_views':signs,'sign_movement_components':moves,'eye_components':eyes,'animated_images':anims,'canvas_scalers':scalers,'cameras':cameras,'canvases':canvases,'runtime_rules':{'room_pose':{'class':'_Code.Rooms.CharacterRoomObjectView','base':'_Code.Rooms.ARoomObjectView<ERoomPeopleState>','initial_state':'CharacterRoomObjectView._startState','states':'CharacterSOData.Poses','sprite':'matched RoomObjectState.Sprite assigned to inherited _image','transform':'localPosition=(PositionShift.x, PositionShift.y, 0); localScale=(ScaleShift.x, ScaleShift.y, 0)','cannot_interact':'selected pose CannotInteract makes TryStartDialog reject interaction'},'dialog_emotion':{'class':'_Code.DialogSystem.DialogView','method':'SetCharacterEmotion(EDialogEmotionState)','room_pose_sprite_is_separate':True,'source':'CharacterSOData.GetEmotion selects first matching emotion; AnimatedImage consumes returned AnimationData','override':'matching EmotionOverrides entry, otherwise zero DialogTransformData','position':'DialogTransformData.Position + CharacterSOData.DialogPosition','scale':'Vector3.one * CharacterSOData.DialogScale + DialogTransformData.Scale; multiplication occurs before override addition in the recovered native body','base_emotion_value':-1966747463},'examination':{'classes':['_Code.DialogSystem.Commands.DialogCommandsInstance.ShowSign','_Code.DialogSystem.DialogManager.OnSignShowed','_Code.DialogSystem.DialogSignsView.ShowSign'],'sign_enum':{'Eye':0,'Hands':1,'Teeth':2,'AuraPhoto':3,'Armpit':4,'Ear':5},'command_flow':'ShowSign resolves character by name from ICharactersSODataProvider, parses requested ECharacterSign, then raises SignShowed. DialogManager.OnSignShowed delegates to DialogView.ShowSign and marks the sign-shown runtime flag. No sign-specific unlock predicate appears in this path.','selector':'CharacterSOData getters select Human or Imposter sign asset according to runtime IsImposter','show':'DialogSignsView.ShowSign disables all sign containers, then activates the requested one and assigns its corresponding sprite/AnimationData','sign_specific_behavior':{'Eye':'white and iris sprites; MoveIris; random eyes sound','Hands':'assign sprite, run Move; random hands sound','Teeth':'assign sprite; random teeth sound','AuraPhoto':'assign photo sprite, run Move; no dedicated sound array','Armpit':'assign AnimatedContent AnimationData, start animation; random armpit sound','Ear':'assign AnimatedContent AnimationData, start animation; random ear sound'},'player_sign_state':'PlayerSigns stores fake-state booleans for Teeth, Hands, Eye, Armpit, and Photo; it has no Ear fake-state field. These flags describe player signs and do not gate the character ShowSign method.','movement_timing':'DialogSignElementViewMovingContent.Move waits BeforeDelay, then tweens Content from StartPosition to EndPosition with Ease for Duration seconds.','animation':'AnimationData contains CyclingType, Frames, and FPS; Duration is frame_count/FPS. StartAnimationOrSetFirstFrame special-cases Cycle by stopping and setting the first frame; other modes run StartPlayingAnimation. Runtime playback time is required.'},'camera_canvas':'DialogView.get_LastUsedCamera returns parentCanvas.worldCamera when parentCanvas exists, else null; reserve camera is separately serialized.'},'unknowns':['Runtime pose and IsImposter must be supplied by game state; initial pose and configured default are authored values only.','The renderer needs current Yarn execution/selected sign plus animation elapsed time for live examination state.','Android screen dimensions and safe area are runtime inputs; CanvasScaler references and camera settings are present in this manifest.','Eye movement uses random destinations and durations, so exact frame-by-frame replay needs RNG state.']}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');print(json.dumps(output['counts'],indent=2))
if __name__=='__main__':main()
