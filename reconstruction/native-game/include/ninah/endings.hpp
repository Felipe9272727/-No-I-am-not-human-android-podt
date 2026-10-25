#pragma once

#include <cstdint>
#include <optional>
#include <vector>

namespace ninah {
enum class Ending : std::int32_t { Basement=1, BasementWithThem=2, Super=3, Baby=4, Death=5, Cult=6, Killer=7, Fema=8, Mushroom=9, Rage=11, BasementAlone=12 };
struct EndingThresholds { std::int32_t kills_count=4, povistkas_used_count=2, fema_calls_count=3; };
struct EndingSnapshot {
    bool is_ending_day=false;
    std::int32_t imposters=0, characters_inside=0;
    bool bathroom_baby=false, bedroom_baby=false, office_baby=false, is_night=false;
    std::int32_t innocents_kills=0;
    bool watched_mushroom_clock=false, mushroom_cartoon_unlocked=false;
    bool cultists_begun=false, death_ready=false;
    bool ever_rude_to_fema=false;
    std::int32_t povistkas_used=0, fema_calls=0;
    bool vigilante_revealed=false;
};
struct EndingSelection { std::optional<Ending> ending; std::vector<Ending> evaluated; };

EndingSelection select_gameplay_ending(const EndingSnapshot&, const EndingThresholds& = {});
bool death_dialog_condition(const std::vector<bool>& prophet_conditions, std::int32_t visit_index);
bool cult_dialog_condition(bool saved_cultists, std::int32_t visit_index);
bool mushroom_dialog_condition(bool hatch_opened, bool watched_clock, std::int32_t visit_index);
} // namespace ninah
