#include "ninah/occupants.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <stdexcept>
#include <utility>

namespace ninah {
namespace {
std::int32_t add32(std::int32_t a, std::int32_t b) noexcept {
    const auto bits = static_cast<std::uint32_t>(a) + static_cast<std::uint32_t>(b);
    std::int32_t result;
    std::memcpy(&result, &bits, sizeof(result));
    return result;
}
void erase_first(std::vector<std::int32_t>& values, std::int32_t value) {
    const auto it = std::find(values.begin(), values.end(), value);
    if (it != values.end()) values.erase(it);
}
template<class Hook>
void require_hook(const Hook& hook, const char* message) {
    if (!hook) throw std::logic_error(message);
}
void add_dictionary_value(std::unordered_map<std::int32_t, float>& values,
                          std::int32_t key, float value, const char* error) {
    if (!values.emplace(key, value).second) throw std::invalid_argument(error);
}
} // namespace

OccupantsRuntime::OccupantsRuntime(CharacterCatalog& catalog, OccupantsState& state,
                                   OccupantsHooks hooks, float chance)
    : catalog_(catalog), state_(state), hooks_(std::move(hooks)), screamer_chance_(chance) {}

void OccupantsRuntime::refuse(std::int32_t type) {
    (void)catalog_.at(type);
    state_.refused.push_back(type);
}

void OccupantsRuntime::kill_tomorrow(std::int32_t type) {
    (void)catalog_.at(type);
    state_.self_kill_next_day.push_back(type);
}

void OccupantsRuntime::exile_after_tomorrow(
    std::int32_t type, const std::function<std::int32_t()>& current_day) {
    (void)catalog_.at(type);
    if (!current_day) throw std::logic_error("GetBaseDayNightData callback is required");
    const auto target_day = add32(current_day(), 2);
    state_.exiles_on_days[target_day].push_back(type);
}

void OccupantsRuntime::kill(std::int32_t type, bool is_by_player) {
    const auto& character = catalog_.at(type);
    require_hook(hooks_.room_kill_character, "GetRoom/ARoom kill hook is required");
    require_hook(hooks_.unity_random_value, "Unity Random.value hook is required");
    require_hook(hooks_.record_kill_effects, "kill data-model/meta hook is required");
    if (is_by_player)
        require_hook(hooks_.unlock_achievement, "SteamAchievements hook is required for player kills");

    // Native order: manager state, room kill, imposter scream probe, external
    // data-model/meta writes, CharacterRemoved, then player-kill achievement.
    erase_first(state_.characters.inside, type);
    state_.fema_rating.erase(type);
    erase_first(state_.characters.with_povistka, type);
    state_.killed.push_back(type);
    if (is_by_player) {
        if (!character.is_imposter) state_.innocents_killed_by_player.push_back(type);
    } else {
        state_.killed_by_imposters.push_back(type);
    }
    state_.killed_today.push_back(type);

    (void)hooks_.room_kill_character(type);
    if (character.is_imposter) {
        const float roll = hooks_.unity_random_value();
        if (roll < screamer_chance_ && hooks_.screamer_showed)
            hooks_.screamer_showed(type);
    }
    hooks_.record_kill_effects(type, is_by_player, character.is_imposter);
    if (hooks_.character_removed) hooks_.character_removed(type);
    if (is_by_player)
        hooks_.unlock_achievement(character.is_imposter ? "KILL_IMPOSTER" : "KILL_HUMAN");
}

void OccupantsRuntime::exile(std::int32_t type) {
    const auto& character = catalog_.at(type);
    require_hook(hooks_.room_exile_character, "GetRoom/ARoom exile hook is required");
    if (state_.characters.alive_inside(type)) erase_first(state_.characters.inside, type);
    state_.fema_rating.erase(type);
    state_.exiled.push_back(type);
    erase_first(state_.characters.with_povistka, type);
    if (hooks_.room_exile_character(type) && hooks_.character_removed)
        hooks_.character_removed(character.type);
}

void OccupantsRuntime::begin_new_day(std::int32_t day, float increment) {
    // Native order: inside FEMA updates, scheduled exile actions, clear today's
    // kill list, and finally the day-seven achievement check.
    for (const auto type : state_.characters.inside) {
        const auto it = state_.fema_rating.find(type);
        if (it == state_.fema_rating.end())
            throw std::out_of_range("FEMARating has no entry for inside character");
        it->second += increment;
    }
    const auto scheduled = state_.exiles_on_days.find(day);
    if (scheduled != state_.exiles_on_days.end()) {
        const auto snapshot = scheduled->second;
        for (const auto type : snapshot) exile(type);
    }
    state_.killed_today.clear();
    if (day == 7 && state_.killed_by_imposters.empty()) {
        require_hook(hooks_.unlock_achievement, "SteamAchievements hook is required on this branch");
        hooks_.unlock_achievement("WEEK1_IMPOSTERS_DOESNT_KILL");
    }
}

LetInResult OccupantsRuntime::let_in(std::int32_t type, bool exile_old_from_place,
                                     float is_human_fema_rating, float character_fema_bonus,
                                     float min_percent, float max_percent,
                                     const std::function<std::int32_t()>& current_day) {
    const auto& incoming = catalog_.at(type);
    require_hook(hooks_.room_add_character, "GetRoom/ARoom add hook is required");
    if (type == 19) require_hook(hooks_.generate_baby_events, "IGameEventsManager.GenerateBabyEvents hook is required for type 19");
    if (type == 51) require_hook(hooks_.record_special_new_arrival, "type-51 data-model/meta hook is required");

    // FirstOrDefault over CharactersInside, with the original enum-zero sentinel.
    std::int32_t occupant = 0;
    for (const auto inside_type : state_.characters.inside) {
        if (catalog_.at(inside_type).place == incoming.place) { occupant = inside_type; break; }
    }
    if (occupant != 0 && occupant != type) {
        if (exile_old_from_place) {
            exile(occupant);
        } else {
            // Native performs a second Select(inside -> place).Contains(place)
            // before its Debug.LogError early return.
            const bool place_still_taken = std::any_of(
                state_.characters.inside.begin(), state_.characters.inside.end(),
                [&](std::int32_t id) { return catalog_.at(id).place == incoming.place; });
            if (place_still_taken) return LetInResult::PlaceAlreadyTaken;
        }
    }

    state_.characters.inside.push_back(type);
    const std::int32_t day = current_day ? current_day() : 0;
    for (const auto& [existing_type, ignored_day] : state_.came_in_days) {
        (void)ignored_day;
        if (existing_type == type) throw std::invalid_argument("CharactersCameInDays.Add duplicate key");
    }
    state_.came_in_days.emplace_back(type, day);

    if (state_.fema_rating.find(type) == state_.fema_rating.end()) {
        const float base = incoming.is_imposter ? 0.0f : is_human_fema_rating;
        add_dictionary_value(state_.fema_rating, type, base + character_fema_bonus,
                             "FEMARating.Add duplicate key");
    }

    (void)hooks_.room_add_character(incoming.room, type, false);
    if (type == 19) hooks_.generate_baby_events(day);

    // GenerateStatus runs after the new occupant is already inside, so the
    // ratio includes this CharacterSOData's current status during the count.
    if (incoming.randomly_generated_status) {
        std::int32_t imposter_count = 0;
        for (const auto id : state_.characters.inside)
            if (catalog_.at(id).is_imposter) ++imposter_count;
        const auto total = static_cast<std::int32_t>(state_.characters.inside.size());
        const float ratio = static_cast<float>(imposter_count) / static_cast<float>(total);
        bool is_imposter;
        if (min_percent > ratio) {
            is_imposter = false;
        } else if (ratio > max_percent) {
            is_imposter = true;
        } else {
            require_hook(hooks_.unity_random_range, "Unity Random.Range(int,int) hook is required for generated status");
            is_imposter = hooks_.unity_random_range(0, 2) == 0;
        }
        catalog_.set_imposter(type, is_imposter);
    }

    const bool status = catalog_.at(type).is_imposter;
    if (!state_.are_imposters.emplace(type, status).second)
        throw std::invalid_argument("AreCharactersImposters.Add duplicate key");
    if (type == 51) hooks_.record_special_new_arrival(type);
    if (hooks_.character_added) hooks_.character_added(type, false);
    return LetInResult::Added;
}

std::vector<std::int32_t> OccupantsRuntime::possible_characters_to_kill(
    std::int32_t current_day) const {
    std::vector<std::int32_t> result;
    for (const auto& [type, arrival_day] : state_.came_in_days) {
        if (!state_.characters.alive_inside(type)) continue;
        if (add32(arrival_day, 1) >= current_day) continue; // signed strict native compare
        if (!catalog_.at(type).is_imposter) result.push_back(type);
    }
    return result;
}

} // namespace ninah
