# Recovered story-state service boundary

The native adapter in `native-game/include/ninah/story_state.hpp` mirrors the
observable `DialogCommandsInstance` story-state command boundary. It does not
claim to reconstruct the backing campaign manager or save model.

| Yarn command / handler | Native behavior | Recovered evidence |
| --- | --- | --- |
| `BeginCultists` → `GameplayEndingManager.OnCultistsBegun` | The event handler sets `GameplayEndingManagerSaveData.HasBegunCultists`; a missing required nested save-data ref null-throws | The command's optional dispatch is in `DialogCommandsInstance.BeginCultists`; the handler is in `GameplayEndingManager.OnCultistsBegun`. `GameplayEndingCultists.BeginCultists` also writes this field in a separate path. |
| `SaveCultists` → `GameplayEndingManager.OnCultistsSaved` | Sets `GameplayEndingManagerSaveData.SavedCultists`; a missing required nested save-data ref null-throws | The command's optional dispatch is in `DialogCommandsInstance.SaveCultists`; the handler is in `GameplayEndingManager.OnCultistsSaved`. `GameplayEndingCultists.SaveCultists` also writes this field in a separate path. |
| `UnlockDeathEnding` → `GameplayEndingManager.OnUnlockedDeathEnding` | Sets `GameplayEndingDeath._isReadyToEnd`; missing required ending object null-throws | `DialogCommandsInstance.UnlockDeathEnding` dispatches; `GameplayEndingManager.OnUnlockedDeathEnding` handles the event |
| `UnlockMushroomEnding` → `GameplayEndingManager.OnUnlockedMushroomEnding` | Sets `GameplayEndingMushroom._cartoonUnlocked`; missing required ending object null-throws | `DialogCommandsInstance.UnlockMushroomEnding` dispatches; `GameplayEndingManager.OnUnlockedMushroomEnding` handles the event |
| `VigilanteRevealsPlayer` → `GameplayEndingManager.OnPlayerRevealedByVigilante` | Sets `GameplayEndingVigilante._isRevealed`; missing required ending object null-throws | `DialogCommandsInstance.VigilanteRevealsPlayer` dispatches; `GameplayEndingManager.OnPlayerRevealedByVigilante` handles the event |
| `OnWereBadBoy` | Missing current character throws; type 14 sets `DialogSaveData.EverRudeToFema`; other types do nothing | `DialogManager.OnWereBadBoy` |
| `HasCompletedMushroomCondition` | Optional query, defaults false | `DialogCommandsInstance.HasCompletedMushroomCondition` |
| `HasSeenDream(raw)` | Optional raw-ID query, defaults false | `DialogCommandsInstance.HasSeenDream` |
| `IsEverCompletedGame` | Optional query, defaults false | `DialogCommandsInstance.IsEverCompletedGame` |
| `GetAchievement(raw)` | Invoke required achievement hook with explicit `false` second argument | `DialogCommandsInstance.GetAchievement` calls `SteamAchievements.Unlock(raw, false)` |
| `Ending` | Invoke Ending subscribers synchronously, in registration order | `DialogCommandsInstance.Ending` dispatches the `EndingTriggered` event |

The `DialogCommandsInstance` methods are event dispatchers. If their optional
delegate is absent, the wrapper returns without changing state. The native
`StoryState` methods represent the receiving gameplay handler effects; its
required bool refs correspond to the handler's nested save/ending-state
references, whose null paths reach `NullReferenceException`. The adapter
represents that with `NullReferenceError`. Missing query delegates have
false-return paths. The achievement adapter is required because the command
directly calls `SteamAchievements.Unlock`.

Evidence files:

- `reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/DialogSystem/Commands/DialogCommandsInstance.txt`
- `reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/DialogSystem/DialogManager.txt`
- `reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/Infrastructure/Endings/Gameplay/GameplayEndingManager.txt`
- `reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/Infrastructure/Endings/Gameplay/GameplayEndingCultists.txt`
- `reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/Infrastructure/Endings/Gameplay/GameplayEndingManagerSaveData.txt`
- `reconstruction/logic/recovered_isil/Assembly-CSharp/_Code/DialogSystem/DialogSaveData.txt`

This adapter leaves concrete campaign persistence, Steam API wiring, dream ID
parsing, and game-manager integration to the host application.
