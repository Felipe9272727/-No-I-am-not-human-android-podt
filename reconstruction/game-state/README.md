# Reconstructed game-state rules

This crate contains a small standalone Rust model of selected rules confirmed in the Windows IL2CPP binary. It is a reconstruction component, not a full port. It ships with no character records, max-energy configuration, inventory rules, event schedule, or progression defaults; callers provide recovered data and services.

## Evidence map

The offsets below are **method RVAs in Cpp2IL's recovered `Assembly-CSharp.dll` IL-recovery assembly**. They are not RVAs into the supplied `GameAssembly.dll`. Recovered IL bodies are preserved in [`../logic/selected_method_bodies.il`](../logic/selected_method_bodies.il); corresponding native x86-64 instruction listings from `GameAssembly.dll` are in [`../logic/selected_native_disassembly.txt`](../logic/selected_native_disassembly.txt). The retained native listings do not preserve a reliable method-entry address map, so no native RVA is claimed here. Source binary hash and recovery caveats are in [`../logic/logic_recovery.md`](../logic/logic_recovery.md).

| Crate behavior | Method | Recovered-IL RVA | Recovered rule |
|---|---|---:|---|
| `EnergyState::act` | `DayNightController.Act` | `0x76208` | Decrement `DayActions` by one, without a local zero guard. |
| `EnergyState::act_all` | `DayNightController.ActAll` | `0x76258` | Set `DayActions` to zero. |
| `EnergyState::add_energy` | `DayNightController.AddEnergy` | `0x74D10` | Increment by one only if current actions are below `get_MaxDayActions`. |
| `EnergyState::refill_energy` | `DayNightController.RefillEnergy` | `0x74DA4` | Assign `get_MaxDayActions` to `DayActions`. This crate takes that maximum explicitly. |
| `EnergyState::add_fine_for_tomorrow` | `DayNightController.RemoveExtraEnergySlotsForTomorrow` | `0x74DEC` | Add the count to the `Day + 1` dictionary entry, creating it if absent. |
| `EnergyState::configured_max_day_actions` | `DayNightController.get_MaxDayActions` | `0x74158` | Read configured array at current day index, subtract that day's fine if present, then add extra slots. Day index must be inside the recovered array. |
| `CharacterSnapshot::is_imposter` | `DialogCommandsInstance.IsImposter` | `0xBC7B4` | Match character data by enum spelling; absent match yields false. |
| `CharacterSnapshot::innocents_count` | `DialogCommandsInstance.GetInnocentsCount` | `0xBCB94` | Count current occupants for which manager `IsImposter` is false. |
| `CharacterSnapshot::is_place_empty` | `DialogCommandsInstance.IsCharacterPlaceEmpty` | `0xBCFDC` | Resolve target's place and test whether any current occupant is at that place. |
| `call_service` | `DialogCommandsInstance.GetEnergy` / `IsAlive` / `TryGiveItemFor` | `0xBD334` / `0xBD5E8` / `0xBC8B4` | These commands depend on injected services. This Rust helper reports missing dependencies explicitly rather than manufacturing gameplay state. |

`get_MaxDayActions` uses the fully parsed day/night config at `../assets/gameplay_data/production_configs.json`. For day `d`, it computes `max_day_actions_by_days[d] - EnergyFinesByDays[d] + ExtraEnergySlots`, treating an absent fine as zero. The native body uses 32-bit `sub` and `add`, so the Rust adapter uses wrapping `i32` arithmetic. The Cpp2IL IL RVA is `0x74158`; the corresponding native entry is `GameAssembly.dll` RVA `0x64A4B0` (VA `0x18064A4B0`, verified as the direct call target in `AddEnergy` and `RefillEnergy`). An out-of-range day returns an error rather than a fabricated maximum. The recovered array has 19 entries; its serialized `last_day` value is 14, and the accessor itself indexes the array directly.

`GetEnergy`'s native wrapper itself returns `0` when its delegate is absent; this crate's `call_service` is a stricter integration boundary chosen so a host cannot mistake an unavailable service for actual game state. `IsAlive` and item assignment also depend on manager/callback behavior, so no local life or inventory rule is supplied.

The unit-test character names and places are synthetic fixtures confined to tests. They are not game defaults. Run `cargo test` from this directory.
