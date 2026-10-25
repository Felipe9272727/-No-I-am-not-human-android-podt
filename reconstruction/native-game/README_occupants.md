# Recovered occupant transitions

`occupants.hpp` / `occupants.cpp` implement only recovered character-manager state transitions. `OccupantsState` is explicit save state, not a default game roster. Populate vectors/maps from recovered save or initialization data; the runtime never creates a new-game occupant list.

The API covers refusal, next-day self-kill scheduling, day+2 exile scheduling, ordinary kill bookkeeping, exile application, new-day bookkeeping, new arrival (`LetIn`), and the exact night-kill candidate filter. Vectors preserve C# list append/first-remove behavior. Dictionary additions reject duplicate keys and indexed reads fail when storage is missing.

`LetIn` takes serialized `isHuman`, character FEMA bonus, and random status bounds as explicit arguments. It preserves the enum-zero `FirstOrDefault` branch, place conflict return, optional replacement exile, in-house append, entry day, initial FEMA value, room add, type-19 `GenerateBabyEvents`, random status, impostor-map add, type-51 external arrival hook, then `CharacterAdded(type,false)`. A missing current-day provider follows the native null-delegate default of day 0. Room/event/meta/RNG operations are host callbacks; absent required callbacks throw instead of silently acting as if the service succeeded. A `PlaceAlreadyTaken` result corresponds to the original log-and-return branch.

The night-kill filter requires current in-house membership, strict signed `arrivalDay + 1 < currentDay`, and non-impostor status. `Random.Range(0,2)` uses Unity’s integer overload with an exclusive upper bound; the callback must preserve the host Unity RNG state and return the Unity integer result. The generated-status interval is inclusive at both configured float bounds, with the random call only inside the interval.

Run the focused tests:

```sh
c++ -std=c++17 -Wall -Wextra -Werror -Iinclude tests/occupants_tests.cpp src/occupants.cpp src/characters.cpp -o build-occupants/occupants_tests
build-occupants/occupants_tests
```

`../logic/selected_native_disassembly.txt` contains the checkpointed static `LetIn` disassembly. It was not revalidated against `.pdata` in this restored workspace, so no fresh PE-boundary proof is claimed.
