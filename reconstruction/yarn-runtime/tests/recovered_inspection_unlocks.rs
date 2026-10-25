use serde_json::Value;
use yarn_runtime::{Event,Runtime};
#[test]
fn original_tv_bytecode_unlocks_inspections_without_forcing_flags(){
 let p:Value=serde_json::from_str(include_str!("../../narrative/program.json")).unwrap();
 let mut vm=Runtime::new(p).unwrap();
 for (index,(node,flag)) in [("tv_2_necessary","$teethCheck"),("tv_3_necessary","$handsCheck"),("tv_4_necessary","$eyesCheck"),("tv_5_necessary","$armpitsCheck")].iter().enumerate(){
  let mut event=vm.start(node);let mut stopped=false;
  for _ in 0..200{match event{Event::Stopped=>{stopped=true;break},Event::Line(_)|Event::Command(_)=>event=vm.advance(),other=>panic!("unexpected TV event: {other:?}")}}
  assert!(stopped);assert_eq!(vm.variables()[*flag],Value::Bool(true));
  assert!(matches!(vm.start("Firefighter_WannaCheck"),Event::Line(_)));
  let Event::Options(options)=vm.advance()else{panic!("missing inspection choices")};
  assert_eq!(options.iter().filter(|o|o.enabled).count(),index+1);
 }
}
