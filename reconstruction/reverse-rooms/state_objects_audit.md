# Recovered room state-object tables

The v11 original archive's static Unity assets establish the exact `Beer1` and `Beer2` state tables used by Daughter's first entrance route. `DialogCommandsInstance` exposes `[YarnCommand("ChangeState")]` with the signature `ChangeState(string stateableRaw, int stateIndex)`. The recovered wrapper calls the generic enum parser with case-insensitive matching, then forwards the resulting state-object type and index through its registered state-controller callback. The recovered enum is `EStateObjectType`; values `Beer1=13` and `Beer2=14` are declared in the retained C# source.

`StateObjectsViewProvider` on `level1` (MonoBehaviour path ID 3826) serializes 16 `StateObjet` entries. Each entry contains an enum integer and an ordered GameObject array. The exported table in [state_objects.json](state_objects.json) was decoded from that component's raw serialized bytes and resolved against `level1` GameObject path IDs. It records the array slots verbatim, including null references.

| State object | Enum | State 0 | State 1 |
|---|---:|---|---|
| Beer1 | 13 | null | Beer1 (GameObject path ID 539) |
| Beer2 | 14 | null | Beer2 (GameObject path ID 660) |

For both, the source tables have two slots. The recovered `StateObjet.SetActiveState(int)` iterates the array and activates a non-null slot only when its array index equals the requested state index. Null slots are skipped. Thus `ChangeState Beer1 1` and `ChangeState Beer2 1` activate the corresponding serialized GameObjects. These two calls can be modeled from recovered tables; this evidence alone does not resolve other commands in the Daughter route or initialize her visit.

The table also shows `Carpet` (0) has two serialized GameObjects and `Ground` (1) has four. The full export preserves all 16 registered table entries. It does not infer a default selected state: that is held in `StateObjectsSaveData` and loaded by `StateObjectController`. Delayed changes, save initialization, state-change callbacks, and campaign dispatch remain responsibilities of the controller integration.

## Reproduction

Run `tools/reverse-rooms/export_state_objects.py` with `UnityPy==1.25.4` against `level1` and `globalgamemanagers.assets`. The exporter validates that there is exactly one provider, checks serialized counts and bounds, rejects external references in the table, and requires the schema to consume the provider's complete raw payload. It reads static data only; no executable or library is loaded.

Evidence files in the v11 checkpoint:

- `reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/StateObjects/EStateObjectType.cs`
- `reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/StateObjects/StateObjet.cs`
- `reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/Infrastructure/StateObjects/StateObjectController.cs`
- `reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/Infrastructure/StateObjects/StateObjet.txt`, `SetActiveState`
- `reconstruction/logic/cpp2il_cs/DiffableCs/Assembly-CSharp/_Code/DialogSystem/Commands/DialogCommandsInstance.cs`, `ChangeState`
