# Campaign slice after the first Neighbour conversation

The native host now keeps the first verified visit and the first in-house
conversation inside the playable house state. Ending `entrance_neighbour_0`
completes the day-0 preset visit and returns to exploration. The reached
Neighbour routes all call LetIn; no refusal choice is invented. Completing `talk_neighbour_1` returns to exploration,
records one Neighbour room talk, and prevents replaying it as though an
unverified `talk_neighbour_2` existed. The recovered Yarn program contains
`talk_neighbour_1` but no `talk_neighbour_2` node.

The campaign snapshot exposes `night_events_complete`, the Neighbour talk
count, and `next_day_preset_visits`. The last field is schedule data, not an
arrival event. It comes from the extracted preset records in
`generated/production_characters.hpp`; for day 1 the records identify Daughter
as guest 1, Esenin as guest 2, and Anxiety as guest 3. The host does not advance
the clock or stage those visitors yet.

The static evidence chain consulted in the v0.8 checkpoint is:

- `EntranceRoom.ShowFullSizeCharacter` captures the event condition and its
  dialog-ended callback calls the game-events manager to complete that event.
- `DialogManager.RunDialog` calls `AddTalk` for completed room dialogue, while
  its entrance-node check excludes `entrance_*` nodes. `ARoom.GetDialogName`
  derives the next `talk_<character>_<index>` from the saved talk count.
- `DayNightController.Change` permits a Night-to-Day transition only when the
  current night's ding-dongs are complete. The following `InitNewDay` performs
  additional manager callbacks before the day is ready.
- `EntranceRoom.GetDialogName` resolves the first Daughter visit to
  `entrance_daughter_1`; that Yarn node and the day-1 preset slots are present
  in the recovered compiled program and character configuration.

The full next-day transition remains out of scope because `InitNewDay` invokes
`CharactersManager.BeginNewDay`, dialog-sign refresh, consumables, and event
generation. Those callbacks are not integrated into this host. The fresh-save
inside roster after all startup callbacks also remains unverified. No day-1
arrival is inferred from the schedule snapshot, and no original executable or
library was run.

`preset_schedule_tests.cpp` verifies day-0 and day-1 preset slots against the
generated character catalog. The Android native host regression covers ending
the Neighbour visit, completing the first room talk, resuming exploration,
retaining talk/event state through the in-memory save, and rejecting the
unavailable repeat dialogue.
