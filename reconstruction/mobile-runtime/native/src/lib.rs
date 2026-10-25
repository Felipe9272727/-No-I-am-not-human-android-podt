use jni::objects::{JClass, JString};
use jni::sys::{jint, jstring};
use jni::JNIEnv;
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, HashMap};
use std::sync::{Mutex, OnceLock};
use yarn_runtime::{Event, Line, Runtime};

#[derive(Default)]
struct ViewerState {
    tables: BTreeMap<String, Vec<String>>,
    translations: HashMap<String, String>,
    program: Option<Value>,
    runtime: Option<Runtime>,
    event: Option<Event>,
}

static STATE: OnceLock<Mutex<ViewerState>> = OnceLock::new();
fn state() -> &'static Mutex<ViewerState> { STATE.get_or_init(|| Mutex::new(ViewerState::default())) }

fn parse_localization(source: &str) -> (BTreeMap<String, Vec<String>>, HashMap<String, String>) {
    let parsed = match serde_json::from_str::<Value>(source) {
        Ok(value) => value,
        Err(_) => return (BTreeMap::new(), HashMap::new()),
    };
    let Some(tables) = parsed.get("tables").and_then(Value::as_object) else {
        return (BTreeMap::new(), HashMap::new());
    };
    let mut catalog = BTreeMap::new();
    let mut translations = HashMap::new();
    for (name, entries) in tables {
        let mut texts = Vec::new();
        if let Some(entries) = entries.as_array() {
            for entry in entries {
                if let Some(text) = entry.get("text").and_then(Value::as_str) {
                    texts.push(text.to_owned());
                    if let Some(key) = entry.get("key").and_then(Value::as_str) {
                        // Unity exports the same stable key into more than one table; those
                        // repeated records carry identical localized text.
                        translations.insert(key.to_owned(), text.to_owned());
                    }
                }
            }
        }
        catalog.insert(name.clone(), texts);
    }
    (catalog, translations)
}

fn page(catalog: &BTreeMap<String, Vec<String>>, table: &str, offset: usize, limit: usize) -> Vec<String> {
    catalog.get(table)
        .map(|entries| entries.iter().skip(offset).take(limit.min(100)).cloned().collect())
        .unwrap_or_default()
}

fn localize_line(line: &Line, translations: &HashMap<String, String>) -> String {
    let mut text = translations.get(&line.string_id).cloned()
        .unwrap_or_else(|| "[Texto recuperado indisponível]".to_owned());
    for (index, value) in line.substitutions.iter().enumerate() {
        text = text.replace(&format!("{{{index}}}"), value);
    }
    text
}

fn event_json(event: Option<&Event>, translations: &HashMap<String, String>) -> Value {
    match event {
        Some(Event::Line(line)) => json!({"type":"line", "text":localize_line(line, translations)}),
        Some(Event::Options(options)) => json!({"type":"options", "options":options.iter().map(|option| json!({
            "text":localize_line(&option.line, translations), "enabled":option.enabled
        })).collect::<Vec<_>>()}),
        Some(Event::Command(command)) => json!({"type":"command", "text":command}),
        Some(Event::Stopped) => json!({"type":"stopped"}),
        Some(Event::Error(error)) => json!({"type":"error", "detail":error}),
        None => json!({"type":"stopped"}),
    }
}

fn read_java_string(env: &mut JNIEnv<'_>, value: JString<'_>) -> String {
    env.get_string(&value).map(|s| s.into()).unwrap_or_default()
}

fn java_string(env: &mut JNIEnv<'_>, value: Value) -> jstring {
    let serialized = serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_owned());
    env.new_string(serialized).map(|s| s.into_raw()).unwrap_or(std::ptr::null_mut())
}

#[no_mangle]
pub extern "system" fn Java_org_reconstruction_viewer_MainActivity_nativeLoadCatalog(
    mut env: JNIEnv<'_>, _class: JClass<'_>, source: JString<'_>,
) -> jstring {
    let (tables, translations) = parse_localization(&read_java_string(&mut env, source));
    let Ok(mut viewer) = state().lock() else { return java_string(&mut env, json!([])); };
    viewer.tables = tables;
    viewer.translations = translations;
    let names: Vec<String> = viewer.tables.keys().cloned().collect();
    java_string(&mut env, json!(names))
}

#[no_mangle]
pub extern "system" fn Java_org_reconstruction_viewer_MainActivity_nativeLoadProgram(
    mut env: JNIEnv<'_>, _class: JClass<'_>, source: JString<'_>,
) -> jstring {
    let parsed = serde_json::from_str::<Value>(&read_java_string(&mut env, source));
    let Ok(program) = parsed else { return java_string(&mut env, json!({"ok":false})); };
    if !program.get("nodes").and_then(Value::as_object).is_some() {
        return java_string(&mut env, json!({"ok":false}));
    }
    let count = program["nodes"].as_object().map(Map::len).unwrap_or(0);
    if let Ok(mut viewer) = state().lock() { viewer.program = Some(program); }
    java_string(&mut env, json!({"ok":true,"nodes":count}))
}

#[no_mangle]
pub extern "system" fn Java_org_reconstruction_viewer_MainActivity_nativeCatalogPage(
    mut env: JNIEnv<'_>, _class: JClass<'_>, table: JString<'_>, offset: jint, limit: jint,
) -> jstring {
    let table = read_java_string(&mut env, table);
    let page = state().lock().ok().map(|viewer| page(
        &viewer.tables, &table, offset.max(0) as usize, limit.max(0) as usize,
    )).unwrap_or_default();
    java_string(&mut env, json!(page))
}

#[no_mangle]
pub extern "system" fn Java_org_reconstruction_viewer_MainActivity_nativeStartNode(
    mut env: JNIEnv<'_>, _class: JClass<'_>, node: JString<'_>,
) -> jstring {
    let node = read_java_string(&mut env, node);
    let mut viewer = match state().lock() { Ok(value) => value, Err(_) => return java_string(&mut env, json!({"type":"error","detail":"state lock"})) };
    let Some(program) = viewer.program.clone() else {
        return java_string(&mut env, json!({"type":"error","detail":"program not loaded"}));
    };
    match Runtime::new(program) {
        Ok(mut runtime) => {
            let event = runtime.start(&node);
            viewer.runtime = Some(runtime);
            viewer.event = Some(event);
        }
        Err(error) => viewer.event = Some(Event::Error(error)),
    }
    let event = event_json(viewer.event.as_ref(), &viewer.translations);
    java_string(&mut env, event)
}

#[no_mangle]
pub extern "system" fn Java_org_reconstruction_viewer_MainActivity_nativeAdvance(
    mut env: JNIEnv<'_>, _class: JClass<'_>,
) -> jstring {
    let Ok(mut viewer) = state().lock() else { return java_string(&mut env, json!({"type":"stopped"})); };
    if let Some(runtime) = viewer.runtime.as_mut() { viewer.event = Some(runtime.advance()); }
    let event = event_json(viewer.event.as_ref(), &viewer.translations);
    java_string(&mut env, event)
}

#[no_mangle]
pub extern "system" fn Java_org_reconstruction_viewer_MainActivity_nativeSelectOption(
    mut env: JNIEnv<'_>, _class: JClass<'_>, index: jint,
) -> jstring {
    let Ok(mut viewer) = state().lock() else { return java_string(&mut env, json!({"type":"stopped"})); };
    if let Some(runtime) = viewer.runtime.as_mut() {
        viewer.event = Some(runtime.select_option(index.max(0) as usize));
    }
    let event = event_json(viewer.event.as_ref(), &viewer.translations);
    java_string(&mut env, event)
}

#[no_mangle]
pub extern "system" fn Java_org_reconstruction_viewer_MainActivity_nativeCurrentEvent(
    mut env: JNIEnv<'_>, _class: JClass<'_>,
) -> jstring {
    let event = state().lock().ok().map(|viewer| event_json(viewer.event.as_ref(), &viewer.translations)).unwrap_or_else(|| json!({"type":"stopped"}));
    java_string(&mut env, event)
}

#[cfg(test)]
mod tests {
    use super::{event_json, page, parse_localization};
    use std::collections::HashMap;
    use yarn_runtime::{Event, Runtime};

    const SOURCE: &str = r#"{"tables":{"UI":[{"id":1,"text":"Open","key":"label.open"},{"id":2,"text":"Close","key":"label.close"}],"Dialogs":[{"id":3,"text":"Visitante: Olá, {0}.","key":"line:greeting"}]}}"#;

    #[test]
    fn localized_table_preserves_source_order_and_stable_keys() {
        let (tables, translations) = parse_localization(SOURCE);
        assert_eq!(tables.keys().cloned().collect::<Vec<_>>(), vec!["Dialogs", "UI"]);
        assert_eq!(page(&tables, "UI", 1, 1), vec!["Close"]);
        assert_eq!(translations.get("line:greeting").unwrap(), "Visitante: Olá, {0}.");
        assert!(page(&tables, "missing", 0, 40).is_empty());
    }

    #[test]
    fn real_neighbor_day_two_scene_starts_with_a_localized_yarn_line() {
        let program = std::fs::read_to_string("../../narrative/program.json").unwrap();
        let locale = std::fs::read_to_string("../../assets/localization/portuguese_brazil_pt-br_.json").unwrap();
        let (_, translations) = parse_localization(&locale);
        let mut runtime = Runtime::from_json_str(&program).unwrap();
        let event = runtime.start("phone_neighbour_day2");
        let display = event_json(Some(&event), &translations);
        assert_eq!(display["type"], "line");
        assert!(!display["text"].as_str().unwrap().contains("line:phone_neighbour_day2"));
        assert!(!display["text"].as_str().unwrap().contains("Texto recuperado indisponível"));
    }

    #[test]
    fn real_neighbor_day_two_option_takes_a_recovered_graph_branch() {
        let program = std::fs::read_to_string("../../narrative/program.json").unwrap();
        let mut runtime = Runtime::from_json_str(&program).unwrap();
        let mut event = runtime.start("phone_neighbour_day2");
        for _ in 0..40 {
            match event {
                Event::Line(_) | Event::Command(_) => event = runtime.advance(),
                Event::Options(ref choices) => {
                    assert!(!choices.is_empty());
                    let branch = runtime.select_option(0);
                    assert!(!matches!(branch, Event::Error(_)), "recovered option branch returned {branch:?}");
                    return;
                }
                Event::Stopped => panic!("dialogue ended before a touchable option appeared"),
                Event::Error(ref error) => panic!("supported dialogue returned VM error: {error}"),
            }
        }
        panic!("no option appeared in the expected recovered dialogue span");
    }

    #[test]
    fn prototype_does_not_hide_commands_or_execute_them() {
        let event = Event::Command("ShowSign Neighbour".into());
        let display = event_json(Some(&event), &HashMap::new());
        assert_eq!(display["type"], "command");
        assert_eq!(display["text"], "ShowSign Neighbour");
    }
}
