#include "ninah/progression.hpp"
#include <cassert>
#include <stdexcept>

using namespace ninah;
static ProgressionHost valid_day_host(ProgressionState& s) {
    ProgressionHost h;
    h.run_morning_of_suicides=[]{}; h.clear_change_poses_tomorrow=[]{};
    h.character_counts=[] { return std::optional<CharacterCountsSnapshot>{{0,0,0}}; };
    h.events_begin_new_day=[]{}; h.characters_begin_new_day=[](int){};
    h.refresh_dialog_sign_checks=[]{}; h.consumables_begin_new_day=[]{};
    (void)s; return h;
}
int main() {
    const ProgressionConfig cfg{DayConfig{{3,4,5,6,7}},1,10};
    {
        ProgressionState s; s.energy.day=2; s.energy.remaining=0; s.accumulated_time=3.0f;
        ProgressionHost h; h.current_time=[] {return 12.0f;}; h.update_talks_count=[]{};
        h.start_visual_transition=[](TimeOfDay){};
        assert(request_daynight_change(s,h)==TransitionResult::started);
        assert(s.time_of_day==TimeOfDay::Night && s.last_change==15.0f);
    }
    {
        ProgressionState s; s.energy.day=2; s.energy.extra_slots=1; s.coffee_days={0,3};
        s.energy.fines_by_day[3]=0;
        auto h=valid_day_host(s);
        h.run_morning_of_suicides=[&]{s.energy.extra_slots=5;s.energy.fines_by_day[3]=1;};
        initialize_new_day(s,cfg,h);
        assert(s.energy.extra_slots==4 && s.energy.remaining==9);
        assert((s.coffee_days==std::vector<std::int32_t>{3}));
    }
    {
        ProgressionState s; s.energy.day=2; s.bodyeater_ready=true;
        std::vector<int> calls;
        ProgressionHost h; h.initialize_all_window_images=[&](int){calls.push_back(1);};
        h.renew_all_window_dialogs=[&]{calls.push_back(2);}; h.kill_everyone=[&]{calls.push_back(3);};
        h.disable_super_for_day=[&](int){calls.push_back(4);}; h.generate_night_ding_dongs=[&](int){calls.push_back(5);};
        initialize_new_night(s,h);
        assert(!s.bodyeater_ready && s.repair_after_bodyeater && calls.size()==5);
    }
}
