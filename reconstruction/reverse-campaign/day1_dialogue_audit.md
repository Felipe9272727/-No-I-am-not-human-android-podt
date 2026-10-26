# Day-1 dialogue static audit

Static analysis of the recovered compiled Yarn program and current host dispatch. No original game binary or library was executed.

## Findings

The preset schedule lists Daughter (guest 1), Esenin (guest 2), and Anxiety (guest 3). This establishes schedule configuration only; it does not establish actual day-start arrivals or their event order.

The recovered entrance room resolves the first Daughter visit to `entrance_daughter_1` in the checkpoint notes. Its Yarn node has two authored options and branches into Daughter entrance subnodes. The native disassembly does not expose managed field names for the visit index/visited bit, so this audit preserves that mapping as checkpoint-reported rather than claiming a field-level reconstruction.

No node named `morningTV` or `morning_tv` exists. `tv_1_necessary` is present as the TV dialogue candidate, but its presence does not prove event generation or the morning sequence.

## Routes and reachable nodes

### `tv_1_necessary`

Present: **True**. Static RunNode closure: `tv_1_necessary`.

### `entrance_daughter_1`

Present: **True**. Static RunNode closure: `Daughter_Entrance_1_1`, `Daughter_Entrance_1_2`, `Daughter_Entrance_1_3`, `Daughter_Entrance_1_4`, `Daughter_Entrance_1_5`, `entrance_daughter_1`.

### `Esenin_Entrance_11`

Present: **True**. Static RunNode closure: `Esenin_Entrance_11`, `Esenin_Entrance_3`, `Esenin_Entrance_4`, `Esenin_Entrance_NoLet`, `Esenin_Entrance_Occupied`, `Esenin_Entrance_Occupied_NoLet`, `Esenin_Entrance_Occupied_YesLet`, `Esenin_Entrance_YesLet`.

### `Anxiety_Entrance_11`

Present: **True**. Static RunNode closure: `Anxiety_Entrance_11`, `Anxiety_Entrance_3`, `Anxiety_Entrance_4`, `Anxiety_Entrance_NoLet`, `Anxiety_Entrance_Occupied`, `Anxiety_Entrance_Occupied_NoLet`, `Anxiety_Entrance_Occupied_YesLet`, `Anxiety_Entrance_YesLet`.

## Command/function inventory

Each node includes exact extracted RunCommand text and CallFunc names in the adjacent JSON inventory. Host status reflects the current typed dialogue and scene dispatchers; a recognized command may still require runtime providers or presentation assets.

- `Anxiety_Entrance_11` — commands: `SetEmotion Base` (supported); functions: none.
- `Anxiety_Entrance_3` — commands: `SetEmotion Base` (supported); `SetEmotion Sad` (supported); functions: `IsCharacterPlaceEmpty`.
- `Anxiety_Entrance_4` — commands: `SetEmotion Base` (supported); `SetEmotion Sad` (supported); functions: `IsCharacterPlaceEmpty`.
- `Anxiety_Entrance_NoLet` — commands: `SetEmotion Base` (supported); `SetEmotion Sad` (supported); `Refuse Anxiety` (supported); functions: none.
- `Anxiety_Entrance_Occupied` — commands: none; functions: `GetCharacterOnPlace`.
- `Anxiety_Entrance_Occupied_NoLet` — commands: `Refuse Anxiety` (supported); functions: none.
- `Anxiety_Entrance_Occupied_YesLet` — commands: `AggressiveLetIn Anxiety` (supported); functions: none.
- `Anxiety_Entrance_YesLet` — commands: `SetEmotion Happy` (supported); `LetIn Anxiety` (supported); functions: none.
- `Daughter_Entrance_1_1` — commands: `SetEmotion Happy` (supported); functions: none.
- `Daughter_Entrance_1_2` — commands: `SetEmotion Happy` (supported); `SetEmotion Base` (supported); functions: none.
- `Daughter_Entrance_1_3` — commands: `SetEmotion Base` (supported); functions: none.
- `Daughter_Entrance_1_4` — commands: `SetEmotion Base` (supported); functions: none.
- `Daughter_Entrance_1_5` — commands: `SetEmotion Happy` (supported); `SetEmotion Base` (supported); `SetEmotion Happy` (supported); `ExileCharacter Neighbour true` (supported); `ChangeState Beer1 1` (unsupported_or_unmapped); `ChangeState Beer2 1` (unsupported_or_unmapped); functions: none.
- `Esenin_Entrance_3` — commands: none; functions: `IsCharacterPlaceEmpty`.
- `Esenin_Entrance_4` — commands: none; functions: `IsCharacterPlaceEmpty`.
- `Esenin_Entrance_NoLet` — commands: `Refuse Esenin` (supported); functions: none.
- `Esenin_Entrance_Occupied` — commands: none; functions: `GetCharacterOnPlace`.
- `Esenin_Entrance_Occupied_NoLet` — commands: `Refuse Esenin` (supported); functions: none.
- `Esenin_Entrance_Occupied_YesLet` — commands: `AggressiveLetIn Esenin` (supported); functions: none.
- `Esenin_Entrance_YesLet` — commands: `SetEmotion Happy` (supported); `LetIn Esenin` (supported); functions: none.
- `entrance_daughter_1` — commands: `SetEmotion Base` (supported); functions: none.

## Integration boundary

A deterministic next slice may invoke recovered nodes directly after the existing host reaches a supported state. `IsCharacterPlaceEmpty` and `GetCharacterOnPlace` are in the current game-function adapter. `LetIn`, `AggressiveLetIn`, `Refuse`, and `ExileCharacter` have command models, but LetIn needs production inputs, ExileCharacter may need its dialog callback, and commands such as `ChangeState Beer1 1` are unsupported by the current generic dispatcher. The night-to-day transition, initialization callbacks, day-1 event generation, and actual arrival ordering remain blockers; do not claim the preset entries prove those stages.

Machine-readable node-by-node route and dispatcher inventory: [`day1_dialogue_audit.json`](day1_dialogue_audit.json).
