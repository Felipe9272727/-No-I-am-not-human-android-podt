use serde_json::Value;
use yarn_runtime::{Event, Runtime};

fn next_choices(runtime: &mut Runtime, mut event: Event) -> Vec<yarn_runtime::OptionItem> {
    for _ in 0..40 {
        match event {
            Event::Line(_) => event = runtime.advance(),
            Event::Options(options) => return options,
            other => panic!("Expected the original phone choices, got {other:?}"),
        }
    }
    panic!("Phone scene did not reach choices within its expected bounded dialogue");
}

#[test]
fn all_three_original_phone_questions_return_to_choices_and_fourth_choice_ends_call() {
    let program: Value = serde_json::from_str(include_str!("../../narrative/program.json")).unwrap();
    let first_answer_ids = [
        "line:phone_neighbour_day2_1_043d908",
        "line:phone_neighbour_day2_2_05b919e",
        "line:phone_neighbour_day2_3_0f9fc69",
    ];
    for (index, expected) in first_answer_ids.iter().enumerate() {
        let mut runtime = Runtime::new(program.clone()).unwrap();
        let start = runtime.start("phone_neighbour_day2");
        let choices = next_choices(&mut runtime, start);
        assert_eq!(choices.len(), 4);
        assert!(choices.iter().all(|choice| choice.enabled));
        let first_answer = runtime.select_option(index);
        assert!(matches!(&first_answer, Event::Line(line) if line.string_id == *expected));
        assert_eq!(next_choices(&mut runtime, first_answer).len(), 4);
        let goodbye = runtime.select_option(3);
        assert!(matches!(goodbye, Event::Line(line) if line.string_id == "line:phone_neighbour_day2_4_041f95f"));
        assert_eq!(runtime.advance(), Event::Stopped);
    }
}
