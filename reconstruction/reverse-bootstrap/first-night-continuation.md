# First-night continuation evidence

This note records the first day-0 Neighbour entrance dialogue and the next verified in-house conversation route. It uses retained compiled Yarn JSON and recovered native ISIL; it does not execute the original EXE or DLL.

The scheduled preset visitor is Neighbour (enum value 3), day 0, guest 1. The entrance presentation callback calls `EntranceRoom.GetDialogName(character)` and passes the same visitor plus that returned name to `IDialogManager.RunDialog`. For this visitor, the generated node is `entrance_neighbour_0`.

That node offers `Neighbour_Entrance_1` and `_2`, plus the completed-game skip branch when the optional completion callback permits it. Both normal branches converge on `_3` or `_4`, then `_5`, `_6`, or `_7`; `_7` continues to `_8`. Nodes `_5`, `_6`, and `_8` end with the Yarn command `LetIn Neighbour`. The Yarn program proves where admission is requested. The retained command method body does not prove that its adapter dispatches to `ICharactersManager.LetIn`, so that call edge should remain behind an explicit native callback until verified.

After admission, an in-house conversation is grounded by the room selector. `ARoom.GetDialogName` asks `IDialogManager.GetCurrentDialogIndexForCharacter`, adds one, lowercases the character enum name, and constructs `talk_<type>_<index>`. `GetCurrentDialogIndexForCharacter` reads the per-character talk count from `DialogSaveData`. A new-game Neighbour with no prior room talks therefore selects `talk_neighbour_1` when the player starts that interaction. The `RunDialog` completion callback excludes node names containing `entrance`; normal talk completions call `AddTalk` and advance the saved count.

`talk_neighbour_1` checks whether `Neighbour_Asking_1` or `_2` has already been visited. If so, it runs `Neighbour_Asking_6`. Otherwise it shows its three opening lines, enables the fridge, and offers `Neighbour_Asking_1` or `_2`. It stops after the selected asking node. This establishes an optional first room conversation after admission; it does not establish a day-end transition or the full campaign path.

The final initial in-house roster remains unknown. `CharactersManagerSaveData` constructor initializes collection fields, but that constructor state alone does not prove the roster after fresh-save creation, `CharactersManager.OnSaveDataLoad`, and all initialization callbacks. The scheduled Neighbour visit likewise proves an event, not a pre-existing in-house roster.

Machine-readable evidence and file-level source references are in [first-night-continuation.json](first-night-continuation.json). The main startup and intro findings remain in [bootstrap_manifest.json](bootstrap_manifest.json).
