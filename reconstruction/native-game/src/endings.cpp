#include "ninah/endings.hpp"

#include <array>
#include <stdexcept>

namespace ninah {
EndingSelection select_gameplay_ending(const EndingSnapshot& s, const EndingThresholds& t) {
    struct Candidate { Ending ending; bool met; std::int32_t priority; };
    const std::array<Candidate,10> candidates{{
        {Ending::Basement, s.is_ending_day && s.imposters == 0 && s.characters_inside > 0, 1},
        {Ending::BasementWithThem, s.is_ending_day && s.imposters > 0, 1},
        {Ending::BasementAlone, s.is_ending_day && s.characters_inside == 0, 1},
        {Ending::Baby, s.bathroom_baby && s.bedroom_baby && s.office_baby && s.is_night, 2},
        {Ending::Killer, s.innocents_kills >= t.kills_count, 3},
        {Ending::Mushroom, s.watched_mushroom_clock && s.mushroom_cartoon_unlocked, 1},
        {Ending::Cult, s.cultists_begun, 1},
        {Ending::Death, s.death_ready, 10},
        {Ending::Fema, !s.ever_rude_to_fema && s.povistkas_used >= t.povistkas_used_count && s.fema_calls >= t.fema_calls_count, 1},
        {Ending::Rage, s.vigilante_revealed, 2}
    }};
    EndingSelection result;
    std::int32_t best = 0;
    bool have = false;
    for (const auto& c : candidates) {
        result.evaluated.push_back(c.ending);
        if (c.met && (!have || c.priority > best)) { have=true; best=c.priority; result.ending=c.ending; }
    }
    return result;
}

bool death_dialog_condition(const std::vector<bool>& prophet, std::int32_t index) {
    if (index == 0) return true;
    if (index >= 1 && index <= 3) {
        if (static_cast<std::size_t>(index - 1) >= prophet.size()) throw std::out_of_range("missing prophet condition");
        return prophet[static_cast<std::size_t>(index - 1)];
    }
    throw std::out_of_range("unsupported Death visit index");
}
bool cult_dialog_condition(bool saved, std::int32_t index) {
    if (index == 0 || index == 1) return saved;
    if (index == 2) return true;
    throw std::out_of_range("unsupported Cult visit index");
}
bool mushroom_dialog_condition(bool hatch, bool clock, std::int32_t index) {
    if (index == 0 || index == 1) return hatch && clock;
    if (index == 2) return hatch;
    throw std::out_of_range("unsupported Mushroom visit index");
}
} // namespace ninah
