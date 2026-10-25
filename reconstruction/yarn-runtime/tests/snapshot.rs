use serde_json::{json, Value};
use yarn_runtime::{Event, Runtime};

fn program(instructions: Value, labels: Value) -> Value {
    json!({"name":"snapshot-test","initial_values":{"score":1},"nodes":{"N":{"instructions":instructions,"labels":labels}}})
}

#[test]
fn pending_options_and_variables_survive_restore() {
    let p = program(json!([
        {"opcode":6,"operands":["Ada"]},
        {"opcode":4,"operands":["choice","picked",1.0,false]},
        {"opcode":5,"operands":[]},
        {"opcode":1,"operands":[]},
        {"opcode":13,"operands":["score"]},
        {"opcode":2,"operands":["picked-line",1.0]},
        {"opcode":15,"operands":[]}
    ]), json!({"picked":4}));
    let mut source = Runtime::new(p.clone()).unwrap();
    assert!(matches!(source.start("N"), Event::Options(ref options) if options.len() == 1));
    source.set_variable("score", json!(7));
    let snapshot = source.dump_snapshot().unwrap();

    let mut restored = Runtime::new(p).unwrap();
    restored.restore_snapshot(&snapshot).unwrap();
    assert_eq!(restored.variables()["score"], json!(7));
    assert_eq!(restored.select_option(0), Event::Line(yarn_runtime::Line {
        string_id: "picked-line".into(), substitutions: vec!["7".into()]
    }));
}

#[test]
fn graph_mismatch_and_bad_pc_are_rejected_without_mutation() {
    let original = program(json!([
        {"opcode":2,"operands":["one",0.0]},
        {"opcode":15,"operands":[]}
    ]), json!({}));
    let mut source = Runtime::new(original.clone()).unwrap();
    assert!(matches!(source.start("N"), Event::Line(_)));
    let snapshot = source.dump_snapshot().unwrap();

    let changed_graph = program(json!([
        {"opcode":2,"operands":["different",0.0]},
        {"opcode":15,"operands":[]}
    ]), json!({}));
    let mut target = Runtime::new(changed_graph).unwrap();
    let unchanged = target.dump_snapshot().unwrap();
    assert!(target.restore_snapshot(&snapshot).unwrap_err().contains("identity mismatch"));
    assert_eq!(target.dump_snapshot().unwrap(), unchanged);

    let mut valid_target = Runtime::new(original).unwrap();
    assert!(matches!(valid_target.start("N"), Event::Line(_)));
    let before = valid_target.dump_snapshot().unwrap();
    let mut invalid_pc = before.clone();
    invalid_pc["state"]["pc"] = json!(99);
    assert!(valid_target.restore_snapshot(&invalid_pc).unwrap_err().contains("outside node"));
    assert_eq!(valid_target.dump_snapshot().unwrap(), before);
}

#[test]
fn malformed_snapshot_types_are_rejected_atomically() {
    let p = program(json!([
        {"opcode":4,"operands":["choice","picked",0.0,false]},
        {"opcode":5,"operands":[]},
        {"opcode":1,"operands":[]},
        {"opcode":15,"operands":[]}
    ]), json!({"picked":3}));
    let mut runtime = Runtime::new(p).unwrap();
    assert!(matches!(runtime.start("N"), Event::Options(_)));
    let valid = runtime.dump_snapshot().unwrap();
    let before = valid.clone();

    let mut bad_variables = valid.clone();
    bad_variables["state"]["variables"] = json!([]);
    let mut bad_stack = valid.clone();
    bad_stack["state"]["stack"] = json!([{"not":"primitive"}]);
    let mut bad_option = valid.clone();
    bad_option["state"]["options"][0]["enabled"] = json!("yes");
    let mut bad_destination = valid;
    bad_destination["state"]["options"][0]["destination"] = json!("missing-label");

    for malformed in [bad_variables, bad_stack, bad_option, bad_destination] {
        assert!(runtime.restore_snapshot(&malformed).is_err());
        assert_eq!(runtime.dump_snapshot().unwrap(), before);
    }
}

#[test]
fn dump_refuses_state_that_cannot_be_restored_within_limits() {
    let p = program(json!([]), json!({}));
    let mut runtime = Runtime::new(p).unwrap();
    runtime.set_variable("large", json!("x".repeat(1024 * 1024 + 1)));
    assert!(runtime.dump_snapshot().unwrap_err().contains("limits"));
}
