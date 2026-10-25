#pragma once

#include "ninah/inventory.hpp"

#include <cstddef>
#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <vector>

namespace ninah {

struct CourierOrder {
    Consumable item;
    std::int32_t count;
};

// Ordered references to the source OtherGameSOData.DeficitConsumables map.
// The adapter must preserve the source dictionary's enumeration order.
struct DeficitConsumableTarget {
    Consumable item;
    std::int32_t target_count;
};
using DeficitConsumableTargets = std::vector<DeficitConsumableTarget>;

struct OtherGameDeficitDataRef {
    const DeficitConsumableTargets* items = nullptr;
    // Calls the original OtherGameSOData.GetDeficitRandomDaysCount getter,
    // retaining its configured bounds and Unity random behavior.
    std::function<std::int32_t()> get_random_days_count;
};

struct ConsumablesDeficitSaveRef {
    // Reference to ConsumablesSaveData.DeficitItemDay; state remains externally owned.
    std::int32_t* deficit_item_day = nullptr;
};

// A small native view over the source ConsumablesController inputs. It does not
// own or mirror day, save, inventory, or OtherGameSOData state.
class ConsumablesDeficitService {
public:
    using CurrentDay = std::function<std::int32_t()>;
    using RandomRange = std::function<std::int32_t(std::int32_t, std::int32_t)>;

    ConsumablesDeficitService(Inventory&, CurrentDay,
                              ConsumablesDeficitSaveRef,
                              OtherGameDeficitDataRef,
                              RandomRange);

    bool is_need_to_get_item() const;
    Consumable get_deficit_item() const;
    void update_deficit_day() const;

private:
    std::vector<Consumable> eligible_items() const;

    Inventory& inventory_;
    CurrentDay current_day_;
    ConsumablesDeficitSaveRef save_;
    OtherGameDeficitDataRef other_game_data_;
    RandomRange random_range_;
};

// Explicit source references. DayNightController owns current_day and
// LastCourierOrderedDay; DialogManager owns queued order save/claim behavior.
struct DayNightCourierRefs {
    std::function<std::int32_t()> current_day;
    std::function<std::int32_t()> last_courier_ordered_day;
};

struct CourierDialogHooks {
    // Mirrors DialogCommandsInstance.OrderedCourier multicast delegate order.
    std::vector<std::function<void(Consumable, std::int32_t)>> ordered_subscribers;
    // Mirrors GotCourierOrder Func delegate. Each callback may apply the saved
    // order and clear its source save field; multicast returns the last result.
    std::vector<std::function<std::optional<CourierOrder>()>> get_order_subscribers;
    // Uses LocalizationExtension.GetLocalization(key, "UI") from the source game.
    std::function<std::string(const std::string& key,
                              const std::string& table)> localize;
};

class CourierService {
public:
    CourierService(DayNightCourierRefs,
                   CourierDialogHooks = {},
                   ConsumablesDeficitService* = nullptr);

    bool can_order_courier() const;
    std::string get_courier_order() const;
    void order_courier(const std::string& raw_consumable, std::int32_t count) const;

    void update_deficit_day() const;
    bool is_need_to_get_deficit_item() const;
    std::string peek_deficit_item() const;

private:
    DayNightCourierRefs day_night_;
    CourierDialogHooks dialog_;
    ConsumablesDeficitService* deficit_;
};

// Source enum conversion used by Enum.Parse(..., ignoreCase: true) and
// Enum.ToString(). Numeric enum values are preserved even when undefined.
Consumable parse_consumable_enum(const std::string&);
std::string consumable_enum_name(Consumable);

} // namespace ninah
