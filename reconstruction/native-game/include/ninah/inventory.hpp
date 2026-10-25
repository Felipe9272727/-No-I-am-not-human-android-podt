#pragma once

#include <cstdint>
#include <functional>
#include <string>
#include <unordered_map>
#include <vector>

namespace ninah {

enum class Consumable : std::int32_t {
    Bobeer = 0,
    Cigarette = 1,
    Coffee = 2,
    Enerjeka = 3,
    Pills = 4,
    Mushroom = 5,
    CatFood = 6,
    Povistka = 7,
    Kombucha = 8,
    Photo = 9,
    Cockroach = 100,
};

struct InventoryState {
    std::unordered_map<Consumable, std::int32_t> storage;
    std::vector<Consumable> ever_used;
    std::vector<Consumable> today_used;
    std::int32_t povistkas_used = 0;

    static InventoryState initial(bool need_load);
};

struct InventoryHooks {
    // Optional event subscribers. UpdatedCount is raised after every write.
    std::function<void(Consumable, std::int32_t)> updated_count;
    std::function<void(Consumable, std::int32_t)> received_with_hint;
    std::function<void(Consumable, std::int32_t)> given_away_with_hint;

    // Required on successful removal; reflects meta persistence, separate from
    // ConsumablesSaveData::ever_used.
    std::function<bool(Consumable)> meta_ever_used;
    std::function<void(Consumable)> meta_use_consumable;
    std::function<void(const std::string&)> unlock_achievement;

    // External effects triggered by TryGiveItem; no implied success behavior.
    std::function<void(std::int32_t)> give_povistka;
    std::function<void(std::int32_t)> given_povistka;
    std::function<void()> fed_cat;
};

class Inventory {
public:
    explicit Inventory(InventoryState& state, InventoryHooks hooks = {});

    std::int32_t count(Consumable item) const;
    bool ever_used_this_run(Consumable item) const;
    void add(Consumable item, std::int32_t amount = 1, bool show_hint = false);
    bool try_remove(Consumable item, std::int32_t amount = 1, bool show_hint = false);
    bool try_give_item(Consumable item, std::int32_t amount, std::int32_t recipient);
    const InventoryState& state() const noexcept { return state_; }

private:
    InventoryState& state_;
    InventoryHooks hooks_;
};

} // namespace ninah
