#include "ninah/inventory.hpp"

#include <algorithm>
#include <cassert>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace ninah;

static InventoryHooks make_hooks(std::vector<std::string>& order,
                                 std::vector<Consumable>& ever_in_meta,
                                 InventoryState* state = nullptr) {
    InventoryHooks hooks;
    hooks.updated_count = [&](Consumable item, std::int32_t count) {
        order.push_back("updated:" + std::to_string(static_cast<int>(item)) + ":" + std::to_string(count));
    };
    hooks.received_with_hint = [&](Consumable item, std::int32_t amount) {
        order.push_back("received:" + std::to_string(static_cast<int>(item)) + ":" + std::to_string(amount));
    };
    hooks.given_away_with_hint = [&](Consumable item, std::int32_t amount) {
        order.push_back("given:" + std::to_string(static_cast<int>(item)) + ":" + std::to_string(amount));
    };
    hooks.meta_ever_used = [&](Consumable item) {
        order.push_back("meta-query:" + std::to_string(static_cast<int>(item)));
        return std::find(ever_in_meta.begin(), ever_in_meta.end(), item) != ever_in_meta.end();
    };
    hooks.meta_use_consumable = [&](Consumable item) {
        order.push_back("meta-use:" + std::to_string(static_cast<int>(item)));
        ever_in_meta.push_back(item);
    };
    hooks.unlock_achievement = [&](const std::string& achievement) {
        order.push_back("achievement:" + achievement);
    };
    hooks.give_povistka = [&ever_in_meta, &order, state](std::int32_t recipient) {
        if (state) assert(state->povistkas_used == 1);
        order.push_back("give-povistka:" + std::to_string(recipient));
    };
    hooks.given_povistka = [&](std::int32_t recipient) {
        order.push_back("given-povistka:" + std::to_string(recipient));
    };
    hooks.fed_cat = [&] { order.push_back("fed-cat"); };
    return hooks;
}

int main() {
    {
        auto state = InventoryState::initial(true);
        assert(state.storage.size() == 11);
        assert(state.storage.at(Consumable::Bobeer) == 0);
        assert(state.storage.at(Consumable::Cockroach) == 0);
        auto fresh = InventoryState::initial(false);
        assert(fresh.storage.at(Consumable::Bobeer) == 8);
        assert(fresh.storage.at(Consumable::Kombucha) == 1);
        assert(fresh.storage.at(Consumable::Cockroach) == 1);
        assert(fresh.storage.at(Consumable::Coffee) == 0);
    }
    {
        auto state = InventoryState::initial(true);
        state.storage.at(Consumable::Coffee) = 1;
        std::vector<std::string> order;
        std::vector<Consumable> meta;
        Inventory inventory(state, make_hooks(order, meta));
        const bool removed = inventory.try_remove(Consumable::Coffee, 2, true);
        assert(!removed);
        assert(state.storage.at(Consumable::Coffee) == 1);
        assert(state.ever_used.empty() && state.today_used.empty());
        assert(order.empty());
    }
    {
        auto state = InventoryState::initial(true);
        state.storage.at(Consumable::Cigarette) = 1;
        state.storage.at(Consumable::Coffee) = 1;
        std::vector<std::string> order;
        std::vector<Consumable> meta;
        Inventory inventory(state, make_hooks(order, meta));
        assert(inventory.try_remove(Consumable::Cigarette, 1, true));
        assert(inventory.try_remove(Consumable::Cigarette, 0, false));
        assert(inventory.try_remove(Consumable::Coffee, 1, false));
        assert(state.ever_used.size() == 2);
        assert(state.ever_used[0] == Consumable::Cigarette);
        assert(state.ever_used[1] == Consumable::Coffee);
        assert((state.today_used == std::vector<Consumable>{Consumable::Cigarette,
                                                             Consumable::Cigarette,
                                                             Consumable::Coffee}));
        assert(order.back() == "achievement:CONSUM_COFFEE_CIG");
        assert(inventory.ever_used_this_run(Consumable::Cigarette));
    }
    {
        auto state = InventoryState::initial(true);
        state.storage.at(Consumable::Pills) = 1;
        std::vector<std::string> order;
        std::vector<Consumable> meta;
        Inventory inventory(state, make_hooks(order, meta));
        assert(inventory.try_remove(Consumable::Pills, -2));
        assert(state.storage.at(Consumable::Pills) == 3);
        assert(state.today_used.size() == 1 && state.ever_used.size() == 1);
    }
    {
        auto state = InventoryState::initial(true);
        state.storage.at(Consumable::Povistka) = 1;
        std::vector<std::string> order;
        std::vector<Consumable> meta;
        Inventory inventory(state, make_hooks(order, meta, &state));
        assert(inventory.try_give_item(Consumable::Povistka, 1, 42));
        assert(state.storage.at(Consumable::Povistka) == 0);
        assert(state.povistkas_used == 1);
        assert(order[0] == "updated:7:0");
        assert(order[1] == "given:7:1");
        assert(order[order.size() - 2] == "give-povistka:42");
        assert(order.back() == "given-povistka:42");
    }
    {
        auto state = InventoryState::initial(true);
        state.storage.at(Consumable::CatFood) = 1;
        std::vector<std::string> order;
        std::vector<Consumable> meta;
        Inventory inventory(state, make_hooks(order, meta));
        assert(inventory.try_give_item(Consumable::CatFood, 1, 8));
        assert(order.back() == "fed-cat");
    }
    {
        InventoryState state;
        std::vector<std::string> order;
        std::vector<Consumable> meta;
        Inventory inventory(state, make_hooks(order, meta));
        bool missing_storage_threw = false;
        try { (void)inventory.count(Consumable::Coffee); }
        catch (const std::out_of_range&) { missing_storage_threw = true; }
        assert(missing_storage_threw);
    }
    std::cout << "inventory tests passed\n";
}
