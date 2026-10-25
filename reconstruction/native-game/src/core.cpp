#include "ninah/core.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <stdexcept>
namespace ninah {
namespace {
std::int32_t bits(std::uint32_t v) noexcept { std::int32_t r;std::memcpy(&r,&v,4);return r; }
std::int32_t add32(std::int32_t a,std::int32_t b) noexcept { return bits(static_cast<std::uint32_t>(a)+static_cast<std::uint32_t>(b)); }
std::int32_t sub32(std::int32_t a,std::int32_t b) noexcept { return bits(static_cast<std::uint32_t>(a)-static_cast<std::uint32_t>(b)); }
}
GameEvent::GameEvent(EventConditions c):conditions_(std::move(c)){}
bool GameEvent::check(std::int32_t day,TimeOfDay time,float now,float last_change,
 const std::unordered_set<std::string>& completed,bool fake) {
    // Original RVA 0x66FB00: completed-name hit marks IsTriggered even in probe mode.
    if(completed.count(conditions_.name)){triggered_=true;return false;}
    if(triggered_&&!conditions_.can_repeat)return false;
    if(completed_)return false;
    if(std::find(conditions_.days.begin(),conditions_.days.end(),day)==conditions_.days.end())return false;
    if(conditions_.time_of_day!=time)return false;
    if(conditions_.delay_seconds>now-last_change)return false;
    for(const auto& n:conditions_.necessary_events)if(!completed.count(n))return false;
    if(!fake)triggered_=true;
    return true;
}
std::int32_t EnergyState::maximum(const DayConfig& c)const{
    if(day<0||static_cast<std::size_t>(day)>=c.max_actions_by_day.size())throw std::out_of_range("day not present in production configuration");
    const auto f=fines_by_day.find(day);
    return add32(sub32(c.max_actions_by_day[day],f==fines_by_day.end()?0:f->second),extra_slots);
}
void EnergyState::act()noexcept{remaining=sub32(remaining,1);}
void EnergyState::add(const DayConfig& c){if(remaining<maximum(c))remaining=add32(remaining,1);}
void EnergyState::refill(const DayConfig& c){remaining=maximum(c);}
void EnergyState::fine_tomorrow(std::int32_t n){auto& f=fines_by_day[add32(day,1)];f=add32(f,n);}
void ButtonState::set_active(bool v)noexcept{active_count=add32(active_count,v?1:-1);}
bool ButtonState::accepts_alpha(float a)const noexcept{return active()&&a>0.1f;}
Viewport::Viewport(float w,float h,Rect s){
    if(!std::isfinite(w)||!std::isfinite(h)||w<=0||h<=0||!std::isfinite(s.x)||!std::isfinite(s.y)||!std::isfinite(s.width)||!std::isfinite(s.height)||s.width<=0||s.height<=0)throw std::invalid_argument("invalid viewport dimensions");
    scale_=std::min(s.width/w,s.height/h);
    bounds_={s.x+(s.width-w*scale_)*0.5f,s.y+(s.height-h*scale_)*0.5f,w*scale_,h*scale_};
}
std::optional<Point> Viewport::to_scene(Point p)const noexcept{
    if(!std::isfinite(p.x)||!std::isfinite(p.y)||p.x<bounds_.x||p.y<bounds_.y||p.x>=bounds_.x+bounds_.width||p.y>=bounds_.y+bounds_.height)return std::nullopt;
    return Point{(p.x-bounds_.x)/scale_,(p.y-bounds_.y)/scale_};
}
TouchController::TouchController(Viewport v,HitTest h):viewport_(std::move(v)),hit_test_(std::move(h)){if(!hit_test_)throw std::invalid_argument("hit test required");}
std::optional<TouchController::Target> TouchController::hit(Point p)const{auto q=viewport_.to_scene(p);return q?hit_test_(*q):std::nullopt;}
void TouchController::down(std::int32_t id,Point p){if(pointer_)return;pointer_=id;target_=hit(p);}
void TouchController::move(std::int32_t id,Point p){if(pointer_&&*pointer_==id&&target_&&hit(p)!=target_)target_.reset();}
std::optional<TouchController::Target> TouchController::up(std::int32_t id,Point p){if(!pointer_||*pointer_!=id)return std::nullopt;auto r=target_&&hit(p)==target_?target_:std::nullopt;cancel();return r;}
void TouchController::cancel()noexcept{pointer_.reset();target_.reset();}
}
