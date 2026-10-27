#!/usr/bin/env python3
"""Static level1 export with direct MeshHandler source buffers; never executes original binaries."""
import argparse,json,math,hashlib,re,struct
from pathlib import Path
import UnityPy
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
DEFAULT=ROOT/'malware-review/No.Im.not.a.Human.v1.3.18/No.Im.not.a.Human.v1.3.18/NoImNotAHuman_Data'
OUT=ROOT/'reconstruction/reverse-world'
def vec(v):
 try:return [float(x) for x in v]
 except TypeError:return [float(getattr(v,k)) for k in ('x','y','z','w') if hasattr(v,k)]
def ref(p):return {'file_id':int(p.m_FileID),'path_id':int(p.m_PathID)}
def objname(p):
 try:return str(getattr(p.read(),'m_Name',''))
 except:return ''
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--data',type=Path,default=DEFAULT);ap.add_argument('--out',type=Path,default=OUT);a=ap.parse_args();out=a.out
 for d in ('models','textures'):(out/d).mkdir(parents=True,exist_ok=True)
 env=UnityPy.load(str(a.data/'level1'));objects=list(env.objects);byid={o.path_id:o for o in objects}
 def read(o):
  try:return o.read()
  except:return None
 gos={};trans={};compgo={};compbygo={}
 for o in objects:
  d=read(o)
  if o.type.name=='GameObject' and d:gos[o.path_id]=d
  if o.type.name in ('Transform','RectTransform') and d:trans[o.path_id]=d;compgo[o.path_id]=d.m_GameObject.m_PathID
 for goid,g in gos.items():compbygo[goid]=[x.component.m_PathID for x in g.m_Component]
 def active(goid,seen=None):
  seen=seen or set()
  if goid in seen:return False
  seen.add(goid);g=gos.get(goid)
  if not g or not g.m_IsActive:return False
  t=next((trans.get(x) for x in compbygo[goid] if x in trans),None)
  if t and t.m_Father.m_PathID:
   parent=compgo.get(t.m_Father.m_PathID);return active(parent,seen) if parent else True
  return True
 wc={}
 def worldmat(tid):
  if tid in wc:return wc[tid]
  t=trans[tid];p=vec(t.m_LocalPosition);q=vec(t.m_LocalRotation);s=vec(t.m_LocalScale);x,y,z,w=q;sx,sy,sz=s
  m=[[(1-2*(y*y+z*z))*sx,(2*(x*y-z*w))*sy,(2*(x*z+y*w))*sz,p[0]],[(2*(x*y+z*w))*sx,(1-2*(x*x+z*z))*sy,(2*(y*z-x*w))*sz,p[1]],[(2*(x*z-y*w))*sx,(2*(y*z+x*w))*sy,(1-2*(x*x+y*y))*sz,p[2]],[0,0,0,1]]
  f=t.m_Father.m_PathID
  if f and f in trans:
   pp=worldmat(f);m=[[sum(pp[i][k]*m[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
  wc[tid]=m;return m
 transforms=[]
 for tid,t in trans.items():
  gid=compgo[tid];transforms.append({'path_id':tid,'gameobject_path_id':gid,'name':gos[gid].m_Name if gid in gos else '', 'parent_path_id':int(t.m_Father.m_PathID),'local_position':vec(t.m_LocalPosition),'local_rotation_xyzw':vec(t.m_LocalRotation),'local_scale':vec(t.m_LocalScale),'world_matrix_row_major':worldmat(tid)})
 meshes=[];meshmap={};materials=[];matmap={};textures=[];texmap={};errors=[]
 def mesh_export(ptr):
  key=(getattr(ptr.assetsfile,'name',''),ptr.m_FileID,ptr.m_PathID)
  if key in meshmap:return meshmap[key]
  try:
   from UnityPy.helpers.MeshHelper import MeshHandler
   m=ptr.read();h=MeshHandler(m);h.process();vs=h.m_Vertices or [];ns=h.m_Normals or [];uvs=h.m_UV0 or [];subs=h.get_triangles();verts=[];indices=[];outsubs=[]
   for tris in subs:
    start=len(indices)
    for tri in tris:
     if len(tri)!=3:continue
     for vi in tri:
      p=vec(vs[vi]) if vi<len(vs) else [0,0,0];n=vec(ns[vi]) if vi<len(ns) else [0,0,0];uv=vec(uvs[vi])[:2] if vi<len(uvs) else [0,0]
      verts.append(p[:3]+n[:3]+(uv+[0,0])[:2]);indices.append(len(verts)-1)
    outsubs.append({'index_start':start,'index_count':len(indices)-start,'topology':'triangles'})
   if not verts:raise ValueError('MeshHandler has no triangles')
   raw=bytearray()
   for v in verts:raw.extend(struct.pack('<8f',*v))
   for ix in indices:raw.extend(struct.pack('<I',ix))
   fn=f"mesh_{re.sub(r'[^A-Za-z0-9_-]+','_',key[0])}_f{key[1]}_p{key[2]}.bin";(out/'models'/fn).write_bytes(raw)
   idx=len(meshes);meshmap[key]=idx
   bounds={'min':[min(v[i] for v in vs) for i in range(3)],'max':[max(v[i] for v in vs) for i in range(3)]} if vs else None
   meshes.append({'source_ref':{'source_file':key[0],'file_id':key[1],'path_id':key[2]},'name':getattr(m,'m_Name',''),'mesh_asset':'models/'+fn,'vertex_count':len(verts),'index_count':len(indices),'vertex_stride_bytes':32,'vertex_layout':['position_f32x3','normal_f32x3','uv0_f32x2'],'index_type':'uint32_le','submeshes':outsubs,'local_bounds':bounds,'sha256':hashlib.sha256(raw).hexdigest()});return idx
  except Exception as e:errors.append({'kind':'mesh','ref':key,'error':str(e)});return None
 def texture(ptr):
  key=(getattr(ptr.assetsfile,'name',''),ptr.m_FileID,ptr.m_PathID)
  if key in texmap:return texmap[key]
  try:
   t=ptr.read();im=t.image;pixel_hash=hashlib.sha256(im.tobytes()).hexdigest()[:12];fn=f"texture_{re.sub(r'[^A-Za-z0-9_-]+','_',key[0])}_f{key[1]}_p{key[2]}_{pixel_hash}_{re.sub(r'[^A-Za-z0-9_-]+','_',t.m_Name)[:48]}.png";path=out/'textures'/fn;import io;bio=io.BytesIO();im.save(bio,format='PNG');png_bytes=bio.getvalue();tmp=path.with_suffix('.png.tmp');tmp.write_bytes(png_bytes);tmp.replace(path);i=len(textures);texmap[key]=i;sett=t.m_TextureSettings
   textures.append({'source_ref':{'source_file':key[0],'file_id':key[1],'path_id':key[2]},'name':t.m_Name,'asset':'textures/'+fn,'android_asset':'textures/'+fn,'width':int(t.m_Width),'height':int(t.m_Height),'mode':im.mode,'sampler':{'filter_mode':int(sett.m_FilterMode),'aniso':int(sett.m_Aniso),'mip_bias':float(sett.m_MipBias),'wrap_u':int(sett.m_WrapU),'wrap_v':int(sett.m_WrapV),'wrap_w':int(sett.m_WrapW)},'sha256':hashlib.sha256(png_bytes).hexdigest()});return i
  except Exception as e:errors.append({'kind':'texture','ref':key,'error':str(e)});return None
 def material(ptr):
  key=(getattr(ptr.assetsfile,'name',''),ptr.m_FileID,ptr.m_PathID)
  if key in matmap:return matmap[key]
  try:
   m=ptr.read();sh=m.m_Shader.read();parsed=getattr(sh,'m_ParsedForm',None);saved=m.m_SavedProperties;d={'source_ref':{'source_file':key[0],'file_id':key[1],'path_id':key[2]},'name':m.m_Name,'shader_ref':ref(m.m_Shader),'shader_name':getattr(parsed,'m_Name',None) or objname(m.m_Shader),'color':[1,1,1,1],'color_properties':{},'float_properties':dict(getattr(saved,'m_Floats',[]) or []),'int_properties':dict(getattr(saved,'m_Ints',[]) or []),'texture_refs':[],'custom_render_queue':getattr(m,'m_CustomRenderQueue',None),'string_tags':dict(getattr(m,'stringTagMap',[]) or []),'shader_keywords':list(getattr(m,'m_ValidKeywords',[]) or []),'double_sided_gi':bool(getattr(m,'m_DoubleSidedGI',False))}
   for prop,v in getattr(saved,'m_Colors',[]):
    c=[float(v.r),float(v.g),float(v.b),float(v.a)];d['color_properties'][str(prop)]=c
    if prop in ('_Color','_BaseColor'):d['color']=c
   for prop,v in getattr(saved,'m_TexEnvs',[]):
    tex=getattr(v,'m_Texture',None)
    if tex and tex.m_PathID:
     ti=texture(tex);d['texture_refs'].append({'property':str(prop),'ref':ref(tex),'texture_index':ti,'asset':textures[ti]['asset'] if ti is not None else None,'sha256':textures[ti]['sha256'] if ti is not None else None,'scale':vec(v.m_Scale),'offset':vec(v.m_Offset),'name':objname(tex)})
   i=len(materials);materials.append(d);matmap[key]=i;return i
  except Exception as e:errors.append({'kind':'material','ref':key,'error':str(e)});return None
 renderers=[]
 for o in objects:
  if o.type.name!='MeshRenderer':continue
  d=read(o)
  if not d:continue
  gid=d.m_GameObject.m_PathID;comps=compbygo.get(gid,[]);mf=next((read(byid[x]) for x in comps if x in byid and byid[x].type.name=='MeshFilter'),None)
  if mf is None:continue
  mi=mesh_export(mf.m_Mesh);tid=next((x for x in comps if x in trans),None);mats=[material(x) for x in d.m_Materials];g=gos.get(gid)
  renderers.append({'renderer_path_id':o.path_id,'gameobject_path_id':gid,'name':g.m_Name if g else '', 'layer':g.m_Layer if g else None,'tag':g.m_Tag if g else None,'active_in_hierarchy':active(gid),'transform_path_id':tid,'mesh_index':mi,'material_indices':mats,'enabled':bool(d.m_Enabled),'world_matrix_row_major':worldmat(tid) if tid in trans else None})
 # Unity stores the visible miner as a SkinnedMeshRenderer. Bake the serialized
 # bone transforms and bind poses into renderer-local vertices so the Android
 # renderer can draw this exact authored pose without pretending to evaluate
 # its Animator. Inactive skinned renderers remain represented but are gated
 # by the same source active/enabled flags as ordinary renderers.
 skinned_renderers=[]
 from UnityPy.helpers.MeshHelper import MeshHandler
 def matrix4(value):
  return np.array([[float(getattr(value,f'e{row}{col}')) for col in range(4)] for row in range(4)],dtype=np.float64)
 def local4(t):
  p=vec(t.m_LocalPosition);q=vec(t.m_LocalRotation);s=vec(t.m_LocalScale);x,y,z,w=q
  m=np.eye(4,dtype=np.float64)
  m[:3,:3]=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])@np.diag(s)
  m[:3,3]=p[:3]
  return m
 skinned=[]
 for o in objects:
  if o.type.name!='SkinnedMeshRenderer':continue
  d=read(o)
  if not d or not d.m_Mesh:continue
  gid=int(d.m_GameObject.m_PathID);g=gos.get(gid);tid=next((x for x in compbygo.get(gid,[]) if x in trans),None)
  if tid is None:errors.append({'kind':'skinned_renderer','ref':int(o.path_id),'error':'missing renderer transform'});continue
  renderer_row={'renderer_path_id':int(o.path_id),'gameobject_path_id':gid,'name':g.m_Name if g else '', 'layer':g.m_Layer if g else None,'tag':g.m_Tag if g else None,'active_in_hierarchy':active(gid),'transform_path_id':tid,'mesh_index':None,'material_indices':[],'enabled':bool(d.m_Enabled),'world_matrix_row_major':worldmat(tid),'pose_mode':'source_mesh_not_baked_inactive'}
  if not renderer_row['active_in_hierarchy'] or not renderer_row['enabled']:
   skinned_renderers.append(renderer_row);continue
  try:
   source_mesh=d.m_Mesh.read();handler=MeshHandler(source_mesh);handler.process()
   verts=np.asarray(handler.m_Vertices,dtype=np.float64);normals=np.asarray(handler.m_Normals,dtype=np.float64);uvs=np.asarray(handler.m_UV0,dtype=np.float64)
   weights=np.asarray(handler.m_BoneWeights,dtype=np.float64);bone_indices=np.asarray(handler.m_BoneIndices,dtype=np.int64)
   if len(verts)==0 or len(normals)!=len(verts) or len(uvs)!=len(verts) or len(weights)!=len(verts) or len(bone_indices)!=len(verts):raise ValueError('incomplete skinned vertex attributes')
   if len(d.m_Bones)!=len(source_mesh.m_BindPose):raise ValueError('bone and bind-pose counts differ')
   renderer_world=np.asarray(worldmat(tid),dtype=np.float64);renderer_inverse=np.linalg.inv(renderer_world)
   bone_matrices=[]
   for bone,bindpose in zip(d.m_Bones,source_mesh.m_BindPose):
    bid=int(bone.m_PathID)
    if bid not in trans:raise ValueError(f'missing bone transform {bid}')
    bone_matrices.append(renderer_inverse@np.asarray(worldmat(bid),dtype=np.float64)@matrix4(bindpose))
   if not np.allclose(weights.sum(axis=1),1.0,atol=1e-4):raise ValueError('skin weights do not sum to one')
   if np.any(bone_indices<0) or np.any(bone_indices>=len(bone_matrices)):raise ValueError('skin weights refer to invalid bone')
   baked_pos=np.zeros((len(verts),3),dtype=np.float64);baked_norm=np.zeros((len(verts),3),dtype=np.float64)
   for vi,(v,n,ws,bs) in enumerate(zip(verts,normals,weights,bone_indices)):
    for weight,bone_idx in zip(ws,bs):
     if weight<=0:continue
     bm=bone_matrices[int(bone_idx)];baked_pos[vi]+=weight*(bm@np.r_[v[:3],1.0])[:3];baked_norm[vi]+=weight*(bm[:3,:3]@n[:3])
    length=np.linalg.norm(baked_norm[vi])
    if length:baked_norm[vi]/=length
   triangles=handler.get_triangles();flat_indices=[];subs=[]
   for group in triangles:
    start=len(flat_indices)
    for tri in group:
     if len(tri)==3:flat_indices.extend(int(i) for i in tri)
    subs.append({'index_start':start,'index_count':len(flat_indices)-start,'topology':'triangles'})
   if not flat_indices:raise ValueError('skinned mesh has no triangles')
   raw=bytearray()
   for p,n,uv in zip(baked_pos,baked_norm,uvs):raw.extend(struct.pack('<8f',*p,*n,*uv[:2]))
   for ix in flat_indices:raw.extend(struct.pack('<I',ix))
   source_ref=ref(d.m_Mesh);fn=f"skinned_{re.sub(r'[^A-Za-z0-9_-]+','_',getattr(d.m_Mesh.assetsfile,'name',''))}_f{source_ref['file_id']}_p{source_ref['path_id']}_renderer{o.path_id}.bin"
   (out/'models'/fn).write_bytes(raw);bounds={'min':[float(baked_pos[:,i].min()) for i in range(3)],'max':[float(baked_pos[:,i].max()) for i in range(3)]}
   mesh_index=len(meshes);meshes.append({'source_ref':{'source_file':getattr(d.m_Mesh.assetsfile,'name',''),'file_id':source_ref['file_id'],'path_id':source_ref['path_id']},'name':getattr(source_mesh,'m_Name','')+' [serialized skin pose]','mesh_asset':'models/'+fn,'vertex_count':len(baked_pos),'index_count':len(flat_indices),'vertex_stride_bytes':32,'vertex_layout':['position_f32x3','normal_f32x3','uv0_f32x2'],'index_type':'uint32_le','submeshes':subs,'local_bounds':bounds,'sha256':hashlib.sha256(raw).hexdigest(),'skinned_pose_bake':{'renderer_path_id':int(o.path_id),'source_bones':len(d.m_Bones),'source_bindposes':len(source_mesh.m_BindPose),'pose_source':'serialized Unity bone transforms; Animator not evaluated'}})
   renderer_row.update({'mesh_index':mesh_index,'material_indices':[material(x) for x in d.m_Materials],'pose_mode':'serialized_bone_pose_baked_without_animator'});skinned_renderers.append(renderer_row)
  except Exception as e:errors.append({'kind':'skinned_renderer','ref':int(o.path_id),'error':str(e)})
 colliders=[]
 for o in objects:
  if o.type.name not in ('BoxCollider','MeshCollider','CapsuleCollider','SphereCollider'):continue
  d=read(o);gid=d.m_GameObject.m_PathID;tid=next((x for x in compbygo.get(gid,[]) if x in trans),None);g=gos.get(gid);r={'type':o.type.name,'path_id':o.path_id,'gameobject_path_id':gid,'name':g.m_Name if g else '', 'layer':g.m_Layer if g else None,'tag':g.m_Tag if g else None,'active_in_hierarchy':active(gid),'enabled':bool(d.m_Enabled),'is_trigger':bool(d.m_IsTrigger),'transform_path_id':tid,'world_matrix_row_major':worldmat(tid) if tid in trans else None}
  for attr in ('m_Center','m_Size','m_Radius','m_Height','m_Direction','m_Convex'):
   if hasattr(d,attr):r[attr[2:].lower()]=vec(getattr(d,attr)) if attr in ('m_Center','m_Size') else getattr(d,attr)
  if hasattr(d,'m_Mesh'):r.update({'mesh_ref':ref(d.m_Mesh),'mesh_name':objname(d.m_Mesh),'mesh_asset_index':mesh_export(d.m_Mesh) if d.m_Mesh.m_PathID else None})
  colliders.append(r)
 cameras=[];lights=[];settings=[];rigidbodies=[]
 for o in objects:
  if o.type.name=='Camera':
   d=read(o);gid=d.m_GameObject.m_PathID;tid=next((x for x in compbygo.get(gid,[]) if x in trans),None);g=gos.get(gid);c={'path_id':o.path_id,'name':g.m_Name if g else '', 'gameobject_path_id':gid,'transform_path_id':tid,'active_in_hierarchy':active(gid),'world_matrix_row_major':worldmat(tid) if tid in trans else None,'field_of_view':float(d.field_of_view),'near_clip':float(d.near_clip_plane),'far_clip':float(d.far_clip_plane),'orthographic':bool(d.orthographic),'enabled':bool(d.m_Enabled)};cameras.append(c)
  elif o.type.name=='Light':
   d=read(o);gid=d.m_GameObject.m_PathID;tid=next((x for x in compbygo.get(gid,[]) if x in trans),None);g=gos.get(gid);c=d.m_Color;lights.append({'path_id':o.path_id,'gameobject_path_id':gid,'name':g.m_Name if g else '', 'layer':g.m_Layer if g else None,'tag':g.m_Tag if g else None,'enabled':bool(d.m_Enabled),'active_in_hierarchy':active(gid),'transform_path_id':tid,'world_matrix_row_major':worldmat(tid) if tid in trans else None,'type':int(d.m_Type),'color':[float(c.r),float(c.g),float(c.b),float(c.a)],'intensity':float(d.m_Intensity),'range':float(d.m_Range),'spot_angle':float(d.m_SpotAngle),'inner_spot_angle':float(getattr(d,'m_InnerSpotAngle',d.m_SpotAngle)),'shadows':{'type':int(d.m_Shadows.m_Type),'strength':float(d.m_Shadows.m_Strength),'bias':float(d.m_Shadows.m_Bias)}})
  elif o.type.name=='RenderSettings':
   d=read(o);color=lambda c:[float(c.r),float(c.g),float(c.b),float(c.a)] if c else None;settings.append({'path_id':o.path_id,'fog':bool(d.m_Fog),'fog_color':color(d.m_FogColor),'fog_mode':int(d.m_FogMode),'fog_density':float(d.m_FogDensity),'linear_fog_start':float(d.m_LinearFogStart),'linear_fog_end':float(d.m_LinearFogEnd),'ambient_mode':int(d.m_AmbientMode),'ambient_intensity':float(d.m_AmbientIntensity),'ambient_sky_color':color(d.m_AmbientSkyColor),'ambient_equator_color':color(d.m_AmbientEquatorColor),'ambient_ground_color':color(d.m_AmbientGroundColor),'reflection_intensity':float(d.m_ReflectionIntensity),'reflection_bounces':int(d.m_ReflectionBounces),'skybox_material_ref':ref(d.m_SkyboxMaterial) if d.m_SkyboxMaterial else None})
  elif o.type.name=='Rigidbody':
   d=read(o);gid=d.m_GameObject.m_PathID;g=gos.get(gid);rigidbodies.append({'path_id':o.path_id,'gameobject_path_id':gid,'name':g.m_Name if g else '', 'mass':float(d.m_Mass),'drag':float(d.m_Drag if d.m_Drag is not None else getattr(d,'m_LinearDamping',0)),'angular_drag':float(d.m_AngularDrag if d.m_AngularDrag is not None else getattr(d,'m_AngularDamping',0)),'use_gravity':bool(d.m_UseGravity),'is_kinematic':bool(d.m_IsKinematic),'constraints':int(d.m_Constraints)})
 maincam=next((c for c in cameras if c['name']=='Main Camera'),None);campos=[maincam['world_matrix_row_major'][i][3] for i in range(3)] if maincam else None
 def point(m,p):return [sum(m[i][j]*([p[0],p[1],p[2],1][j]) for j in range(4)) for i in range(3)]
 for r in renderers:
  mi=r['mesh_index'];m=r['world_matrix_row_major']
  if mi is not None and m is not None and meshes[mi]['local_bounds']:
   b=meshes[mi]['local_bounds'];pts=[point(m,[b['min'][0] if not i&1 else b['max'][0],b['min'][1] if not i&2 else b['max'][1],b['min'][2] if not i&4 else b['max'][2]]) for i in range(8)];r['world_bounds']={'min':[min(p[j] for p in pts) for j in range(3)],'max':[max(p[j] for p in pts) for j in range(3)]};center=[(r['world_bounds']['min'][j]+r['world_bounds']['max'][j])/2 for j in range(3)];r['main_camera_bounds_center_distance']=math.sqrt(sum((center[j]-campos[j])**2 for j in range(3))) if campos else None
  else:r['world_bounds']=None;r['main_camera_bounds_center_distance']=None
 doors=[]
 for gid,g in gos.items():
  if not re.search(r'^(Door|door)\s*\d+',g.m_Name):continue
  root_tid=next((x for x in compbygo.get(gid,[]) if x in trans),None);desc=[]
  if root_tid:
   todo=[root_tid]
   while todo:
    tid=todo.pop();desc.append(compgo[tid]);todo.extend(ch.m_PathID for ch in trans[tid].m_Children if ch.m_PathID in trans)
  doors.append({'gameobject_path_id':gid,'name':g.m_Name,'active_in_hierarchy':active(gid),'descendant_gameobject_path_ids':desc,'component_path_ids':[x for gg in desc for x in compbygo.get(gg,[])],'transform':next((t for t in transforms if t['gameobject_path_id']==gid),None),'colliders':[c for c in colliders if c['gameobject_path_id'] in desc]})
 interaction_targets=[{'kind':'door','id':d['gameobject_path_id'],'label':d['name'],'transform_path_id':d['transform']['path_id'] if d['transform'] else None,'world_matrix_row_major':d['transform']['world_matrix_row_major'] if d['transform'] else None,'room':d['name'][d['name'].find('(')+1:d['name'].rfind(')')] if '(' in d['name'] and ')' in d['name'] else None,'collider_path_ids':[c['path_id'] for c in d['colliders']],'trigger_collider_path_ids':[c['path_id'] for c in d['colliders'] if c['is_trigger']],'colliders':[{'path_id':c['path_id'],'name':c['name'],'is_trigger':c['is_trigger']} for c in d['colliders']]} for d in doors]
 for c in colliders:
  if c['name'] in ('RaycastTrigger','RaycastTarget') and not any(c['path_id'] in x['collider_path_ids'] for x in interaction_targets):
   interaction_targets.append({'kind':'raycast_target','id':c['gameobject_path_id'],'label':c['name'],'transform_path_id':c['transform_path_id'],'world_matrix_row_major':c['world_matrix_row_major'],'collider_path_ids':[c['path_id']],'trigger_collider_path_ids':[c['path_id']] if c['is_trigger'] else [],'colliders':[{'path_id':c['path_id'],'name':c['name'],'is_trigger':c['is_trigger']}]})
 scene_path=a.data if a.data.is_file() else a.data/'level1'
 manifest={'schema_version':1,'provenance':{'scene_file':'level1','source_scene_sha256':hashlib.sha256(scene_path.read_bytes()).hexdigest(),'tool':'UnityPy 1.25.4 static parser','executed_original_binaries':False},'coordinate_system':{'source':'Unity left-handed, Y-up, metres','export':'Unconverted Unity source coordinates','uv_origin':'Unity UV convention (0,0 bottom-left)','matrix':'row-major 4x4 column-vector transform; local TRS composed parent-first','triangle_winding':'Unity MeshHandler source triangles/winding preserved; renderer must reflect coordinates and winding together when converting handedness','binary':'interleaved LE float32 position3 normal3 uv0_2 (32 bytes), then LE uint32 indices; expanded face corners'},'counts':{'gameobjects':len(gos),'transforms':len(trans),'mesh_renderers':len(renderers),'renderers_active':sum(r['active_in_hierarchy'] for r in renderers),'skinned_mesh_renderers':len(skinned_renderers),'skinned_renderers_active':sum(r['active_in_hierarchy'] and r['enabled'] for r in skinned_renderers),'renderers_active_within_40m_main_camera':sum(r['active_in_hierarchy'] and r['main_camera_bounds_center_distance'] is not None and r['main_camera_bounds_center_distance']<=40 for r in renderers),'mesh_filters':sum(o.type.name=='MeshFilter' for o in objects),'unique_meshes':len(meshes),'materials':len(materials),'textures':len(textures),'colliders':len(colliders),'cameras':len(cameras),'lights':len(lights),'mesh_errors':sum(e['kind'] in ('mesh','skinned_renderer') for e in errors)},'meshes':meshes,'materials':materials,'textures':textures,'renderers':renderers,'skinned_renderers':skinned_renderers,'transforms':transforms,'colliders':colliders,'cameras':cameras,'lights':lights,'render_settings':settings,'rigidbodies':rigidbodies,'spawn_candidates':[t for t in transforms if t['name'] in ('StartPoint','SaveStartPoint','BasementStartPoint')],'player_instance':next((t for t in transforms if t['name']=='PlayerInstance'),None),'named_door_targets':doors,'interaction_targets':interaction_targets,'exclusions':['ParticleSystemRenderer and VFXRenderer are dynamic and not flattened.','Skinned meshes are baked at serialized bone transforms; Animator playback is not evaluated.','Static data does not determine runtime initial spawn or door activation.'],'errors':errors}
 (out/'world_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n');print(json.dumps(manifest['counts'],indent=2));print('Main Camera',maincam);print('texture_MB',sum((out/t['asset']).stat().st_size for t in textures)/1e6,'mesh_MB',sum((out/m['mesh_asset']).stat().st_size for m in meshes)/1e6)
if __name__=='__main__':main()
