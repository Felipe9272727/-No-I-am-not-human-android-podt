# Courier and consumables-deficit source evidence

All evidence below is from local ISIL, generated C# declarations, and raw Unity serialized asset bytes. The Windows PE and managed game code were not executed.

## Courier wrappers and subscribers

- `_Code/DialogSystem/Commands/DialogCommandsInstance.txt`, `OrderCourier(string,int)`: calls `Enum.Parse(typeof(EConsumable), rawConsumable, true)` and then invokes `OrderedCourier` if non-null. It does not call `CanOrderCourier`, impose a price, alter the count, or mutate inventory itself. A missing action delegate is a no-op. The two callback paths execute in the multicast invocation-list registration order.
- `CanOrderCourier()` invokes `CouldOrderCourier`; null delegate returns false. `_Code/Infrastructure/DayNight/DayNightController.txt`, `OnCouldOrderCourier()`: returns false if the day/night save reference is null; otherwise compares `LastCourierOrderedDay + 2 < _day`. No time-of-day or action count is read by this method.
- `GetCourierOrder()` invokes the `Func<DialogCourierOrderData>` delegate. A missing delegate or null return produces `DialogCourierOrderData(EConsumable.Bobeer, 1)`. It builds `consumable_<enum-name-lowercase>_name`, localizes from table `UI`, and formats ` (x{count})`.
- `_Code/DialogSystem/DialogManager.txt`, `OnOrderedCourier(EConsumable,int)`: invokes the manager's own `OrderedCourier` callback, constructs and stores `DialogSaveData.CourierOrderData` with the supplied item/count, and raises the save-data change notification.
- `OnGotCourierOrder()`: copies the stored courier order, clears `CourierOrderData`, then calls `IConsumablesController.Add(item,count,isShowHint:true)` and returns the copied order. No queued order returns through the command wrapper's Bobeer × 1 fallback.
- The wrapper invokes `UpdateDeficitDay` action subscribers when present; absent action is a no-op. `IsNeedToGetDeficitItem` defaults false without its `Func<bool>` subscriber. `PeekDeficitItem` defaults empty without its `Func<string>` subscriber.

## Consumables state and eligibility

- `_Code/Infrastructure/Consumables/ConsumablesSaveData.txt`: `Storage`, `DeficitItemDay`, `PovistkasUsed`, and consumable-use lists are members of the existing save object. The native model stores only a pointer/reference to `DeficitItemDay`; it does not create a second counter.
- `_Code/Infrastructure/Consumables/ConsumablesController.txt`, `IsNeedToGetDeficitItem()`: calls the injected current-day function, returns false if current day is less than saved `DeficitItemDay`, then asks whether any `OtherGameSOData.DeficitConsumables` entry passes the comparison `configuredTarget >= currentStorageCount`.
- `GetDeficitItem()` filters the same source dictionary with the same comparison, projects keys in dictionary enumeration order, and delegates random selection to `RandomElementFromCollectionExtension.GetRandomElement`. That helper returns default enum value 0 for an empty collection and otherwise calls the Unity integer random-range helper and selects the indexed element.
- `UpdateDeficitDay()` assigns `currentDay + OtherGameSOData.GetDeficitRandomDaysCount` to the existing saved field. `GetDeficitRandomDaysCount` uses the serialized `_daysRange` bounds and Unity random-range code. These calls remain injected through typed providers so native code uses the same external day/save/config/RNG state.

## Serialized `OtherGameData` values

`sharedassets0.assets` MonoBehaviour path ID 2715 (`OtherGameData`) has a 356-byte raw record. Its generated `OtherGameSOData.cs` declaration places `_daysRange` before `_deficitConsumables`; reading that typed prefix gives:

| Source field | Value |
|---|---:|
| `_daysRange` minimum | 2 |
| `_daysRange` maximum | 3 |
| `DeficitConsumables` entry count | 6 |

The serialized dictionary entry order and target counts are:

| Position | `EConsumable` | target count |
|---:|---|---:|
| 1 | Enerjeka | 2 |
| 2 | Cigarette | 0 |
| 3 | Coffee | 1 |
| 4 | CatFood | 0 |
| 5 | Kombucha | 1 |
| 6 | Povistka | 0 |

This mapping is supplied as a typed ordered reference to the native deficit service. The implementation does not hard-code or reorder these serialized entries.

## Native implementation boundary

`reconstruction/native-game/include/ninah/courier.hpp` and `src/courier.cpp` implement wrappers, the recovered courier-day predicate, deficit eligibility, and day update. `CourierDialogHooks` model explicit event subscribers; `DayNightCourierRefs`, `OtherGameDeficitDataRef`, and `ConsumablesDeficitSaveRef` refer to source-owned state. The implementation has no stored order, courier-day, deficit-day, or inventory mirror. Random selection and localization are external callbacks. `tests/courier_tests.cpp` exercises callback order and source-config test cases.
