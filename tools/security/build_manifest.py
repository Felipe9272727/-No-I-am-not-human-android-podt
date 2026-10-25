import os,hashlib,subprocess,csv,json,zipfile,sys
root='/workspace/scratch/ad0b61c5ef81/malware-review/No.Im.not.a.Human.v1.3.18'
out='/workspace/scratch/ad0b61c5ef81/reconstruction/security'
def digest(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
rows=[]
for dp,_,fs in os.walk(root):
 for fn in fs:
  p=os.path.join(dp,fn); rel=os.path.relpath(p,root); size=os.path.getsize(p)
  desc=subprocess.run(['file','-b',p],capture_output=True,text=True).stdout.strip()
  with open(p,'rb') as f:
   head=f.read(8)
   f.seek(0)
   mz=f.read(2)==b'MZ'
   f.seek(0x3c)
   offraw=f.read(4)
   peoff=int.from_bytes(offraw,'little') if len(offraw)==4 else -1
   if 0 <= peoff <= size-4:
    f.seek(peoff)
    pe_sig=f.read(4)==b'PE\0\0'
   else:pe_sig=False
  magic=head.hex()
  kind='data'
  if mz and pe_sig:kind='native executable (Windows PE)'
  elif desc.startswith('PDF document'):kind='PDF document'
  elif 'Zip archive' in desc or '7-zip archive' in desc or 'Microsoft Cabinet' in desc:kind='archive/container'
  elif rel.lower().endswith(('.url','.bat','.cmd','.ps1','.vbs','.js','.hta','.sh','.py','.xml','.json','.txt')):kind='text/config/shortcut'
  elif '.assets' in rel or '/level' in rel or rel.endswith(('.bundle','.resource','.resS','.dat')):kind='Unity/game data'
  rows.append({'path':rel,'size':size,'sha256':digest(p),'magic_hex_first8':magic,'file_identification':desc,'classification':kind})
with open(out+'/file-manifest.csv','w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(sorted(rows,key=lambda r:r['path']))
# ZIP entry details from original archive, validate CRC on stream as read; do not extract or execute
zpath='/workspace/scratch/No.Im.not.a.Human.v1.3.18.zip'; zrows=[]
with zipfile.ZipFile(zpath) as z:
 for i in z.infolist():
  h=hashlib.sha256()
  if not i.is_dir():
   with z.open(i) as f:
    for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
  zrows.append({'path':i.filename,'size':i.file_size,'compressed_size':i.compress_size,'crc32':f'{i.CRC:08x}','sha256_uncompressed':h.hexdigest() if not i.is_dir() else '', 'zip_method':i.compress_type})
with open(out+'/zip-entry-manifest.csv','w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=zrows[0].keys());w.writeheader();w.writerows(zrows)
print('extracted files',len(rows),'PE by MZ+PE headers',sum(r['classification']=='native executable (Windows PE)' for r in rows),'zip entries',len(zrows),'zip files',sum(not i.is_dir() for i in z.infolist()),'zip dirs',sum(i.is_dir() for i in z.infolist()))
