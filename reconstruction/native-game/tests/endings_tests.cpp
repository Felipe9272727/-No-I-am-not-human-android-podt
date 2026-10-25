#include "ninah/endings.hpp"
#include <cassert>
#include <stdexcept>
using namespace ninah;
int main() {
    EndingSnapshot s;
    auto r=select_gameplay_ending(s);
    assert(!r.ending && r.evaluated.size()==10);
    s.death_ready=true; s.innocents_kills=4;
    r=select_gameplay_ending(s); assert(r.ending==Ending::Death);
    s.death_ready=false; s.innocents_kills=0; s.bathroom_baby=s.bedroom_baby=s.office_baby=s.is_night=true;
    s.vigilante_revealed=true;
    r=select_gameplay_ending(s); assert(r.ending==Ending::Baby);
    assert(r.evaluated.front()==Ending::Basement && r.evaluated.back()==Ending::Rage);
    s={}; s.is_ending_day=true; s.characters_inside=1;
    r=select_gameplay_ending(s); assert(r.ending==Ending::Basement);
    s.characters_inside=0; r=select_gameplay_ending(s); assert(r.ending==Ending::BasementAlone);
    s={}; s.povistkas_used=1; s.fema_calls=3; assert(!select_gameplay_ending(s).ending);
    s.povistkas_used=2; assert(select_gameplay_ending(s).ending==Ending::Fema);
    s.ever_rude_to_fema=true; assert(!select_gameplay_ending(s).ending);
    s={}; s.innocents_kills=3; assert(!select_gameplay_ending(s).ending);
    s.innocents_kills=4; assert(select_gameplay_ending(s).ending==Ending::Killer);
    s={}; s.watched_mushroom_clock=true; s.mushroom_cartoon_unlocked=true;
    assert(select_gameplay_ending(s).ending==Ending::Mushroom);
    s={}; s.cultists_begun=true; assert(select_gameplay_ending(s).ending==Ending::Cult);
    s={}; s.is_ending_day=true; s.imposters=2; s.characters_inside=3;
    assert(select_gameplay_ending(s).ending==Ending::BasementWithThem);
    assert(death_dialog_condition({},0));
    assert(death_dialog_condition({false,true,false},2));
    assert(cult_dialog_condition(true,0) && !cult_dialog_condition(false,1) && cult_dialog_condition(false,2));
    assert(mushroom_dialog_condition(true,true,0) && !mushroom_dialog_condition(false,true,2));
    bool threw=false; try { (void)cult_dialog_condition(false,3); } catch(const std::out_of_range&) {threw=true;} assert(threw);
}
