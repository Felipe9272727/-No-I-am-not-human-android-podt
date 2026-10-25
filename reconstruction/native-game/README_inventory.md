# Recovered inventory behavior

`Inventory` mirrors `ConsumablesController` and `ConsumablesSaveData` without adding initial values to an existing save. Call `InventoryState::initial(need_load)` only at the recovered creation/load boundary: all eleven original enum IDs are inserted at zero, and `Bobeer=8`, `Kombucha=1`, `Cockroach=1` are added only when `need_load` is false.

`Count` and mutations use `unordered_map::at`, so missing saved storage throws like `Dictionary.get_Item`. `Add` and successful `TryRemove` use wrapping 32-bit arithmetic. `TryRemove` checks `stored < requested` before any callback or mutation; this preserves the original negative-count behavior. It updates count, optionally raises the hint event, checks meta ever-used state and records a meta use only when needed, appends to the ever-used save list once, and appends to today-used every time. The coffee+cigarette achievement checks today-used membership after the append. Successful Povistka removals increment `PovistkasUsed` once per call.

`TryGiveItem` removes with the hint flag enabled first. On success it performs the Povistka recipient call and optional event, or the optional FedCat event for CatFood. These effects are supplied by explicit hooks. Missing required meta/recipient/achievement handlers throw where reached; missing event subscribers mean the original event has no listeners.

Compile the focused tests:

```sh
c++ -std=c++17 -Wall -Wextra -Werror -Iinclude tests/inventory_tests.cpp src/inventory.cpp -o build-occupants/inventory_tests
build-occupants/inventory_tests
```

The restored checkpoint contains declarations but not the earlier extracted `ConsumablesController` native/IL method block. The transition rules above were supplied from the prior static recovery history and are implemented without claiming the unavailable binary proof was re-run. The generated inventory/source evidence should be reattached after the GameAssembly recovery finishes.
