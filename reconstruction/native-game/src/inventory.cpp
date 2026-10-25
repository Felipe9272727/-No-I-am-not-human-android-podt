#include "ninah/inventory.hpp"

#include <algorithm>
#include <cstring>
#include <stdexcept>

namespace ninah {
namespace {
constexpr Consumable all_items[] = {
    Consumable::Bobeer, Consumable::Cigarette, Consumable::Coffee,
    Consumable::Enerjeka, Consumable::Pills, Consumable::Mushroom,
    Consumable::CatFood, Consumable::Povistka, Consumable::Kombucha,
    Consumable::Photo, Consumable::Cockroach,
};
std::int32_t add32(std::int32_t a, std::int32_t b) noexcept {
    const auto bits = static_cast<std::uint32_t>(a) + static_cast<std::uint32_t>(b);
    std::int32_t result;
    std::memcpy(&result, &bits, sizeof(result));
    return result;
}
std::int32_t sub32(std::int32_t a, std::int32_t b) noexcept {
    const auto bits = static_cast<std::uint32_t>(a) - static_cast<std::uint32_t>(b);
    std::int32_t result;
    std::memcpy(&result, &bits, sizeof(result));
    return result;
}
template<class Hook>
void require_hook(const Hook& hook, const char* message) {
    if (!hook) throw std::logic_error(message);
}
bool contains(const std::vector<Consumable>& values, Consumable item) {
    return std::find(values.begin(), values.end(), item) != values.end();
}
} // namespace

InventoryState InventoryState::initial(bool need_load) {
    InventoryState state;
    for (const auto item : all_items) state.storage.emplace(item, 0);
    if (!need_load) {
        state.storage.at(Consumable::Bobeer) = 8;
        state.storage.at(Consumable::Kombucha) = 1;
        state.storage.at(Consumable::Cockroach) = 1;
    }
    return state;
}

Inventory::Inventory(InventoryState& state, InventoryHooks hooks)
    : state_(state), hooks_(std::move(hooks)) {}

std::int32_t Inventory::count(Consumable item) const {
    return state_.storage.at(item);
}

bool Inventory::ever_used_this_run(Consumable item) const {
    return contains(state_.ever_used, item);
}

void Inventory::add(Consumable item, std::int32_t amount, bool show_hint) {
    auto& current = state_.storage.at(item);
    current = add32(current, amount);
    if (hooks_.updated_count) hooks_.updated_count(item, current);
    if (show_hint && hooks_.received_with_hint)
        hooks_.received_with_hint(item, amount);
}

bool Inventory::try_remove(Consumable item, std::int32_t amount, bool show_hint) {
    auto& current = state_.storage.at(item);
    if (current < amount) return false;

    current = sub32(current, amount);
    if (hooks_.updated_count) hooks_.updated_count(item, current);
    if (show_hint && hooks_.given_away_with_hint)
        hooks_.given_away_with_hint(item, amount);

    require_hook(hooks_.meta_ever_used, "meta EverUsedConsumable hook is required on successful remove");
    if (!hooks_.meta_ever_used(item)) {
        require_hook(hooks_.meta_use_consumable, "meta UseConsumable hook is required when not ever-used");
        hooks_.meta_use_consumable(item);
    }

    if (!contains(state_.ever_used, item)) state_.ever_used.push_back(item);
    state_.today_used.push_back(item);

    if (contains(state_.today_used, Consumable::Cigarette)
        && contains(state_.today_used, Consumable::Coffee)) {
        require_hook(hooks_.unlock_achievement, "achievement hook is required on coffee+cigarette branch");
        hooks_.unlock_achievement("CONSUM_COFFEE_CIG");
    }
    if (item == Consumable::Povistka)
        state_.povistkas_used = add32(state_.povistkas_used, 1);
    return true;
}

bool Inventory::try_give_item(Consumable item, std::int32_t amount, std::int32_t recipient) {
    if (!try_remove(item, amount, true)) return false;
    if (item == Consumable::Povistka) {
        require_hook(hooks_.give_povistka, "CharactersManager.GivePovistka hook is required for Povistka");
        hooks_.give_povistka(recipient);
        if (hooks_.given_povistka) hooks_.given_povistka(recipient);
    }
    if (item == Consumable::CatFood && hooks_.fed_cat) hooks_.fed_cat();
    return true;
}

} // namespace ninah
