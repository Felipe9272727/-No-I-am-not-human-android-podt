# Recovered dialogue service functions

`DialogueServices` now handles all 19 registered Yarn functions represented by the current bridge: the existing ten functions plus `CanOrderCourier`, `GetCharacterOnPlace`, `GetCourierOrder`, `HasCompletedMushroomCondition`, `HasSeenDream`, `IsEverCompletedGame`, `IsNeedToGetDeficitItem`, `LocalizeItem`, and `PeekDeficitItem`.

The wrappers and signatures come from the retained `DialogCommandsInstance.cs`; native branches and string literals come from `cpp2il_isil_target/IsilDump/Assembly-CSharp/_Code/DialogSystem/Commands/DialogCommandsInstance.txt`, with the corresponding selected IL bodies in `selected_method_bodies.il`. The wrapper fields identify concrete service delegate types. Unrecovered state is supplied through `DialogueServiceHooks`; an absent hook raises a callback error so an unwired host cannot silently supply guessed gameplay state. The old constructor remains valid and leaves these hooks empty. For the five boolean delegates, a present callback returning `std::nullopt` explicitly models the native null-delegate branch and returns false; an absent hook means host wiring is missing and throws.

`GetCharacterOnPlace` parses `ECharacterType` case-insensitively, obtains the requested character's serialized `CharacterSOData.Place`, then scans `CharactersInside` in order and asks the host for each occupant's current place. It returns the first occupant at that place. When no occupant matches, the source's `FirstOrDefault<ECharacterType>` produces enum value `0`, which is `Sanya`, and the wrapper localizes `characterName_Sanya`. The localization table is `UI`. Character results use `characterName_{ECharacterType.ToString()}`.

`LocalizeItem` lowercases the raw item string and requests `consumable_{lowercase item}_name` from table `UI`; the wrapper does not parse it as an enum. `GetCourierOrder` builds the same key from the enum name of the current order, asks the host to localize it, then appends ` (x{count})`. The source constructs the default order `(Bobeer, 1)` when its order callback returns null; the typed hook can represent that source state with `std::nullopt`. `PeekDeficitItem` likewise converts a null callback result to the empty string. The provider callback itself remains required for both functions.

Dream and character argument parsing follows the retained `Enum.Parse(..., ignoreCase: true)` call pattern, including signed numeric enum strings. Dream IDs come from `EDream`; character names and values follow the retained `ECharacterType` declaration. Localization keys and `UI` table names match the native wrapper literals. The localization callback takes `(key, table)` and owns actual table lookup.

Run the focused callback, parsing, localization, default, and empty-occupant tests with:

```sh
g++ -std=c++17 -Wall -Wextra -Werror -pedantic \
  -Ireconstruction/native-game/include \
  reconstruction/native-game/src/dialogue_services.cpp \
  reconstruction/native-game/src/core.cpp \
  reconstruction/native-game/src/characters.cpp \
  reconstruction/native-game/src/inventory.cpp \
  reconstruction/native-game/src/phone.cpp \
  reconstruction/native-game/tests/dialogue_services_tests.cpp \
  -o /tmp/ninah-dialogue-services-tests
/tmp/ninah-dialogue-services-tests
```

The check exercises host callbacks only; it does not load or execute the original PE/DLL. Native evidence establishes wrapper flow, delegate calls, enum parsing, localization keys, and the empty-list default. It does not establish the runtime provider state for courier eligibility/order, mushroom-condition completion, seen-dream history, completion history, deficit-item state, current occupant places, or localization table results. The host must supply those through hooks.
