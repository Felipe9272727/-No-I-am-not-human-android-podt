#pragma once

#include "ninah/characters.hpp"

#include <cstdint>
#include <functional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace ninah {

// Mirrors CharactersManagerSaveData collections. Vectors retain insertion
// order and duplicates, matching List<ECharacterType>.
struct OccupantsState {
    CharactersState characters;
    std::vector<std::int32_t> killed;
    std::vector<std::int32_t> exiled;
    std::vector<std::int32_t> refused;
    std::vector<std::int32_t> self_kill_next_day;
    std::vector<std::int32_t> innocents_killed_by_player;
    std::vector<std::int32_t> killed_by_imposters;
    std::vector<std::int32_t> killed_today;
    std::unordered_map<std::int32_t, float> fema_rating;
    std::vector<std::pair<std::int32_t, std::int32_t>> came_in_days;
    std::unordered_map<std::int32_t, bool> are_imposters;
    std::unordered_map<std::int32_t, std::vector<std::int32_t>> exiles_on_days;
};

enum class LetInResult { Added, PlaceAlreadyTaken };

// External Unity services remain explicit. Room callbacks return true only if
// the room lookup succeeded and the recovered ARoom operation was performed.
struct OccupantsHooks {
    std::function<bool(std::int32_t)> room_kill_character;
    std::function<bool(std::int32_t)> room_exile_character;
    std::function<bool(std::int32_t, std::int32_t, bool)> room_add_character;
    std::function<void(std::int32_t)> character_removed;
    std::function<void(std::int32_t, bool)> character_added;
    std::function<float()> unity_random_value;
    std::function<std::int32_t(std::int32_t, std::int32_t)> unity_random_range;
    std::function<void(std::int32_t)> screamer_showed;
    std::function<void(std::int32_t)> generate_baby_events;
    std::function<void(std::int32_t)> record_special_new_arrival;
    std::function<void(std::int32_t, bool, bool)> record_kill_effects;
    std::function<void(const std::string&)> unlock_achievement;
};

class OccupantsRuntime {
public:
    OccupantsRuntime(CharacterCatalog& catalog, OccupantsState& state,
                     OccupantsHooks hooks, float screamer_on_imposter_chance);

    void refuse(std::int32_t character_type);
    void kill_tomorrow(std::int32_t character_type);
    void exile_after_tomorrow(std::int32_t character_type,
                              const std::function<std::int32_t()>& current_day);
    void kill(std::int32_t character_type, bool is_by_player = false);
    void exile(std::int32_t character_type);
    void begin_new_day(std::int32_t day, float every_day_fema_increment);

    // LetIn inputs are serialized production values, not local defaults.
    // Empty current_day reproduces the recovered delegate-null path (day 0).
    LetInResult let_in(std::int32_t character_type, bool exile_old_from_place,
                       float is_human_fema_rating, float character_fema_bonus,
                       float min_imposters_percent, float max_imposters_percent,
                       const std::function<std::int32_t()>& current_day);

    // Exact recovered candidate predicate/pipeline for night-kill selection.
    std::vector<std::int32_t> possible_characters_to_kill(std::int32_t current_day) const;

private:
    CharacterCatalog& catalog_;
    OccupantsState& state_;
    OccupantsHooks hooks_;
    float screamer_chance_;
};

} // namespace ninah
