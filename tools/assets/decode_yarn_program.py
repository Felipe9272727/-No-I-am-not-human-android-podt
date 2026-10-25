#!/usr/bin/env python3
"""Decode Yarn Spinner Protocol Buffer program embedded in YarnProject MonoBehaviour.
Field numbers are based on the local generated YarnSpinner DiffableCs declarations."""
import json, struct, sys
from pathlib import Path
import UnityPy

def varint(b,i):
 v=0; shift=0
 while True:
  x=b[i]; i+=1; v|=(x&127)<<shift
  if x<128:return v,i
  shift+=7
  if shift>70: raise ValueError('oversized varint')
def fields(b):
 i=0
 while i<len(b):
  tag,i=varint(b,i); n=tag>>3; w=tag&7
  if w==0: v,i=varint(b,i)
  elif w==1: v=b[i:i+8]; i+=8
  elif w==2:
   z,i=varint(b,i); v=b[i:i+z]; i+=z
  elif w==5: v=b[i:i+4]; i+=4
  else: raise ValueError(f'unsupported wire type {w} at {i}')
  yield n,w,v

def s(b): return b.decode('utf-8','replace')
def parse_operand(b):
 for n,w,v in fields(b):
  if n==1:return {'string':s(v)}
  if n==2:return {'bool':bool(v)}
  if n==3:return {'float':struct.unpack('<f',v)[0]}
 return None
def parse_header(b):
 d={}
 for n,w,v in fields(b):
  if n in (1,2):d['key' if n==1 else 'value']=s(v)
 return d
def parse_instruction(b):
 op=0; args=[]
 for n,w,v in fields(b):
  if n==1:op=v
  elif n==2:args.append(parse_operand(v))
 return {'opcode':op,'op':OP.get(op,f'Unknown({op})'),'operands':args}
OP={0:'JumpTo',1:'Jump',2:'RunLine',3:'RunCommand',4:'AddOption',5:'ShowOptions',6:'PushString',7:'PushFloat',8:'PushBool',9:'PushNull',10:'JumpIfFalse',11:'Pop',12:'CallFunc',13:'PushVariable',14:'StoreVariable',15:'Stop',16:'RunNode'}
def parse_node(b):
 d={'instructions':[],'labels':{},'tags':[],'headers':[]}
 for n,w,v in fields(b):
  if n==1:d['name']=s(v)
  elif n==2:d['instructions'].append(parse_instruction(v))
  elif n==3:
   pair=list(fields(v)); key=s(pair[0][2]) if pair else ''; value=pair[1][2] if len(pair)>1 else 0; d['labels'][key]=value
  elif n==4:d['tags'].append(s(v))
  elif n==5:d['sourceTextStringID']=s(v)
  elif n==6:d['headers'].append(parse_header(v))
 return d
def parse_program(b):
 p={'nodes':{},'initialValues':{}}
 for n,w,v in fields(b):
  if n==1:p['name']=s(v)
  elif n==2:
   ent={}
   for en,ew,ev in fields(v):
    if en==1:ent['key']=s(ev)
    elif en==2:ent['value']=parse_node(ev)
   if 'key' in ent and 'value' in ent:p['nodes'][ent['key']]=ent['value']
  elif n==3:
   ent={}
   for en,ew,ev in fields(v):
    if en==1:ent['key']=s(ev)
    elif en==2:ent['value']=parse_operand(ev)
   if 'key' in ent and 'value' in ent:p['initialValues'][ent['key']]=ent['value']
 return p

src=Path(sys.argv[1]).resolve(); out=Path(sys.argv[2]).resolve(); out.mkdir(parents=True,exist_ok=True)
env=UnityPy.load(str(src)); obj=next(o for o in env.objects if o.path_id==2735)
raw=obj.get_raw_data()
# Unity MonoBehaviour serialized header: component refs + m_Name; YarnProject compiledYarnProgram follows as byte[].
# For this object the four-byte little-endian array length at offset 48 is validated against protobuf boundary.
length=struct.unpack_from('<I',raw,48)[0]
program_bytes=raw[52:52+length]
if len(program_bytes)!=length: raise ValueError('compiled program byte array truncated')
(out/'compiled_yarn_program.pb').write_bytes(program_bytes)
p=parse_program(program_bytes)
(out/'compiled_yarn_program.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
summary={'source':str(src),'object_path_id':2735,'object_raw_bytes':len(raw),'protobuf_offset':52,'protobuf_bytes':length,'program_name':p.get('name'),'node_count':len(p['nodes']),'initial_value_count':len(p['initialValues']),'instruction_count':sum(len(n['instructions']) for n in p['nodes'].values()),'nodes':[],'schema_source':'YarnSpinner/Yarn/Program.cs, Node.cs, Instruction.cs, Operand.cs, Header.cs in local generated DiffableCs'}
for name,node in p['nodes'].items():
 summary['nodes'].append({'name':name,'instructions':len(node['instructions']),'labels':len(node['labels']),'headers':node['headers'],'sourceTextStringID':node.get('sourceTextStringID')})
(out/'decoded_manifest.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in summary.items() if k not in ('nodes',)},indent=2))
print('first nodes:',json.dumps(summary['nodes'][:8],ensure_ascii=False))
