#include "ninah/core.hpp"
#include "production_data.hpp"
#include "production_characters.hpp"
#include "production_emotions.hpp"
#include <cassert>
#include <cmath>
#include <iostream>
int main(){
 auto chars=ninah::production::character_catalog();assert(chars.records().size()==72);
 assert(chars.at(25).name=="Alkonost"&&chars.at(25).place==68&&chars.at(25).is_imposter);
 auto anxiety=chars.at(chars.parse_name("Anxiety",false));assert(anxiety.visits.size()==1&&anxiety.visits[0].day==1&&anxiety.visits[0].guest_number==3);
 auto emotions=ninah::production::emotion_catalog();assert(emotions.entries().size()==275);
 auto cry=emotions.find_name("Alkonost_Cry");assert(cry&&*cry==474078978);
 auto frames=emotions.get(25,*cry);assert(!frames.frames_missing&&frames.frames.size()==1&&frames.cycling==ninah::AnimationCycling::FixLastFrame);
 assert(emotions.get(25,2147483647).frames_missing);
 ninah::EnergyState energy;energy.day=13;energy.refill(ninah::production::day_config());assert(energy.remaining==4);
 energy.fine_tomorrow(3);energy.day=14;energy.extra_slots=1;energy.refill(ninah::production::day_config());assert(energy.remaining==3);
 ninah::ButtonState button;button.set_active(true);button.set_active(true);button.set_active(false);assert(button.active());assert(!button.accepts_alpha(0.1f));
 ninah::TouchController touch(ninah::Viewport(100,100,{10,20,300,200}),[](ninah::Point p)->std::optional<std::int32_t>{return p.x<50?7:8;});
 touch.down(1,{80,80});touch.down(2,{200,80});assert(!touch.up(2,{200,80}));assert(touch.up(1,{80,80})==7);assert(!touch.up(1,{80,80}));
 touch.down(1,{80,80});touch.move(1,{200,80});assert(!touch.up(1,{80,80}));
 std::cout<<"Production characters, emotions, energy and touch passed\n";
}
