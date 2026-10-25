# Dialogue-to-game session

`DialogueSession` owns a Rust Yarn handle and connects command events to the typed C++ dispatcher and an optional synchronous scene-command handler. The gameplay decoder recognizes 12 kinds and 396 original command instructions; its other 3,647 instructions go to the scene handler or remain explicit host requests. `KillTomorrow` is supported but unused in this graph. Individual commands can still require typed production state/providers.

`SceneCommandRouter` binds presentation and story effects without interpreting text as shell commands. A handler returns true only after updating its supported state; false leaves the request pending without applying effects. Unknown commands, missing portrait data, player-sign data gaps and the original one-argument ChangePose anomaly are not silently discarded. Timers and other asynchronous effects require a host operation before acknowledgement. The 1,024 synchronous-command limit applies to both typed gameplay and scene effects.

The decoder implements the unquoted forms used by the retained graph. Quoted/multiline supported commands fail explicitly. Choices require current enabled options, original metadata and registered gameplay subscribers; selection callbacks run before VM resumption. A failed session cannot continue until explicitly restored/recovered.

## Snapshot boundary

`dump_snapshot()` creates `ninah-dialogue-session-snapshot` version 1 with a runtime snapshot, the visible event, started/host-ack state and a metadata fingerprint. The session envelope has an FNV-1a corruption checksum, not authentication. The runtime independently verifies the canonical program SHA-256. Restore checks event/instruction agreement, original metadata, option correspondence and the VM state before committing. It invokes no gameplay subscribers and replays no emitted command.

Inventory, occupants, presentation and story state are externally owned. The Android save transaction must capture those together with the session snapshot. Session-only restoration cannot roll back the rest of a game. Pending host commands keep blocking advance after restore. The current acknowledgement API compares exact text; it does not distinguish repeated asynchronous requests with the same text. The final host must serialize and cancel requests around restoration, or introduce opaque request tokens.

Regression tests traverse original Fatman item/portrait effects, Firefighter refusal and Alkonost energy choices. Snapshot tests preserve pending options and host commands and resume after Fatman's item grant without granting twice; the fixture explicitly restores inventory as part of that save. Malformed snapshots and graph mismatch leave the prior state intact. These tests do not claim complete campaign integration.

The JSON parser is MIT-licensed nlohmann/json v3.11.3, vendored with provenance. Original Windows code is never loaded by this layer. The current test app in `../android-current/` now consumes this session through JNI and touch controls. The full campaign, final presentation, audio and durable saves remain incomplete.
