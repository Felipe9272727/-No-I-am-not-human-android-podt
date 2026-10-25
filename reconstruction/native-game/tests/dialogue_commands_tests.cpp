#include "ninah/dialogue_commands.hpp"

#include <cassert>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace ninah;

static CharacterData character(int type, const std::string& name) {
    return CharacterData{type, name, 0, type, false, true, false, false,
                         {}, {}, 0};
}

static CharacterData character_at(int type, const std::string& name, int place,
                                  bool imposter = false) {
    return CharacterData{type, name, 0, place, imposter, true, false, false,
                         {}, {}, 0};
}

int main() {
    CharacterCatalog catalog({character(12, "Scammer"), character(73, "FunnyGuy")});
    OccupantsState occupants_state;
    OccupantsRuntime occupants(catalog, occupants_state, {}, 0.0f);

    auto inventory_state = InventoryState::initial(false);
    std::vector<std::string> order;
    InventoryHooks hooks;
    hooks.updated_count = [&order](Consumable item, std::int32_t count) {
        assert(item == Consumable::Coffee);
        order.push_back("item:" + std::to_string(count));
    };
    Inventory inventory(inventory_state, hooks);
    DialogueCommandDispatcher dispatcher(inventory, occupants, [] { return 4; });

    dispatcher.dispatch_all({GetItemCommand{Consumable::Coffee, 2},
                             RefuseCommand{12},
                             KillTomorrowCommand{73},
                             ExileAfterTomorrowCommand{12}});

    assert(inventory.count(Consumable::Coffee) == 2);
    assert(occupants_state.refused == std::vector<std::int32_t>{12});
    assert(occupants_state.self_kill_next_day == std::vector<std::int32_t>{73});
    assert(occupants_state.exiles_on_days.at(6) == std::vector<std::int32_t>{12});
    assert(order == std::vector<std::string>{"item:2"});

    const auto inventory_before = inventory.count(Consumable::Coffee);
    const auto refused_before = occupants_state.refused;
    const auto scheduled_before = occupants_state.self_kill_next_day;
    bool rejected = false;
    try {
        dispatcher.dispatch_all({GetItemCommand{Consumable::Coffee, 3},
                                 UnsupportedDialogueCommand{"SetEmotion"}});
    } catch (const std::invalid_argument& error) {
        rejected = std::string(error.what()).find("SetEmotion") != std::string::npos;
    }
    assert(rejected);
    assert(inventory.count(Consumable::Coffee) == inventory_before);
    assert(occupants_state.refused == refused_before);
    assert(occupants_state.self_kill_next_day == scheduled_before);
    assert(order == std::vector<std::string>{"item:2"});

    bool bad_character_rejected = false;
    try {
        dispatcher.dispatch(RefuseCommand{999});
    } catch (const std::out_of_range&) {
        bad_character_rejected = true;
    }
    assert(bad_character_rejected);
    assert(occupants_state.refused == refused_before);

    bool missing_let_in_inputs_rejected = false;
    try {
        dispatcher.dispatch(LetCharacterInCommand{12});
    } catch (const std::logic_error&) {
        missing_let_in_inputs_rejected = true;
    }
    assert(missing_let_in_inputs_rejected);
    assert(occupants_state.characters.inside.empty());
    bool batch_missing_service_rejected = false;
    try {
        dispatcher.dispatch_all({GetItemCommand{Consumable::Coffee, 5},
                                 LetCharacterInCommand{12}});
    } catch (const std::logic_error&) {
        batch_missing_service_rejected = true;
    }
    assert(batch_missing_service_rejected);
    assert(inventory.count(Consumable::Coffee) == inventory_before);
    bool batch_missing_courier_rejected = false;
    try {
        dispatcher.dispatch_all({GetItemCommand{Consumable::Coffee, 5},
                                 OrderCourierCommand{Consumable::Coffee, 1}});
    } catch (const std::logic_error&) {
        batch_missing_courier_rejected = true;
    }
    assert(batch_missing_courier_rejected);
    assert(inventory.count(Consumable::Coffee) == inventory_before);
    bool missing_kill_room_rejected = false;
    try {
        dispatcher.dispatch_all({GetItemCommand{Consumable::Coffee, 5},
                                 KillRoomCommand{73}});
    } catch (const std::logic_error&) {
        missing_kill_room_rejected = true;
    }
    assert(missing_kill_room_rejected);
    assert(inventory.count(Consumable::Coffee) == inventory_before);
    bool missing_exile_dialog_rejected = false;
    try {
        dispatcher.dispatch(ExileCharacterCommand{12, true});
    } catch (const std::logic_error&) {
        missing_exile_dialog_rejected = true;
    }
    assert(missing_exile_dialog_rejected);
    assert(occupants_state.exiled.empty());

    {
        // Original enum IDs: Fan=8, Widow=11, Scammer=12.
        CharacterCatalog command_catalog({character_at(8, "Fan", 40),
                                          character_at(11, "Widow", 40),
                                          character_at(12, "Scammer", 41)});
        OccupantsState command_state;
        command_state.characters.inside = {11, 12};
        command_state.fema_rating = {{11, .3f}, {12, .4f}};
        command_state.came_in_days = {{11, 2}, {12, 3}};
        command_state.are_imposters = {{11, false}, {12, false}};
        command_state.characters.with_povistka = {11};
        std::vector<std::string> effects;
        OccupantsHooks occupant_hooks;
        occupant_hooks.room_add_character = [&effects](int room, int id, bool silent) {
            assert(room == 0 && !silent);
            effects.push_back("room-add:" + std::to_string(id));
            return true;
        };
        occupant_hooks.room_exile_character = [&effects](int id) {
            effects.push_back("room-exile:" + std::to_string(id));
            return true;
        };
        occupant_hooks.character_removed = [&effects](int id) {
            effects.push_back("removed:" + std::to_string(id));
        };
        occupant_hooks.character_added = [&effects](int id, bool loaded) {
            assert(!loaded);
            effects.push_back("added:" + std::to_string(id));
        };
        occupant_hooks.room_kill_character = [&effects](int id) {
            effects.push_back("room-kill:" + std::to_string(id));
            return true;
        };
        occupant_hooks.unity_random_value = [] { return .5f; };
        occupant_hooks.record_kill_effects = [&effects](int id, bool player, bool imposter) {
            assert(player && !imposter);
            effects.push_back("record-kill:" + std::to_string(id));
        };
        occupant_hooks.unlock_achievement = [&effects](const std::string& id) {
            effects.push_back("achievement:" + id);
        };
        OccupantsRuntime command_occupants(command_catalog, command_state,
                                           occupant_hooks, .75f);
        auto command_inventory_state = InventoryState::initial(false);
        Inventory command_inventory(command_inventory_state);
        DialogueCommandDispatcher command_dispatcher(
            command_inventory, command_occupants, [] { return 7; },
            [](int id) {
                assert(id == 8);
                return LetInInputs{.2f, .05f, .1f, .5f};
            },
            [&effects](int id) {
                effects.push_back("show-exile:" + std::to_string(id));
            });

        command_dispatcher.dispatch(LetCharacterInCommand{8});
        assert(command_state.characters.inside == (std::vector<int>{11, 12}));
        assert(command_state.exiled.empty());
        assert(effects.empty());

        command_dispatcher.dispatch(AggressiveLetInCommand{8});
        assert(command_state.characters.inside == (std::vector<int>{12, 8}));
        assert(command_state.exiled == std::vector<int>{11});
        assert(command_state.characters.with_povistka.empty());
        assert(command_state.came_in_days.back() == std::make_pair(8, 7));
        assert((effects == std::vector<std::string>{"room-exile:11", "removed:11",
                                                    "room-add:8", "added:8"}));

        effects.clear();
        command_dispatcher.dispatch(KillCommand{12});
        assert(command_state.killed == std::vector<int>{12});
        assert(command_state.innocents_killed_by_player == std::vector<int>{12});
        assert((effects == std::vector<std::string>{"room-kill:12", "record-kill:12",
                                                    "removed:12", "achievement:KILL_HUMAN"}));

        effects.clear();
        command_dispatcher.dispatch(ExileCharacterCommand{8, true});
        assert(command_state.exiled == (std::vector<int>{11, 8}));
        assert((effects == std::vector<std::string>{"room-exile:8", "removed:8",
                                                    "show-exile:8"}));
    }

    {
        auto command_inventory_state = InventoryState::initial(false);
        Inventory command_inventory(command_inventory_state);
        std::int32_t day = 8;
        std::int32_t deficit_day = 0;
        const DeficitConsumableTargets targets{{Consumable::Coffee, 0}};
        OtherGameDeficitDataRef other_data{&targets, [] { return 4; }};
        ConsumablesDeficitService deficit(
            command_inventory, [&] { return day; }, {&deficit_day}, other_data,
            [](std::int32_t minimum, std::int32_t maximum) {
                assert(minimum == 0 && maximum == 5);
                return 3;
            });
        std::vector<CourierOrder> ordered;
        CourierDialogHooks courier_hooks;
        courier_hooks.ordered_subscribers.push_back(
            [&](Consumable item, std::int32_t count) {
                ordered.push_back({item, count});
            });
        CourierService courier({}, courier_hooks, &deficit);
        std::vector<std::int32_t> room_kills;
        std::vector<std::int32_t> fema_exiles;
        DialogueCommandDispatcher command_dispatcher(
            command_inventory, occupants, {}, {}, {}, &courier,
            [&](std::int32_t count) { fema_exiles.push_back(count); },
            [&](std::int32_t id) { room_kills.push_back(id); });

        command_dispatcher.dispatch_all(
            {OrderCourierCommand{Consumable::CatFood, 2},
             UpdateDeficitDayCommand{}, ExileByFEMACommand{1},
             KillRoomCommand{73}});
        assert(ordered.size() == 1 && ordered[0].item == Consumable::CatFood &&
               ordered[0].count == 2);
        assert(deficit_day == day + 4);
        assert(fema_exiles == std::vector<std::int32_t>{1});
        assert(room_kills == std::vector<std::int32_t>{73});
        assert(occupants_state.killed.empty());

        // ExileByFEMA is a multicast action and safely does nothing without
        // subscribers; KillRoom still needs its concrete room-manager hook.
        DialogueCommandDispatcher without_fema(
            command_inventory, occupants, {}, {}, {}, &courier);
        without_fema.dispatch(ExileByFEMACommand{2});
    }

    std::cout << "dialogue command dispatcher tests passed\n";
}
