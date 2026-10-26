# Static audit: progression after Neighbour on day 0

Scope: recovered C#/ISIL plus the compiled Yarn program in the v10 Rust checkpoint. This documents reachable source behavior; it does not claim the reconstructed Android host implements it. Original EXE/DLL were not executed or loaded. The checkpoint is recovered from a prior static extraction, and its DLL identity/hash was not independently revalidated in this audit.

## Finding

After the first Neighbour entrance and the first in-house conversation, there is no Yarn node that automatically advances to bedtime or day 1. The player remains in the house. The supported day-end trigger is the bedroom object's `Sleep()` interaction, which invokes `IDayNightController` interface member 10; the recovered controller's `Change()` is the day/night state transition. `Change()` does not accept every request: it checks `CanLeaveRooms`, then requires either the day action count to be at/below zero (when current `TimeOfDay` is day) or completion of all night ding-dong events (when current `TimeOfDay` is night). Thus a call to the bed during day 0 only consumes the day and enters night when the day action gate is met; a second eligible transition begins day 1 after night events are complete.

The schedule list for day 1 (Daughter, Esenin, Anxiety) is not evidence that these visitors have arrived, and does not establish an arrival order beyond preset data. `entrance_daughter_1` exists in the Yarn program, but the evidence here does not prove that it is the next node dispatched after this particular save state.

## Recovered call order and gates

1. Yarn completes `entrance_neighbour_0`, followed by the first in-house conversation node `talk_neighbour_1` when that room dialogue is selected. These nodes contain dialogue choices/runs and stop; neither invokes a sleep command or a day/night transition. `talk_neighbour_1` runs `SetFridgeActiveState true`, then has the two shortcut branches into `Neighbour_Asking_1` and `Neighbour_Asking_2`.
2. Bedroom interaction: `ObjectRoomObjectView.Sleep()` loads `IDayNightController` and calls interface slot 10. `DayNightController.Change()` is the recovered implementation. Exact interface-slot name is not in the ISIL call operand, but the controller has a single `Change()` method and its public interface declares it.
3. `Change()` first returns if `CanLeaveRooms` is false. For current day (`TimeOfDay == 0`), it checks the saved day-action value and only advances when `DayActions <= 0`. For current night (`TimeOfDay == 1`), it queries `IGameEventsManager` and only advances when the current day's ding-dong events are complete. It then invokes the sleep/bed transition path: vibration, the registered `WentToBed` callback if present, increments/wraps the time-of-day state, calls the dialog manager's `UpdateTalksCount`, starts the visual transition task, and stores `LastChange = Time.timeSinceLevelLoad + AccumulatedTime`.
4. On night-to-day, the method calls `InitNewDay(false)` as part of that transition. In recovered ISIL order, `InitNewDay(false)` resets the day action value, increments the day number, calls `CharactersManager.BeginNewDay(day)`, updates event/save flags and schedules, then invokes the recovered callbacks through manager interfaces (including game events, dialog manager, consumables and character-related dependencies). Callback invocation signatures appear as indirect method-pointer calls in this ISIL; do not infer side effects beyond separately recovered methods.
5. On day-to-night, the method calls `InitNewNight(false)`. It initializes window images and renews their dialogs first. Its non-restore branch changes night state and proceeds through game-event callbacks including the night ding-dong generation path. The ISIL has several indirect manager calls; callback names/order beyond calls that are directly identified are not safely recoverable from this method dump alone.
6. Night completion is a precondition for `Change()` to enter day. `GameEventsManager.GenerateDingDongEventsForDayAsync(day)` is an asynchronous event generator. The recovered source shows that its completion is represented by the manager's night-event state; the exact user-facing response after the last event and its handoff timing into `Change()` are not established here.

## Exact narrative nodes relevant to this slice

- `entrance_neighbour_0`: first entrance visit, options branch to `Neighbour_Entrance_1`, `Neighbour_Entrance_2`, or `Neighbour_Entrance_SkipIntro`; third option is conditional on `IsEverCompletedGame`. Node stops after selected subnode.
- `talk_neighbour_1`: the recovered first room talk. It checks the two `visited(...)` conditions for an additional asking line, sets the fridge active, and branches into `Neighbour_Asking_1` or `Neighbour_Asking_2`. No `talk_neighbour_2` node exists in the compiled program.
- `entrance_daughter_1`: present and starts with `SetEmotion Base`, three lines, then branches to `Daughter_Entrance_1_1` or `_1_2`. Presence is not proof of dispatch in a fresh day-1 save.
- Compiled program also contains day-specific Neighbour phone nodes (`phone_neighbour_day2` and later), which are not day-1 arrival nodes.

## Timing facts and limits

`Change()` records `LastChange` after starting its visual transition and uses Unity's `Time.timeSinceLevelLoad` plus `AccumulatedTime`. `InitNewDay` and `InitNewNight` receive the `isFromSaveData` flag; the ordinary transition uses `false`, while loading takes a distinct path. This is a call/timing relationship from recovered ISIL, not a measured wall-clock duration. The visual fade coroutine and async callbacks may complete later. No exact duration or real-time ordering between all callbacks can be supplied from these source artifacts.

## Evidence locations

All paths below are in the recovered checkpoint `restore-v10/checkpoint/reconstruction/`:

- `logic/recovered_isil/Assembly-CSharp/_Code/Rooms/ObjectRoomObjectView.txt`, method `Sleep()`; calls `IDayNightController` slot 10.
- `logic/recovered_isil/Assembly-CSharp/_Code/Infrastructure/DayNight/IDayNightController.txt`, `Change()` declaration.
- `logic/recovered_isil/Assembly-CSharp/_Code/Infrastructure/DayNight/DayNightController.txt`, methods `Change()`, `InitNewNight(bool)`, `InitNewDay(bool)`, and `add_WentToBed`.
- `logic/recovered_isil/Assembly-CSharp/_Code/Infrastructure/GameEvents/GameEventsManager.txt`, `GenerateDingDongEventsForDayAsync(int)`, night event state and `BeginNewDay()`.
- `logic/recovered_isil/Assembly-CSharp/_Code/Characters/CharactersManager.txt`, `BeginNewDay(int)`.
- `logic/recovered_isil/Assembly-CSharp/_Code/Rooms/EntranceRoom.txt`, entrance node selection and completion path.
- `narrative/program.json`, exact compiled node instructions for the three nodes above.
- Existing context: `reconstruction/native-game/README_campaign_slice.md` (describes the bounded v0.9 host and its known gap).

## Explicit unknowns before implementing the next advance

- Initial day-action count and the fresh-save room state after all startup callbacks; therefore whether sleeping immediately after the two Neighbour dialogues is eligible.
- The user's route through the Neighbour choices and any campaign flags those subnodes set that could affect later eligibility.
- Exact side effects and completion timing of every indirect callback in `InitNewDay` / `InitNewNight`, including what changes which residents are inside, and whether any events are queued before the first day-1 entrance.
- Exact dispatcher path selecting the next day-1 preset entrant, and whether it selects Daughter first under the state reached from this sequence.
- How the final night ding-dong completion triggers or enables bed interaction, including whether an additional input or transition is required.
- The mapping from opaque numeric manager interface slots in this ISIL to names where no direct method signature is available.
- Visual transition duration, async callback interleaving, and exact `WentToBed` subscribers for the active scene.
- Whether the checkpoint's recovered IL corresponds to the supplied v1.3.18 binary; no source DLL hash was rechecked.

Do not implement a generic “normal game loop” or automatically jump to `entrance_daughter_1` from the day-1 preset schedule. A faithful next step needs the outstanding eligibility and event-dispatch evidence above.

## Callback audit for the first morning (fresh-state slice)

This section narrows the state to day 0 with Neighbour as the only accepted guest, no imposters, no refusals/exiles, no coffee, and no queued next-day self-kill or exile. It does not simulate an arbitrary later campaign save.

### DayNightController.InitNewDay(false)

`InitNewDay(false)` executes synchronously during night-to-day `Change()`. The named interface calls at its tail resolve by interface declaration order, not by guessed semantics from slot numbers:

| Order | Call from `InitNewDay(false)` | Result in this slice |
| --- | --- | --- |
| Before reset/callback tail | `ICharactersManager.RunMorningOfSuicides()` (slot 24) | It iterates `CharactersManagerSaveData.SelfKillNextDayCharacters`, kills each listed character, then clears the list. Fresh state has no queued self-kill, so the loop emits no kill. |
| Callback after day action recompute | Opaque delegate stored on controller | May perform additional work; subscriber was not resolved from the extracted method body. Keep as an unresolved hook. |
| Tail #1 | `IGameEventsManager.BeginNewDay()` (slot 24) | Literal `GameEventsManager.BeginNewDay()` is a true no-op (`ret 0`; ISIL `Return`). It creates no arrival, TV, or ding-dong event. |
| Tail #2 | `ICharactersManager.BeginNewDay(day)` (slot 33) | Looks up `ExilesOnDays[day]`; calls `ExileCharacter` for matching entries; clears daily killed-character state. For day 1 with no scheduled exile, no exile is produced. |
| Tail #3 | `IDialogManager.RefreshSignChecks()` (slot 71) | If `HasCheckedSignsToday` is false, increments `DidntCheckSignsDays`; clears `HasCheckedSignsToday`; invokes the Prophet threshold hook only if the incremented value meets `ProphetDontCheckSignsDaysNeeded`. It is a counter update, not a no-op. The threshold value was not decoded from the available data. |
| Tail #4 | `IConsumablesController.BeginNewDay()` (slot 14) | Resets `PovistaskUsedCount` to zero. A fresh zero count remains zero; this method does not add coffee. |

The ordered controller method also resets the action counter, increments `Day`, clears a controller-owned per-day collection, and recomputes `MaxDayActions`. The collection’s semantic field name is not exposed in this ISIL. The `DayNightControllerData` record stores `[1,2,2,...]`; the getter indexes the array by the current day, and the no-coffee day-1 value is **2 actions**. The getter also adds active day-specific coffee bonuses, but those are absent in this slice. An internal first-week flag branch requires `GetImpostersCount() > 1`, `GetPossibleCharactersToKillCount() > 0`, `GetInnocentsCount() > 0`, plus an unset saved flag. With no imposters, that branch is ineligible regardless of the remaining counts.

`UpdateTalksCount()` is not a daily callback; `Change()` calls it on both day/night transitions. It delegates to `DialogSaveData.ApplyCharacterTalks()`, which copies each pending per-character talk into `CharactersTalksCountData.AddTalk(type)` and clears the transient list. Consequently the completed `talk_neighbour_1` is applied at the first eligible sleep transition; if no further dialogue is completed during night, the second `Change()` sees no new pending talk. Entrance-node completion is not a room talk count.

### Morning TV: explicit interaction and first node

TV dialogue is not launched by the no-op `GameEventsManager.BeginNewDay()`. `RoomsManager.WatchTV()` explicitly dispatches to `Bedroom.WatchMorningTV()` when the active room is Bedroom. Bedroom startup sets the TV active only when `CanWatchTV` allows it; the interaction path starts a TV dialog and later deactivates it. `Bedroom.StartTVDialog` forms the node name as `tv_{currentDay}_{kind}`: first `necessary`, then `extra1`, `extra2`, etc.; it records the chosen name through `IMetaPrefsDataHandler.WatchTV` and calls `IDialogManager.RunDialog`. Under a day-1, first-view state, the compiled program contains `tv_1_necessary`, which runs seven line instructions and then `Stop`. Its mere presence does not cause an automatic launch at dawn.

`DayNightController.WatchMorningTV()` is a separately recovered async hook. Its `MoveNext` constructs a predicate, awaits `UniTask.WaitUntil(predicate, 8, ...)`, then invokes a callback stored on the controller. The state-machine numeric states are `0` (create/await), `-1` (suspended), and `-2` (completed); the recovered predicate body itself is an indirect delegate and is not named in the dump. `RoomsManager.WatchTV -> Bedroom.WatchMorningTV -> Bedroom.StartTVDialog -> IDialogManager.RunDialog` is the explicit, source-supported start chain for a player-initiated TV view.

The compiled Yarn `tv_1_necessary` node contains seven `RunLine` operations and `Stop`, with no Yarn commands or event-generation call. It is the first necessary TV node for day index 1 only when bedroom's TV conditions permit viewing and the corresponding meta-save has not already recorded it. The detailed localized line text is not needed to establish progression and does not change that gate.

`GameEventsData` (`sharedassets0_2714_GameEventsData.bin`) contains only delays: first guest 6–8 seconds, subsequent guests 2–5 seconds. Those timing values do not create a day-1 arrival. `GenerateDingDongEventsForDayAsync(day)` is a distinct generator and is not the `BeginNewDay()` callback; the current evidence does not establish a day-1 guest arrival during the morning transition. The preset schedule and `entrance_daughter_1` remain insufficient to claim Daughter is automatically displayed at dawn.

### Implementable boundary and residual unknowns

A faithful pass-through may implement the state effects above without inventing successful events: apply pending talk counts at `Change`; run morning self-kill only for queued `SelfKillNextDayCharacters`; apply scheduled exiles only from `ExilesOnDays[day]`; increment/reset sign-check counters with threshold gated; reset consumable daily-use count; set day 1 and two actions in the no-coffee configuration; and leave `GameEventsManager.BeginNewDay` empty. TV should remain an explicit Bedroom/TV interaction with `tv_1_necessary` selected through the recovered node-name rule. These conclusions say which source branches do nothing for this stated state, while preserving actual bookkeeping and UI actions.

Still unresolved: the opaque `InitNewDay` delegate subscriber; the exact condition behind `WatchMorningTV`'s predicate; the numeric Prophet sign threshold; the full `CanWatchTV`/energy gate in user-visible terms; and the separate night-event generation/arrival dispatch after day 1. The decoded `GameEventsData` floats alone do not identify event names or cause an event to start.
