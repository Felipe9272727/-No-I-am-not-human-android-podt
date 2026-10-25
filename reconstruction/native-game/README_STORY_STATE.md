# Story-state adapter

`native-game/include/ninah/story_state.hpp` and `src/story_state.cpp` provide a
small native boundary for recovered story-command effects. The adapter owns no
campaign state: `StoryStateRefs` holds caller-owned, non-owning pointers to
handler state, while query and achievement behavior enters through callbacks.

The five state methods model the effects after the Yarn event has reached its
gameplay handler. The `DialogCommandsInstance` methods themselves are optional
delegate dispatchers: a missing delegate is a no-op. A missing required nested
save/ending-state reference in the receiving handler raises
`NullReferenceError`. The refs correspond to `GameplayEndingManagerSaveData`
`HasBegunCultists` and `SavedCultists`, `GameplayEndingDeath._isReadyToEnd`,
`GameplayEndingMushroom._cartoonUnlocked`, `GameplayEndingVigilante._isRevealed`,
and `DialogSaveData.EverRudeToFema`.

`on_were_bad_boy` accepts the current character type from the dialog layer,
throws when that character is absent, and sets `ever_rude_to_fema` only for
character type 14. It does not interpret a Yarn option ID. Missing
mushroom-condition, seen-dream, and ever-completed query callbacks return
`false`. The dream query accepts an already parsed source enum value; raw Yarn parsing remains in `DialogueServices`. `get_achievement` calls the required achievement callback with the raw
ID and explicit `false` unlock parameter; it throws if the callback is
unavailable. The zero-arg `ending()` command invokes registered subscribers
synchronously in registration order.

The boundary is deliberately not a campaign-manager integration. Callers must
wire the bool refs, query callbacks, achievement adapter, and Ending event
subscribers to their own state/service implementation.

Evidence for Yarn command dispatch and query adapters is in recovered ISIL at
`reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/DialogSystem/Commands/DialogCommandsInstance.txt`.
The state-writing handlers are `GameplayEndingManager.OnCultistsBegun`,
`OnCultistsSaved`, `OnUnlockedDeathEnding`, `OnUnlockedMushroomEnding`, and
`OnPlayerRevealedByVigilante` in
`reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/Infrastructure/Endings/Gameplay/GameplayEndingManager.txt`;
`GameplayEndingCultists.BeginCultists` and `SaveCultists` write the cultist
save-data fields in
`reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/Infrastructure/Endings/Gameplay/GameplayEndingCultists.txt`.
`DialogManager.OnWereBadBoy` and its backing field name are evidenced in
`reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/DialogSystem/DialogManager.txt`
and `reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/DialogSystem/DialogSaveData.txt`.
The provided targeted test can be built with:

```sh
g++ -std=c++17 -Wall -Wextra -Werror -pedantic \
  -Ireconstruction/native-game/include \
  reconstruction/native-game/src/story_state.cpp \
  reconstruction/native-game/tests/story_state_tests.cpp \
  -o /tmp/story_state_tests
/tmp/story_state_tests
```
