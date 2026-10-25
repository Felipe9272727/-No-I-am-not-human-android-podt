#include "ninah/courier.hpp"

#include <cassert>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace ninah;

int main() {
    auto inventory_state = InventoryState::initial(true);
    Inventory inventory(inventory_state);
    inventory.add(Consumable::Enerjeka, 2);
    inventory.add(Consumable::Cigarette, 0);
    inventory.add(Consumable::Coffee, 1);
    inventory.add(Consumable::CatFood, 1);
    inventory.add(Consumable::Kombucha, 0);
    inventory.add(Consumable::Povistka, 0);

    std::int32_t day = 4;
    std::int32_t last_courier_day = 0;
    DayNightCourierRefs day_refs{
        [&] { return day; },
        [&] { return last_courier_day; },
    };

    const DeficitConsumableTargets targets{
        {Consumable::Enerjeka, 2}, // Source OtherGameData item/order/target values.
        {Consumable::Cigarette, 0},
        {Consumable::Coffee, 1},
        {Consumable::CatFood, 0},
        {Consumable::Kombucha, 1},
        {Consumable::Povistka, 0},
    };
    std::int32_t deficit_item_day = 5;
    std::vector<std::string> deficit_calls;
    OtherGameDeficitDataRef other_data{
        &targets,
        [&] { deficit_calls.push_back("random-days"); return 3; },
    };
    ConsumablesDeficitService deficit(
        inventory, [&] { return day; }, {&deficit_item_day}, other_data,
        [&](std::int32_t minimum, std::int32_t maximum) {
            assert(minimum == 0 && maximum == 5);
            deficit_calls.push_back("random-range:" + std::to_string(minimum) + ":" +
                                    std::to_string(maximum));
            return std::int32_t{2};
        });

    std::vector<std::string> events;
    std::vector<CourierOrder> submitted_orders;
    CourierDialogHooks hooks;
    hooks.ordered_subscribers = {
        [&](Consumable item, std::int32_t count) {
            submitted_orders.push_back({item, count});
            events.push_back("ordered-1");
        },
        [&](Consumable item, std::int32_t count) {
            submitted_orders.push_back({item, count});
            events.push_back("ordered-2");
        },
    };
    hooks.get_order_subscribers = {
        [&]() -> std::optional<CourierOrder> {
            events.push_back("get-order-1");
            return CourierOrder{Consumable::Coffee, 2};
        },
        [&]() -> std::optional<CourierOrder> {
            events.push_back("get-order-2");
            return CourierOrder{Consumable::Pills, 0};
        },
    };
    hooks.localize = [&](const std::string& key, const std::string& table) {
        assert(table == "UI");
        events.push_back("localize:" + key);
        return std::string("label");
    };
    CourierService courier(day_refs, hooks, &deficit);

    // The source condition is strict: last + 2 must be less than current day.
    assert(courier.can_order_courier()); // 0 + 2 < 4
    day = 2;
    assert(!courier.can_order_courier());
    day = 3;
    assert(true == courier.can_order_courier());
    last_courier_day = 1;
    assert(!courier.can_order_courier()); // 1 + 2 == 3
    last_courier_day = 0;
    day = 4;
    assert(courier.can_order_courier());
    assert(!CourierService({}, {}).can_order_courier());

    events.clear();
    courier.order_courier("cOfFeE", -2);
    assert((events == std::vector<std::string>{"ordered-1", "ordered-2"}));
    assert(submitted_orders.size() == 2);
    assert(submitted_orders[0].item == Consumable::Coffee && submitted_orders[0].count == -2);
    assert(submitted_orders[1].item == Consumable::Coffee && submitted_orders[1].count == -2);
    events.clear();
    courier.order_courier("100", 0); // Enum.Parse accepts numeric enum values.
    assert((events == std::vector<std::string>{"ordered-1", "ordered-2"}));
    assert(submitted_orders.size() == 4);
    assert(static_cast<std::int32_t>(submitted_orders[2].item) == 100);
    assert(submitted_orders[2].count == 0 && submitted_orders[3].count == 0);
    bool invalid_enum = false;
    try { courier.order_courier("coffee-invalid", 1); }
    catch (const std::invalid_argument&) { invalid_enum = true; }
    assert(invalid_enum);
    assert(events.size() == 2); // Parse fails before delegate invocation.
    assert(static_cast<std::int32_t>(parse_consumable_enum("42")) == 42);
    assert(static_cast<std::int32_t>(parse_consumable_enum("Cigarette, Coffee")) == 3);

    events.clear();
    assert(courier.get_courier_order() == "label (x0)");
    assert((events == std::vector<std::string>{"get-order-1", "get-order-2",
                                               "localize:consumable_pills_name"}));
    CourierDialogHooks default_order_hooks;
    default_order_hooks.localize = [&](const std::string& key, const std::string& table) {
        assert(key == "consumable_bobeer_name" && table == "UI");
        return std::string("bobeer label");
    };
    CourierService default_order({}, default_order_hooks);
    assert(default_order.get_courier_order() == "bobeer label (x1)");
    CourierService unsupported_localization({}, {});
    bool missing_localizer = false;
    try { (void)unsupported_localization.get_courier_order(); }
    catch (const std::logic_error&) { missing_localizer = true; }
    assert(missing_localizer);

    // The day gate is inclusive at DeficitItemDay; below it, no deficit is due.
    day = 4;
    assert(!courier.is_need_to_get_deficit_item());
    day = 5;
    assert(courier.is_need_to_get_deficit_item());
    assert(courier.peek_deficit_item() == "Coffee");
    assert(deficit_calls == std::vector<std::string>{"random-range:0:5"});
    courier.update_deficit_day();
    assert(deficit_item_day == 8);
    assert(deficit_calls == (std::vector<std::string>{"random-range:0:5", "random-days"}));

    // No selected subscribers preserves wrapper defaults: false, empty string, no-op.
    CourierService no_deficit(day_refs);
    assert(!no_deficit.is_need_to_get_deficit_item());
    assert(no_deficit.peek_deficit_item().empty());
    no_deficit.update_deficit_day();
    assert(deficit_item_day == 8);

    const DeficitConsumableTargets no_shortages{{Consumable::Coffee, 0}};
    OtherGameDeficitDataRef no_shortage_data{&no_shortages, [&] { return 1; }};
    ConsumablesDeficitService no_shortage(
        inventory, [&] { return day; }, {&deficit_item_day}, no_shortage_data,
        [](std::int32_t, std::int32_t) { return std::int32_t{0}; });
    assert(!no_shortage.is_need_to_get_item());
    assert(no_shortage.get_deficit_item() == Consumable::Bobeer); // default(EConsumable)

    assert(consumable_enum_name(static_cast<Consumable>(42)) == "42");
    std::cout << "courier service tests passed\n";
}
