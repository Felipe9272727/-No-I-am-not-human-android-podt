# Recovered Yarn command dispatcher

This is a small typed dispatch layer for command callbacks whose core gameplay
effects already have native recovery: `GetItem`, `Refuse`, `KillTomorrow`,
`ExileAfterTomorrow`, `LetIn`, `AggressiveLetIn`, `Kill`, `ExileCharacter`,
`OrderCourier`, `UpdateDeficitDay`, `ExileByFEMA`, and `KillRoom`. It does not
claim to implement all Yarn commands or the full campaign.

The dispatcher takes structured values (`Consumable`, integer character IDs,
and integer counts). `decode_gameplay_command` handles the exact unquoted
literal forms recovered from the Yarn program; it rejects quotes and
multiline text and resolves character names through the supplied catalog.
Interpolation remains the VM bridge's responsibility. Unsupported command
names become `UnsupportedDialogueCommand`; dispatch rejects them before
changing state.
`dispatch_all` preflights the entire batch for unsupported commands before
running any callback.

The recovered bindings and C# signatures are recorded in
`../logic/yarn_api_map.md` and
`../logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/DialogSystem/Commands/DialogCommandsInstance.cs`.
The original wrapper bodies are in
`../logic/recovered_isil/Assembly-CSharp/_Code/DialogSystem/Commands/DialogCommandsInstance.txt`,
and the supporting manager bodies are in
`../logic/recovered_isil/Assembly-CSharp/_Code/Characters/CharactersManager.txt`.
The compact wrapper bodies are also in `../logic/selected_method_bodies.il`, and command
invocations such as `GetItem {0} 1` and `Refuse Fairytaller` are present in
`../narrative/program.json`.
The wrappers show `LetIn` passes `false` and `AggressiveLetIn` passes `true` for
the manager's `exileOldCharacterFromThisPlace` flag. `Kill` calls the manager
with `isByPlayer=true`; `ExileCharacter` carries its optional `showInDialog`
flag, whose callback runs after the manager exile operation. The dispatcher
preserves those flags. `OrderCourier` calls the existing
`CourierService::order_courier`, and `UpdateDeficitDay` forwards to its
existing deficit service. These commands require a `CourierService` adapter.
`ExileByFEMA` invokes its optional multicast callback and safely does nothing
when there are no subscribers. `KillRoom` requires a separate room-manager
callback and never aliases `OccupantsRuntime::kill`. The exact native state
mutations are implemented in the inventory and occupants modules:
`Inventory::add`, `OccupantsRuntime::refuse`,
`kill_tomorrow`, `exile_after_tomorrow`, `let_in`, `kill`, and `exile`.
`ExileAfterTomorrow` schedules the character for current day + 2. `LetIn`
requires a caller-supplied provider for recovered serialized FEMA/status inputs;
the dispatcher does not invent those values. A missing provider or requested
dialog callback fails before mutation. The dispatcher also preflights batches
for unsupported commands and missing required services before running them.

The original retained enum declarations are in
`../logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/Consumables/EConsumable.cs`
and `../logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Characters/ECharacterType.cs`.
The dispatcher does not duplicate enum or character string parsing. The typed
bridge must reject invalid input before constructing a command.
`RefuseOldLetInNew` is also omitted because it is a multi-step command with
behavior beyond these recovered operations. No effects are inferred for
animation, emotion, presentation, or other unrecovered commands.

The regression test checks callback order and state changes across supported
commands, wrapper flags for aggressive admission/player kills/dialog exile,
batch rejection before mutation when an unsupported command appears, and
rejection of missing command services or character IDs before state changes,
the distinct `KillRoom` callback, and optional `ExileByFEMA` behavior.
