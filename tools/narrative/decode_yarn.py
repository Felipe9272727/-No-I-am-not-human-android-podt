#!/usr/bin/env python3
"""Static decoder for Yarn protobuf embedded in a Unity YarnProject MonoBehaviour."""
import argparse, base64, collections, json, math, struct
from pathlib import Path

PROJECT_ROOT=Path(__file__).resolve().parents[2]
DEFAULT_IN=PROJECT_ROOT/'reconstruction/assets/narrative/monobehaviour_2735.bin'
DEFAULT_OUT=PROJECT_ROOT/'reconstruction/narrative/program.json'
OPCODES={0:'JumpTo',1:'Jump',2:'RunLine',3:'RunCommand',4:'AddOption',5:'ShowOptions',6:'PushString',7:'PushFloat',8:'PushBool',9:'PushNull',10:'JumpIfFalse',11:'Pop',12:'CallFunc',13:'PushVariable',14:'StoreVariable',15:'Stop',16:'RunNode'}
class DecodeError(ValueError): pass

def varint(b,p,end):
 v=0; shift=0; start=p
 while p<end and shift<70:
  x=b[p];p+=1;v|=(x&127)<<shift
  if x<128:return v,p
  shift+=7
 raise DecodeError(f'invalid/truncated varint at {start}')
def fields(b):
 p=0; end=len(b)
 while p<end:
  start=p; tag,p=varint(b,p,end); n=tag>>3; w=tag&7
  if n==0:raise DecodeError(f'zero field number at {start}')
  if w==0: val,p=varint(b,p,end)
  elif w==1:
   if p+8>end:raise DecodeError(f'truncated fixed64 field {n}')
   val=b[p:p+8];p+=8
  elif w==2:
   ln,p=varint(b,p,end)
   if ln>end-p:raise DecodeError(f'length overrun field {n} ({ln} > {end-p})')
   val=b[p:p+ln];p+=ln
  elif w==5:
   if p+4>end:raise DecodeError(f'truncated fixed32 field {n}')
   val=b[p:p+4];p+=4
  else:raise DecodeError(f'unsupported wire type {w} at {start}')
  yield n,w,val

def utf8(v):
 try:return v.decode('utf-8')
 except UnicodeDecodeError as e:raise DecodeError(f'invalid UTF-8 string: {e}')
def i32(v):return v-0x100000000 if v&0x80000000 else v
def unknown(n,w,v):
 d={'field':n,'wire_type':w}
 if w==2:d['raw_base64']=base64.b64encode(v).decode('ascii')
 elif w in (1,5):d['raw_hex']=v.hex()
 else:d['value']=v
 return d

def parse_operand(b):
 out=None; extras=[]
 for n,w,v in fields(b):
  if n==1 and w==2:out=utf8(v)
  elif n==2 and w==0:out=bool(v)
  elif n==3 and w==5:
   f=struct.unpack('<f',v)[0]
   if not math.isfinite(f):out={'float32_raw_hex':v.hex(),'non_finite':str(f)}
   else:out=f
  else:extras.append(unknown(n,w,v))
 return out,extras

def map_entry(b, parseval, value_wire=2):
 k=None;v=None; extras=[]
 for n,w,x in fields(b):
  if n==1 and w==2:k=utf8(x)
  elif n==2 and w==value_wire:v=parseval(x)
  else:extras.append(unknown(n,w,x))
 if k is None:raise DecodeError('map entry missing key')
 if v is None and value_wire==2:raise DecodeError(f'map entry {k!r} missing value')
 if v is None and value_wire==0:v=0
 return k,v,extras

def parse_header(b):
 d={'key':'','value':''};u=[]
 for n,w,v in fields(b):
  if n in (1,2) and w==2:d['key' if n==1 else 'value']=utf8(v)
  else:u.append(unknown(n,w,v))
 if u:d['_unknown_fields']=u
 return d

def parse_instruction(b):
 op=0; operands=[];u=[]
 for n,w,v in fields(b):
  if n==1 and w==0:op=i32(v)
  elif n==2 and w==2:
   x,extra=parse_operand(v);operands.append(x)
   if extra:operands[-1]={'value':x,'_unknown_fields':extra}
  else:u.append(unknown(n,w,v))
 d={'opcode':op,'operands':operands}
 if op in OPCODES:d['opcode_name']=OPCODES[op]
 else:d['_unknown_opcode']=True
 if u:d['_unknown_fields']=u
 return d

def parse_node(b):
 d={'name':'','instructions':[],'labels':{},'tags':[],'source_text_string_id':'','headers':[]};u=[]; dup=[]
 for n,w,v in fields(b):
  if n==1 and w==2:d['name']=utf8(v)
  elif n==2 and w==2:d['instructions'].append(parse_instruction(v))
  elif n==3 and w==2:
   k,x,extra=map_entry(v,lambda z:i32(z),0)
   if k in d['labels']:dup.append(k)
   d['labels'][k]=x
   if extra:u.append({'map_field':3,'entry_key':k,'unknown_fields':extra})
  elif n==4 and w==2:d['tags'].append(utf8(v))
  elif n==5 and w==2:d['source_text_string_id']=utf8(v)
  elif n==6 and w==2:d['headers'].append(parse_header(v))
  else:u.append(unknown(n,w,v))
 if dup:d['_duplicate_label_keys']=dup
 if u:d['_unknown_fields']=u
 return d

def parse_program(b):
 d={'name':'','nodes':{},'initial_values':{}};u=[];dups=[]
 for n,w,v in fields(b):
  if n==1 and w==2:d['name']=utf8(v)
  elif n==2 and w==2:
   k,x,extra=map_entry(v,parse_node)
   if k in d['nodes']:dups.append({'field':2,'key':k})
   d['nodes'][k]=x
   if extra:u.append({'map_field':2,'entry_key':k,'unknown_fields':extra})
  elif n==3 and w==2:
   k,parsed,extra=map_entry(v,parse_operand)
   x,operand_extra=parsed
   if k in d['initial_values']:dups.append({'field':3,'key':k})
   d['initial_values'][k]=x
   if extra or operand_extra:u.append({'map_field':3,'entry_key':k,'unknown_fields':extra+operand_extra})
  else:u.append(unknown(n,w,v))
 if dups:d['_duplicate_map_keys']=dups
 if u:d['_unknown_fields']=u
 return d

def extract_payload(blob):
 # Unity MonoBehaviour header: PPtr<GameObject> (12), enabled+padding (4), PPtr<MonoScript> (12), aligned m_Name.
 if len(blob)<32:raise DecodeError('blob shorter than expected Unity header')
 pos=12
 enabled=blob[pos];pos+=4
 script_file,script_path=struct.unpack_from('<Iq',blob,pos);pos+=12
 name_len=struct.unpack_from('<I',blob,pos)[0];pos+=4
 if name_len>len(blob)-pos:raise DecodeError('Unity m_Name length exceeds blob')
 unity_name=utf8(blob[pos:pos+name_len]);pos+=name_len
 pos=(pos+3)&~3
 if pos+4>len(blob):raise DecodeError('missing byte[] length prefix')
 length=struct.unpack_from('<I',blob,pos)[0];prefix_offset=pos;pos+=4
 if length>len(blob)-pos:raise DecodeError(f'compiledYarnProgram length {length} exceeds remaining blob {len(blob)-pos}')
 payload=blob[pos:pos+length]
 return payload,{'enabled':enabled,'script_pptr':{'file_id':script_file,'path_id':script_path},'unity_name':unity_name,'length_prefix_offset':prefix_offset,'payload_offset':pos,'payload_length':length,'trailing_serialized_bytes':len(blob)-pos-length}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,default=DEFAULT_IN);ap.add_argument('--output',type=Path,default=DEFAULT_OUT);args=ap.parse_args()
 blob=args.input.read_bytes();payload,header=extract_payload(blob);program=parse_program(payload)
 ops=collections.Counter(); commands=collections.Counter(); functions=collections.Counter(); nodes=program['nodes']
 for nd in nodes.values():
  for ins in nd['instructions']:
   op=ins['opcode'];ops[str(op)]+=1
   if op==3 and ins['operands']:commands[str(ins['operands'][0])]+=1
   if op==12 and ins['operands']:functions[str(ins['operands'][0])]+=1
 unknown_ops=sorted({int(k) for k in ops if int(k) not in OPCODES})
 summary={'program_name':program['name'],'node_count':len(nodes),'instruction_count':sum(ops.values()),'opcode_counts':{f'{k}:{OPCODES.get(int(k),"UNKNOWN")}':v for k,v in sorted(ops.items(),key=lambda x:int(x[0]))},'run_command_names':dict(sorted(commands.items())),'call_function_names':dict(sorted(functions.items())),'unknown_opcode_values':unknown_ops,'unknown_field_count':count_unknown(program),'payload_bytes':len(payload),'payload_sha256':__import__('hashlib').sha256(payload).hexdigest(),'unity_header':header,'schema_field_numbers':{'Program':{'name':1,'nodes':2,'initial_values':3},'Node':{'name':1,'instructions':2,'labels':3,'tags':4,'source_text_string_id':5,'headers':6},'Instruction':{'opcode':1,'operands':2},'Operand':{'string':1,'bool':2,'float32':3},'Header':{'key':1,'value':2}}}
 args.output.parent.mkdir(parents=True,exist_ok=True)
 args.output.write_text(json.dumps(program,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
 args.output.with_name('program_decode_report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
 print(json.dumps(summary,indent=2,ensure_ascii=False))

def count_unknown(x):
 if isinstance(x,dict):return sum(1 for k in x if k in ('_unknown_fields','_unknown_opcode'))+sum(count_unknown(v) for v in x.values())
 if isinstance(x,list):return sum(count_unknown(v) for v in x)
 return 0
if __name__=='__main__':main()
