use serde_json::{json, Value};
use yarn_runtime::{Event, Runtime};

fn program(instructions: Value, labels: Value, initial: Value) -> Value {
    json!({"name":"test","initial_values":initial,"nodes":{"N":{"name":"N","instructions":instructions,"labels":labels,"tags":[],"headers":[]}}})
}

#[test]
fn executes_true_and_false_branch_with_operands_and_real_line_id() {
    let p=program(json!([
        {"opcode":13,"operands":["$flag"]},
        {"opcode":10,"operands":["else"]},
        {"opcode":2,"operands":["real_yes",0.0]},
        {"opcode":15,"operands":[]},
        {"opcode":2,"operands":["real_no",0.0]},
        {"opcode":15,"operands":[]}
    ]),json!({"else":4}),json!({"$flag":true}));
    let mut r=Runtime::new(p).unwrap();
    assert_eq!(r.start("N"),Event::Line(yarn_runtime::Line{string_id:"real_yes".into(),substitutions:vec![]}));
    assert_eq!(r.advance(),Event::Stopped);
    r.set_variable("$flag",json!(false));
    assert_eq!(r.start("N"),Event::Line(yarn_runtime::Line{string_id:"real_no".into(),substitutions:vec![]}));
}

#[test]
fn presents_options_and_runs_selected_destination_label() {
    let p=program(json!([
        {"opcode":6,"operands":["Ada"]},
        {"opcode":4,"operands":["choice_line","picked",1.0,false]},
        {"opcode":5,"operands":[]},
        {"opcode":1,"operands":[]},
        {"opcode":2,"operands":["picked_line",0.0]},
        {"opcode":15,"operands":[]}
    ]),json!({"picked":4}),json!({}));
    let mut r=Runtime::new(p).unwrap();
    let Event::Options(options)=r.start("N") else {panic!("expected options")};
    assert_eq!(options[0].line.string_id,"choice_line");
    assert_eq!(r.select_option(0),Event::Line(yarn_runtime::Line{string_id:"picked_line".into(),substitutions:vec![]}));
}

#[test]
fn rejects_unknown_game_function_and_enforces_loop_budget() {
    let p=program(json!([{"opcode":7,"operands":[0.0]},{"opcode":12,"operands":["GetEnergy"]}]),json!({}),json!({}));
    let mut r=Runtime::new(p).unwrap();
    assert!(matches!(r.start("N"),Event::Error(s) if s.contains("no game hook")));
    let p=program(json!([{"opcode":0,"operands":["again"]}]),json!({"again":0}),json!({}));
    let mut r=Runtime::new(p).unwrap(); r.set_step_budget(5);
    assert!(matches!(r.start("N"),Event::Error(s) if s.contains("budget")));
}

#[test]
fn malformed_operands_and_underflow_are_reported() {
    let p=program(json!([{"opcode":11,"operands":[]}]),json!({}),json!({}));
    let mut r=Runtime::new(p).unwrap();
    assert!(matches!(r.start("N"),Event::Error(s) if s.contains("underflow")));
}

#[test]
fn visited_builtins_read_the_compilers_internal_counters() {
    let p=program(json!([
        {"opcode":6,"operands":["N"]},
        {"opcode":7,"operands":[1.0]},
        {"opcode":12,"operands":["visited_count"]},
        {"opcode":2,"operands":["count_line",1.0]},
        {"opcode":15,"operands":[]}
    ]),json!({}),json!({"$Yarn.Internal.Visiting.N":3.0}));
    let mut r=Runtime::new(p).unwrap();
    assert_eq!(r.start("N"),Event::Line(yarn_runtime::Line{string_id:"count_line".into(),substitutions:vec!["3".into()]}));

    let p=program(json!([
        {"opcode":6,"operands":["N"]},
        {"opcode":7,"operands":[1.0]},
        {"opcode":12,"operands":["visited"]},
        {"opcode":2,"operands":["visited_line",1.0]},
        {"opcode":15,"operands":[]}
    ]),json!({}),json!({"$Yarn.Internal.Visiting.N":0.0}));
    let mut r=Runtime::new(p).unwrap();
    assert_eq!(r.start("N"),Event::Line(yarn_runtime::Line{string_id:"visited_line".into(),substitutions:vec!["false".into()]}));
}

#[test]
fn recovered_game_graph_reaches_original_string_ids() {
    let p:Value=serde_json::from_str(include_str!("../../narrative/program.json")).unwrap();
    let mut r=Runtime::new(p).unwrap();
    assert!(matches!(r.start("Buddy_Asking_2_3"),Event::Line(l) if l.string_id.starts_with("line:")));
}

#[test]
fn recovered_firefighter_options_are_driven_by_original_variable_branches() {
    let p:Value=serde_json::from_str(include_str!("../../narrative/program.json")).unwrap();
    let mut r=Runtime::new(p).unwrap();
    assert!(matches!(r.start("Firefighter_WannaCheck"),Event::Line(_)));
    let Event::Options(opts)=r.advance() else {panic!("expected recovered options")};
    assert!(!opts.is_empty());
    assert!(opts.iter().any(|o|o.line.string_id.starts_with("line:Firefighter_WannaCheck_")));
    assert!(opts.iter().all(|o|!o.enabled));
    r.set_variable("$teethCheck",json!(true));
    assert!(matches!(r.start("Firefighter_WannaCheck"),Event::Line(_)));
    let Event::Options(enabled)=r.advance() else {panic!("expected options after line")};
    assert_eq!(enabled.iter().filter(|o|o.enabled).count(),1);
    let selected=enabled.iter().position(|o|o.enabled).unwrap();
    assert!(matches!(r.select_option(selected),Event::Line(_) | Event::Command(_)));
}

#[test]
fn recovered_node_increments_its_own_visit_counter_once() {
    let p:Value=serde_json::from_str(include_str!("../../narrative/program.json")).unwrap();
    let mut r=Runtime::new(p).unwrap();
    let mut event=r.start("tv_3_necessary");
    for _ in 0..100 {
        match event {
            Event::Stopped=>break,
            Event::Error(e)=>panic!("unexpected recovered node error: {e}"),
            _=>event=r.advance(),
        }
    }
    assert_eq!(r.variables()["$Yarn.Internal.Visiting.tv_3_necessary"],json!(1.0));
}
