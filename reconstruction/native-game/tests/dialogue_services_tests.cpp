#include "ninah/dialogue_services.hpp"

#include <cassert>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using namespace ninah;

CharacterData character(std::int32_t type, const char* name, std::int32_t place) {
    return {type, name, 0, place, false, true, false, false, {}, {}, 0};
}

NinahYarnArg string_arg(const char* value) { return {3, 0.0, value}; }

std::string invoke(DialogueServices& services, const char* function,
                   const NinahYarnArg* args = nullptr, std::size_t count = 0) {
    const auto* value = DialogueServices::callback(&services, function, args, count);
    if (!value) throw std::runtime_error(services.last_error());
    return value;
}

void missing_hook_fails(DialogueServices& services, const char* function,
                        const NinahYarnArg* args = nullptr, std::size_t count = 0) {
    assert(DialogueServices::callback(&services, function, args, count) == nullptr);
    if (services.last_error().find("dialogue service unavailable") == std::string::npos) {
        throw std::runtime_error(std::string(function) + " missing-hook error was: " + services.last_error());
    }
}
}

int main() {
    using namespace ninah;
    EnergyState energy;
    CharacterCatalog catalog({
        character(3, "Neighbour", 12),
        character(6, "Daughter", 21),
        character(74, "Alt", 42),
    });
    CharactersState occupants;
    occupants.inside = {6, 74};
    auto inventory_state = InventoryState::initial(false);
    Inventory inventory(inventory_state);

    std::vector<std::pair<std::string, std::string>> localization_calls;
    std::int32_t seen_dream = -1;
    DialogueServiceHooks hooks;
    hooks.can_order_courier = [] { return true; };
    hooks.get_courier_order = [] { return std::optional<CourierOrder>{{Consumable::Coffee, 2}}; };
    hooks.has_completed_mushroom_condition = [] { return true; };
    hooks.has_seen_dream = [&seen_dream](std::int32_t dream) { seen_dream = dream; return dream == 3; };
    hooks.is_ever_completed_game = [] { return true; };
    hooks.is_need_to_get_deficit_item = [] { return true; };
    hooks.peek_deficit_item = [] { return std::optional<std::string>{"Povistka"}; };
    hooks.get_current_place = [](std::int32_t character_id) {
        if (character_id == 6 || character_id == 74) return 12;
        throw std::out_of_range("fixture has no place for character");
    };
    hooks.localize = [&localization_calls](const std::string& key, const std::string& table) {
        localization_calls.emplace_back(key, table);
        return "localized:" + key;
    };

    DialogueServices services(energy, catalog, occupants, inventory, nullptr, hooks);
    assert(invoke(services, "CanOrderCourier") == "true");
    assert(invoke(services, "GetCourierOrder") == "\"localized:consumable_coffee_name (x2)\"");
    assert(invoke(services, "HasCompletedMushroomCondition") == "true");

    auto dream = string_arg("mUsHrOoM");
    assert(invoke(services, "HasSeenDream", &dream, 1) == "true");
    assert(seen_dream == 3);
    auto numeric_dream = string_arg(" 3 ");
    assert(invoke(services, "HasSeenDream", &numeric_dream, 1) == "true");
    assert(seen_dream == 3);
    assert(invoke(services, "IsEverCompletedGame") == "true");
    assert(invoke(services, "IsNeedToGetDeficitItem") == "true");

    assert(invoke(services, "PeekDeficitItem") == "\"Povistka\"");
    auto localize_item = string_arg("CoFfEe");
    assert(invoke(services, "LocalizeItem", &localize_item, 1) == "\"localized:consumable_coffee_name\"");
    assert(localization_calls.back() == std::make_pair(std::string("consumable_coffee_name"), std::string("UI")));

    auto target = string_arg("nEiGhBoUr");
    assert(invoke(services, "GetCharacterOnPlace", &target, 1) == "\"localized:characterName_Daughter\"");
    assert(localization_calls.back() == std::make_pair(std::string("characterName_Daughter"), std::string("UI")));

    // The native wrapper uses FirstOrDefault over current occupants; an empty
    // match set therefore resolves to enum value 0 (Sanya), then localizes it.
    occupants.inside.clear();
    assert(invoke(services, "GetCharacterOnPlace", &target, 1) == "\"localized:characterName_Sanya\"");
    assert(localization_calls.back() == std::make_pair(std::string("characterName_Sanya"), std::string("UI")));

    DialogueServiceHooks null_results = hooks;
    null_results.get_courier_order = [] { return std::optional<CourierOrder>{}; };
    null_results.peek_deficit_item = [] { return std::optional<std::string>{}; };
    DialogueServices defaults(energy, catalog, occupants, inventory, nullptr, null_results);
    assert(invoke(defaults, "GetCourierOrder") == "\"localized:consumable_bobeer_name (x1)\"");
    assert(invoke(defaults, "PeekDeficitItem") == "\"\"");

    DialogueServiceHooks no_subscribers = hooks;
    no_subscribers.can_order_courier = [] { return std::optional<bool>{}; };
    no_subscribers.has_completed_mushroom_condition = [] { return std::optional<bool>{}; };
    no_subscribers.has_seen_dream = [](std::int32_t) { return std::optional<bool>{}; };
    no_subscribers.is_ever_completed_game = [] { return std::optional<bool>{}; };
    no_subscribers.is_need_to_get_deficit_item = [] { return std::optional<bool>{}; };
    DialogueServices native_nulls(energy, catalog, occupants, inventory, nullptr, no_subscribers);
    assert(invoke(native_nulls, "CanOrderCourier") == "false");
    assert(invoke(native_nulls, "HasCompletedMushroomCondition") == "false");
    assert(invoke(native_nulls, "HasSeenDream", &dream, 1) == "false");
    assert(invoke(native_nulls, "IsEverCompletedGame") == "false");
    assert(invoke(native_nulls, "IsNeedToGetDeficitItem") == "false");

    // The historical constructor signature remains source-compatible.
    DialogueServices old_constructor(energy, catalog, occupants, inventory);
    missing_hook_fails(old_constructor, "CanOrderCourier");
    missing_hook_fails(old_constructor, "GetCourierOrder");
    missing_hook_fails(old_constructor, "HasCompletedMushroomCondition");
    missing_hook_fails(old_constructor, "IsEverCompletedGame");
    missing_hook_fails(old_constructor, "IsNeedToGetDeficitItem");
    missing_hook_fails(old_constructor, "PeekDeficitItem");
    auto old_dream = string_arg("Ball");
    missing_hook_fails(old_constructor, "HasSeenDream", &old_dream, 1);
    auto old_item = string_arg("Coffee");
    missing_hook_fails(old_constructor, "LocalizeItem", &old_item, 1);
    missing_hook_fails(old_constructor, "GetCharacterOnPlace", &target, 1);

    auto bad_dream = string_arg("NotADream");
    assert(DialogueServices::callback(&services, "HasSeenDream", &bad_dream, 1) == nullptr);
    assert(services.last_error().find("invalid dream enum") != std::string::npos);
    assert(DialogueServices::callback(&services, "CanOrderCourier", &target, 1) == nullptr);
    assert(services.last_error() == "invalid game-function arity");

    std::cout << "Nine recovered dialogue service wrappers passed\n";
}
