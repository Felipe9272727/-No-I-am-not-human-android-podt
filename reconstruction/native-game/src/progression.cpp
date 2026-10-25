#include "ninah/progression.hpp"

#include <algorithm>
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace ninah {
namespace {
std::int32_t wrap_i32(std::int64_t value) noexcept {
    constexpr std::int64_t mod = std::int64_t{1} << 32;
    value %= mod;
    if (value < 0) value += mod;
    if (value > std::numeric_limits<std::int32_t>::max()) value -= mod;
    return static_cast<std::int32_t>(value);
}
void require(bool ok, const char* message) { if (!ok) throw std::logic_error(message); }
}

bool is_ending_day(const ProgressionState& s, const ProgressionConfig& c) noexcept { return s.energy.day == c.last_day; }

TransitionResult request_daynight_change(ProgressionState& s, const ProgressionHost& h) {
    if (!s.can_leave_rooms) return TransitionResult::blocked_by_room;
    TimeOfDay next;
    switch (s.time_of_day) {
    case TimeOfDay::Day: if (s.energy.remaining > 0) return TransitionResult::goal_incomplete; next = TimeOfDay::Night; break;
    case TimeOfDay::Night:
        require(static_cast<bool>(h.all_night_ding_dongs_complete), "night-goal provider is required");
        if (!h.all_night_ding_dongs_complete(s.energy.day)) return TransitionResult::goal_incomplete;
        next = TimeOfDay::Day; break;
    default: throw std::logic_error("unsupported TimeOfDay value");
    }
    require(h.start_visual_transition && h.current_time && h.update_talks_count, "transition host callbacks are required");
    if (h.vibrate_before_bed) h.vibrate_before_bed();
    if (h.went_to_bed) h.went_to_bed();
    s.time_of_day = next;
    h.update_talks_count();
    h.start_visual_transition(next);
    s.last_change = h.current_time() + s.accumulated_time;
    return TransitionResult::started;
}

void initialize_new_day(ProgressionState& s, const ProgressionConfig& c, const ProgressionHost& h, bool from_save) {
    if (from_save) return;
    require(h.run_morning_of_suicides && h.events_begin_new_day && h.characters_begin_new_day &&
        h.refresh_dialog_sign_checks && h.consumables_begin_new_day && h.character_counts && h.clear_change_poses_tomorrow,
        "new-day manager callbacks are required");
    const auto day = wrap_i32(static_cast<std::int64_t>(s.energy.day) + 1);
    if (day < 0 || static_cast<std::size_t>(day) >= c.day_config.max_actions_by_day.size()) throw std::out_of_range("recovered day configuration has no such index");
    s.time_of_day = TimeOfDay::Day; s.energy.day = day;
    h.run_morning_of_suicides();
    if (h.poses_changed) h.poses_changed();
    h.clear_change_poses_tomorrow();
    const auto counts = h.character_counts();
    require(counts.has_value(), "new-day character counts are unavailable");
    if (counts->imposters > 1 && counts->possible_kill_targets > 0 && counts->innocents > 0 && !s.imposters_killing_blocked) s.was_somebody_murdered = true;
    s.imposters_killing_blocked = false;
    std::optional<std::int32_t> last_matured;
    for (const auto scheduled : s.coffee_days) {
        if (s.energy.day >= wrap_i32(static_cast<std::int64_t>(scheduled) + c.coffee_boost_days)) {
            s.energy.extra_slots = wrap_i32(static_cast<std::int64_t>(s.energy.extra_slots) - 1);
            last_matured = scheduled;
        }
    }
    if (last_matured) { const auto it = std::find(s.coffee_days.begin(), s.coffee_days.end(), *last_matured); if (it != s.coffee_days.end()) s.coffee_days.erase(it); }
    s.energy.remaining = s.energy.maximum(c.day_config);
    if (h.day_changed) h.day_changed(s.energy.day);
    h.events_begin_new_day(); h.characters_begin_new_day(s.energy.day); h.refresh_dialog_sign_checks(); h.consumables_begin_new_day();
}

void initialize_new_night(ProgressionState& s, const ProgressionHost& h, bool from_save) {
    require(h.initialize_all_window_images && h.renew_all_window_dialogs && h.disable_super_for_day && h.generate_night_ding_dongs, "new-night manager callbacks are required");
    if (!from_save && s.bodyeater_ready) require(static_cast<bool>(h.kill_everyone), "body-eater kill callback is required");
    h.initialize_all_window_images(s.energy.day); h.renew_all_window_dialogs();
    if (!from_save && s.bodyeater_ready) { s.bodyeater_ready = false; s.repair_after_bodyeater = true; h.kill_everyone(); if (h.bodyeater_appeared) h.bodyeater_appeared(); }
    h.disable_super_for_day(s.energy.day); h.generate_night_ding_dongs(s.energy.day);
}

void restore_daynight_from_save(ProgressionState& s, const ProgressionConfig& c, const ProgressionHost& h) {
    require(h.select_music && h.update_selected_time_visuals, "save-restore music/visual callbacks are required");
    if (s.time_of_day == TimeOfDay::Night) require(h.initialize_all_window_images && h.renew_all_window_dialogs && h.disable_super_for_day && h.generate_night_ding_dongs, "save-restore night callbacks are required");
    else if (s.time_of_day != TimeOfDay::Day) throw std::logic_error("unsupported TimeOfDay value during save restore");
    if (s.last_courier_ordered_day == s.energy.day && s.time_of_day == TimeOfDay::Day) require(static_cast<bool>(h.generate_character_ding_dongs), "same-day courier callback is required");
    h.select_music(); h.update_selected_time_visuals();
    if (s.time_of_day == TimeOfDay::Night) initialize_new_night(s, h, true); else initialize_new_day(s, c, h, true);
    if (s.last_courier_ordered_day == s.energy.day && s.time_of_day == TimeOfDay::Day) h.generate_character_ding_dongs(s.energy.day);
    if (s.repair_after_bodyeater && h.bodyeater_appeared) h.bodyeater_appeared();
}
} // namespace ninah
