#pragma once

#include "ninah/core.hpp"

namespace ninah {

struct CharacterCountsSnapshot { std::int32_t imposters, possible_kill_targets, innocents; };

struct ProgressionState {
    EnergyState energy;
    TimeOfDay time_of_day = TimeOfDay::Day;
    float last_change = 0.0f;
    float accumulated_time = 0.0f;
    bool can_leave_rooms = true;
    bool imposters_killing_blocked = false;
    bool was_somebody_murdered = false;
    bool bodyeater_ready = false;
    bool repair_after_bodyeater = false;
    std::int32_t last_courier_ordered_day = -1;
    std::vector<std::int32_t> coffee_days;
};

struct ProgressionConfig { DayConfig day_config; std::int32_t coffee_boost_days; std::int32_t last_day; };
enum class TransitionResult { blocked_by_room, goal_incomplete, started };

struct ProgressionHost {
    std::function<bool(std::int32_t)> all_night_ding_dongs_complete;
    std::function<void()> vibrate_before_bed, went_to_bed, update_talks_count;
    std::function<void(TimeOfDay)> start_visual_transition;
    std::function<float()> current_time;
    std::function<void()> run_morning_of_suicides, poses_changed, clear_change_poses_tomorrow;
    std::function<std::optional<CharacterCountsSnapshot>()> character_counts;
    std::function<void(std::int32_t)> day_changed;
    std::function<void()> events_begin_new_day, refresh_dialog_sign_checks, consumables_begin_new_day;
    std::function<void(std::int32_t)> characters_begin_new_day;
    std::function<void(std::int32_t)> initialize_all_window_images;
    std::function<void()> renew_all_window_dialogs, kill_everyone, bodyeater_appeared;
    std::function<void(std::int32_t)> disable_super_for_day, generate_night_ding_dongs;
    std::function<void(std::int32_t)> generate_character_ding_dongs;
    std::function<void()> select_music, update_selected_time_visuals;
};

bool is_ending_day(const ProgressionState&, const ProgressionConfig&) noexcept;
TransitionResult request_daynight_change(ProgressionState&, const ProgressionHost&);
void initialize_new_day(ProgressionState&, const ProgressionConfig&, const ProgressionHost&, bool from_save_data = false);
void initialize_new_night(ProgressionState&, const ProgressionHost&, bool from_save_data = false);
void restore_daynight_from_save(ProgressionState&, const ProgressionConfig&, const ProgressionHost&);

} // namespace ninah
