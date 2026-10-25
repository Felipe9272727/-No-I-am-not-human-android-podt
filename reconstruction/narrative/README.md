# Recovered Yarn program

`program.json` is a static protobuf decode of the `YarnProject.compiledYarnProgram` byte array in MonoBehaviour path ID 2735. The decoder reads the Unity MonoBehaviour framing (GameObject pointer, enabled flag, MonoScript pointer, aligned name and byte-array length), then parses protobuf wire values directly. It does not load or execute game code.

The decoded payload is 2,207,477 bytes at offset 52 of the 2,207,564-byte Unity object. The remaining 35 bytes belong to subsequent serialized `YarnProject` fields. SHA-256 of the protobuf payload: `33de1e80e55e4eb8ec2093078028aa83fc45ac8b77acc05c5a4f9477ebe92827`.

The stable JSON shape is `{name, nodes, initial_values}`. Nodes contain `name`, `instructions`, `labels`, `tags`, `source_text_string_id`, and `{key,value}` headers. Instructions have numeric `opcode`, `opcode_name`, and primitive operand arrays; omitted protobuf opcode field values correctly decode to enum default `0` (`JumpTo`). Initial value oneofs decode to primitive strings, booleans, and numbers. Schema field numbers and opcode/function/command counts are in `program_decode_report.json`.

Validation: 3,255 nodes, 56,585 instructions, 276 initial values, no unknown protobuf fields, no unknown opcode values. A structural comparison against the parallel Cpp2IL-derived protobuf dump had zero node/instruction mismatches when normalizing omitted opcode to default 0, and zero initial-value mismatches.

Run `python tools/narrative/decode_yarn.py` from the workspace to regenerate the JSON and report. Line identifiers remain symbolic in the bytecode. The SharedTableData mapping was subsequently recovered from `localization-assets-shared_assets_all.bundle`: locale JSON records now preserve the string `key` as well as the numeric Unity entry ID and translated text. Join the bytecode line identifier to that `key`, never to the numeric ID.

Integration validation found all 15,693 distinct dialogue and option line identifiers in both the English and Brazilian Portuguese exports, with zero missing translations and no conflicting text among repeated dialogue keys. Run `python tools/validate_reconstruction.py` for the structural and localization checks.
