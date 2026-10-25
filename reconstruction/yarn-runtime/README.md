# Recovered Yarn bytecode runtime

This crate runs the decoded program at `reconstruction/narrative/program.json` using the primitive-operand JSON projection. It is a VM for the recovered Yarn instructions, not a reconstruction of the Unity game systems.

```rust
use yarn_runtime::{Event, Runtime};
let mut vm = Runtime::from_json_str(include_str!("../../narrative/program.json"))?;
let event = vm.start("Firefighter_WannaCheck");
```

`Line` events contain a recovered string ID and substitutions. The companion assets integration resolves the IDs to localized text; this crate intentionally keeps localization outside the VM. `Options` events expose enabled state and destination labels; pass the selected index to `select_option`. `Command` events are surfaced as text and never executed. `advance` resumes after a line/command. Runtime errors, including unknown external Yarn functions, are reported as `Event::Error`.

Implemented opcodes are the game's recovered 0–16 set, including label jumps, branches, variables, options, and node transfers. Built-in numeric operations and boolean `And`/`Or`/`Not` are supported, along with Yarn's `visited` and `visited_count` functions backed by `$Yarn.Internal.Visiting.<node>` values. Visit counters are incremented by explicit compiler-emitted bytecode; the runtime does not add a second entry/exit increment. Game-registered functions such as `GetEnergy`, `GetItemCount`, `IsImposter`, and inventory/character queries need real game-state hooks and currently stop with an explicit error. There is no Unity presentation layer, save persistence, or command/gameplay handler here.

Semantics were checked against the official Yarn Spinner v2.4.2 `VirtualMachine.cs` implementation: https://github.com/YarnSpinnerTool/YarnSpinner/blob/v2.4.2/YarnSpinner/VirtualMachine.cs

The VM exposes a version 1 snapshot for host-managed saves. Its JSON shape is
`{"format":"ninah-yarn-vm-snapshot","version":1,"program_sha256":"…","state":{"variables":{},"node":"…","pc":0,"stack":[],"options":[],"halted":true}}`.
The SHA-256 identifies the canonical serialized decoded program. Restore rejects a different
program, malformed fields, invalid stack/options, or a program-counter/label mismatch before
changing VM state. The snapshot includes pending choices and execution state but excludes host
function callbacks and line metadata. Restoring never re-emits a line or command; the next event
is produced only by an explicit `advance` or `select_option` call. The C ABI exports
`ninah_yarn_dump_snapshot(handle, error)` and `ninah_yarn_restore_snapshot(handle, snapshot, error)`;
both returned strings and error strings use `ninah_yarn_free_string` ownership. Snapshot input and
output are capped at 32 MiB, with per-collection, primitive-type, and string-size checks during
restore.
