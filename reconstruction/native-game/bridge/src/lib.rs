//! C ABI for the reconstructed C++ host. Original Windows libraries are not loaded.
use std::ffi::{c_char,c_void,CStr,CString};
use serde_json::{json,Value};
use yarn_runtime::{Runtime,Event};
use std::collections::HashMap;
const MAX_SNAPSHOT_BYTES: usize = 32 * 1024 * 1024;
#[repr(C)]
pub struct GameArg { tag:i32, number:f64, text:*const c_char }
pub type GameFunction=unsafe extern "C" fn(*mut c_void,*const c_char,*const GameArg,usize)->*const c_char;
#[derive(Clone,Debug,PartialEq)]
struct LineMetadata { node_name:String, tags:Vec<String> }
pub struct Handle { runtime:Runtime, metadata:HashMap<String,LineMetadata> }
fn owned(s:String)->*mut c_char{CString::new(s).expect("JSON is NUL-escaped").into_raw()}
fn annotate(value:&mut Value,metadata:&HashMap<String,LineMetadata>){
 let entry=value["line_id"].as_str().and_then(|id|metadata.get(id));
 value["metadata"]=entry.map(|m|json!({"node_name":m.node_name,"tags":m.tags})).unwrap_or(Value::Null);
}
fn error_event(error:String)->*mut c_char{owned(json!({"type":"error","error":error}).to_string())}
fn event(e:Event,metadata:&HashMap<String,LineMetadata>)->*mut c_char{
 let mut value=match e {
  Event::Line(l)=>json!({"type":"line","line_id":l.string_id,"substitutions":l.substitutions}),
  Event::Command(c)=>json!({"type":"command","command":c}),
  Event::Options(o)=>json!({"type":"options","options":o.into_iter().map(|o|json!({"line_id":o.line.string_id,"substitutions":o.line.substitutions,"destination":o.destination,"enabled":o.enabled})).collect::<Vec<_>>()}),
  Event::Stopped=>json!({"type":"stopped"}),Event::Error(e)=>json!({"type":"error","error":e}),
 };
 if value["type"]=="line" {annotate(&mut value,metadata)}
 if let Some(options)=value.get_mut("options").and_then(Value::as_array_mut){for option in options{annotate(option,metadata)}}
 owned(value.to_string())
}
fn parse_metadata(raw:&str)->Result<HashMap<String,LineMetadata>,String>{
 let value:Value=serde_json::from_str(raw).map_err(|e|e.to_string())?;
 let rows=value["line_metadata"].as_object().ok_or("line_metadata object required")?;
 let mut result=HashMap::new();
 for (id,row) in rows{
  let refs=row["metadata"].as_array().ok_or("metadata array required")?;
  if refs.len()!=1{return Err(format!("exactly one metadata record required: {id}"))}
  let node=refs[0]["node_name"].as_str().ok_or("node_name string required")?;
  let tags=refs[0]["tags"].as_array().ok_or("tags array required")?.iter()
   .map(|v|v.as_str().map(str::to_owned).ok_or_else(||"tag must be a string".to_string()))
   .collect::<Result<Vec<_>,_>>()?;
  result.insert(id.clone(),LineMetadata{node_name:node.to_owned(),tags});
 }Ok(result)
}
unsafe fn text<'a>(p:*const c_char)->Result<&'a str,String>{if p.is_null(){return Err("null UTF-8 pointer".into())}CStr::from_ptr(p).to_str().map_err(|e|e.to_string())}
/// All calls on one handle must be serialized and non-reentrant; callback/user lifetime covers
/// the handle. The host controls the thread on which its C++ callback executes.
#[no_mangle]
pub unsafe extern "C" fn ninah_yarn_create(program:*const c_char,user:*mut c_void,callback:Option<GameFunction>,error:*mut *mut c_char)->*mut Handle{
 if !error.is_null(){*error=std::ptr::null_mut()}
 let mut runtime=match text(program).and_then(Runtime::from_json_str){Ok(r)=>r,Err(e)=>{if !error.is_null(){*error=error_event(e)}return std::ptr::null_mut()}};
 if let Some(callback)=callback{
  let user_address=user as usize;
  runtime.set_function_handler(Box::new(move|name,args|{
   let name=CString::new(name).map_err(|e|e.to_string())?;
   let strings=args.iter().map(|a|CString::new(a.as_str().unwrap_or("")).map_err(|e|e.to_string())).collect::<Result<Vec<_>,_>>()?;
   let values=args.iter().zip(strings.iter()).map(|(a,s)|Ok(match a{
    Value::Null=>GameArg{tag:0,number:0.,text:std::ptr::null()},
    Value::Number(n)=>GameArg{tag:1,number:n.as_f64().ok_or("invalid number")?,text:std::ptr::null()},
    Value::Bool(b)=>GameArg{tag:2,number:if *b{1.}else{0.},text:std::ptr::null()},
    Value::String(_)=>GameArg{tag:3,number:0.,text:s.as_ptr()},
    _=>return Err("nonprimitive game argument".to_string()),
   })).collect::<Result<Vec<_>,String>>()?;
   let result=callback(user_address as *mut c_void,name.as_ptr(),values.as_ptr(),values.len());
   if result.is_null(){return Err("C++ game function unavailable".into())}
   let value:Value=serde_json::from_str(text(result)?).map_err(|e|e.to_string())?;
   if value.is_array()||value.is_object(){return Err("primitive game result required".into())}Ok(value)
  }));
 }Box::into_raw(Box::new(Handle{runtime,metadata:HashMap::new()}))
}
/// Loads the recovered LineMetadata export atomically. This exposes source tags;
/// it does not itself charge energy, execute commands, or synthesize missing tags.
#[no_mangle]
pub unsafe extern "C" fn ninah_yarn_load_line_metadata(h:*mut Handle,raw:*const c_char,error:*mut *mut c_char)->i32{
 if !error.is_null(){*error=std::ptr::null_mut()}
 let Some(h)=h.as_mut()else{if !error.is_null(){*error=error_event("null runtime".into())}return 0};
 match text(raw).and_then(parse_metadata){Ok(metadata)=>{h.metadata=metadata;1},Err(e)=>{if !error.is_null(){*error=error_event(e)}0}}
}
#[no_mangle]
pub unsafe extern "C" fn ninah_yarn_start(h:*mut Handle,node:*const c_char)->*mut c_char{let Some(h)=h.as_mut()else{return error_event("null runtime".into())};match text(node){Ok(n)=>event(h.runtime.start(n),&h.metadata),Err(e)=>error_event(e)}}
#[no_mangle]
pub unsafe extern "C" fn ninah_yarn_advance(h:*mut Handle)->*mut c_char{let Some(h)=h.as_mut()else{return error_event("null runtime".into())};event(h.runtime.advance(),&h.metadata)}
#[no_mangle]
pub unsafe extern "C" fn ninah_yarn_choose(h:*mut Handle,index:usize)->*mut c_char{let Some(h)=h.as_mut()else{return error_event("null runtime".into())};event(h.runtime.select_option(index),&h.metadata)}
/// Dump VM execution state. The returned JSON string uses `ninah_yarn_free_string` ownership.
/// Callback registrations and line metadata remain attached to the host handle, not the snapshot.
#[no_mangle]
pub unsafe extern "C" fn ninah_yarn_dump_snapshot(h:*mut Handle,error:*mut *mut c_char)->*mut c_char{
 if !error.is_null(){*error=std::ptr::null_mut()}
 let Some(h)=h.as_ref()else{if !error.is_null(){*error=error_event("null runtime".into())}return std::ptr::null_mut()};
 let encoded=match h.runtime.dump_snapshot(){Ok(snapshot)=>snapshot.to_string(),Err(e)=>{if !error.is_null(){*error=error_event(e)}return std::ptr::null_mut()}};
 if encoded.len()>MAX_SNAPSHOT_BYTES{if !error.is_null(){*error=error_event("snapshot exceeds 32 MiB limit".into())}return std::ptr::null_mut()}
 owned(encoded)
}
/// Restore VM execution state atomically. Returns 1 on success, 0 with an error event otherwise.
#[no_mangle]
pub unsafe extern "C" fn ninah_yarn_restore_snapshot(h:*mut Handle,snapshot:*const c_char,error:*mut *mut c_char)->i32{
 if !error.is_null(){*error=std::ptr::null_mut()}
 let Some(h)=h.as_mut()else{if !error.is_null(){*error=error_event("null runtime".into())}return 0};
 let result=text(snapshot).and_then(|raw|{
  if raw.len()>MAX_SNAPSHOT_BYTES{return Err("snapshot exceeds 32 MiB limit".into())}
  serde_json::from_str::<Value>(raw).map_err(|e|e.to_string())
 })
  .and_then(|value|h.runtime.restore_snapshot(&value));
 match result{Ok(())=>1,Err(e)=>{if !error.is_null(){*error=error_event(e)}0}}
}
#[no_mangle]
pub unsafe extern "C" fn ninah_yarn_free_string(p:*mut c_char){if !p.is_null(){drop(CString::from_raw(p))}}
#[no_mangle]
pub unsafe extern "C" fn ninah_yarn_destroy(h:*mut Handle){if !h.is_null(){drop(Box::from_raw(h))}}

#[cfg(test)]
mod tests {
 use super::*;
 unsafe fn take(raw:*mut c_char)->Value{let value=serde_json::from_str(CStr::from_ptr(raw).to_str().unwrap()).unwrap();ninah_yarn_free_string(raw);value}
 unsafe extern "C" fn energy(_: *mut c_void,name:*const c_char,_:*const GameArg,_:usize)->*const c_char{
  assert_eq!(CStr::from_ptr(name).to_str().unwrap(),"GetEnergy");b"4\0".as_ptr().cast()
 }
 #[test]
 fn original_choices_export_exact_source_tags(){unsafe{
  let program=CString::new(include_str!("../../../narrative/program.json")).unwrap();
  let raw=include_str!("../../../reverse-localization/line_metadata.json");
  let metadata=CString::new(raw).unwrap();let expected:Value=serde_json::from_str(raw).unwrap();
  let mut error=std::ptr::null_mut();let h=ninah_yarn_create(program.as_ptr(),std::ptr::null_mut(),Some(energy),&mut error);assert!(!h.is_null());
  assert_eq!(ninah_yarn_load_line_metadata(h,metadata.as_ptr(),&mut error),1);assert!(error.is_null());
  let node=CString::new("Alkonost_Asking_6").unwrap();let mut e=take(ninah_yarn_start(h,node.as_ptr()));
  for _ in 0..5{if e["type"]=="options"{break}assert_ne!(e["type"],"error");e=take(ninah_yarn_advance(h));}
  let options=e["options"].as_array().expect("original options");assert_eq!(options.len(),2);
  let mut charged=0;
  for option in options{let id=option["line_id"].as_str().unwrap();let source=&expected["line_metadata"][id]["metadata"][0];assert_eq!(option["metadata"]["tags"],source["tags"]);assert_eq!(option["metadata"]["node_name"],source["node_name"]);if source["tags"].as_array().unwrap().iter().any(|t|t=="energy"){charged+=1}}
  assert_eq!(charged,1);ninah_yarn_destroy(h);
 }}
 #[test]
 fn invalid_metadata_preserves_previous_catalog_and_unset_is_explicit(){unsafe{
  let p=CString::new(r#"{"nodes":{"N":{"instructions":[{"opcode":2,"operands":["line:one",0]}]}}}"#).unwrap();
  let mut error=std::ptr::null_mut();let h=ninah_yarn_create(p.as_ptr(),std::ptr::null_mut(),None,&mut error);assert!(!h.is_null());
  let node=CString::new("N").unwrap();assert!(take(ninah_yarn_start(h,node.as_ptr()))["metadata"].is_null());
  let good=CString::new(r#"{"line_metadata":{"line:one":{"metadata":[{"node_name":"N","tags":["energy"]}]}}}"#).unwrap();
  assert_eq!(ninah_yarn_load_line_metadata(h,good.as_ptr(),&mut error),1);
  let bad=CString::new(r#"{"line_metadata":{"line:other":{"metadata":[{"node_name":"N","tags":[false]}]}}}"#).unwrap();
  assert_eq!(ninah_yarn_load_line_metadata(h,bad.as_ptr(),&mut error),0);assert_eq!(take(error)["type"],"error");
  let e=take(ninah_yarn_start(h,node.as_ptr()));assert_eq!(e["metadata"]["tags"],json!(["energy"]));ninah_yarn_destroy(h);
 }}
 #[test]
 fn restore_after_reward_command_does_not_emit_the_command_again(){unsafe{
  let raw=r#"{"nodes":{"N":{"instructions":[{"opcode":3,"operands":["reward:energy",0]},{"opcode":2,"operands":["after-reward",0]},{"opcode":15,"operands":[]}]}}}"#;
  let program=CString::new(raw).unwrap();let mut error=std::ptr::null_mut();
  let first=ninah_yarn_create(program.as_ptr(),std::ptr::null_mut(),None,&mut error);assert!(!first.is_null());
  let node=CString::new("N").unwrap();
  assert_eq!(take(ninah_yarn_start(first,node.as_ptr()))["type"],"command");
  let snapshot=ninah_yarn_dump_snapshot(first,&mut error);assert!(!snapshot.is_null());assert!(error.is_null());
  let second=ninah_yarn_create(program.as_ptr(),std::ptr::null_mut(),None,&mut error);assert!(!second.is_null());
  assert_eq!(ninah_yarn_restore_snapshot(second,snapshot,&mut error),1);assert!(error.is_null());
  ninah_yarn_free_string(snapshot);
  assert_eq!(take(ninah_yarn_advance(second))["line_id"],"after-reward");
  ninah_yarn_destroy(first);ninah_yarn_destroy(second);
 }}
 #[test]
 fn restore_rejects_a_mismatched_graph_atomically(){unsafe{
  let a=CString::new(r#"{"nodes":{"N":{"instructions":[{"opcode":15,"operands":[]}]}}}"#).unwrap();
  let b=CString::new(r#"{"nodes":{"N":{"instructions":[{"opcode":2,"operands":["other",0]}]}}}"#).unwrap();
  let mut error=std::ptr::null_mut();let source=ninah_yarn_create(a.as_ptr(),std::ptr::null_mut(),None,&mut error);let target=ninah_yarn_create(b.as_ptr(),std::ptr::null_mut(),None,&mut error);
  let snapshot=ninah_yarn_dump_snapshot(source,&mut error);assert_eq!(ninah_yarn_restore_snapshot(target,snapshot,&mut error),0);
  assert!(take(error)["error"].as_str().unwrap().contains("identity mismatch"));ninah_yarn_free_string(snapshot);
  assert_eq!(take(ninah_yarn_start(target,CString::new("N").unwrap().as_ptr()))["line_id"],"other");
  ninah_yarn_destroy(source);ninah_yarn_destroy(target);
 }}
}
