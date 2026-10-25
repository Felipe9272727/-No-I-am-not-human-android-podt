#pragma once
#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>
namespace ninah {
enum class TimeOfDay : std::int32_t { Day=0, Night=1 };
struct EventConditions {
    std::string name;
    std::vector<std::int32_t> days;
    TimeOfDay time_of_day;
    float delay_seconds;
    std::vector<std::string> necessary_events;
    bool can_repeat;
};
class GameEvent {
public:
    explicit GameEvent(EventConditions conditions);
    bool check(std::int32_t day, TimeOfDay time, float now, float last_change,
               const std::unordered_set<std::string>& completed, bool is_fake=false);
    void reset() noexcept { triggered_=false; }
    void complete() noexcept { completed_=true; }
    bool triggered() const noexcept { return triggered_; }
    bool completed() const noexcept { return completed_; }
    const EventConditions& conditions() const noexcept { return conditions_; }
    void set_necessary_events(std::vector<std::string> names) { conditions_.necessary_events=std::move(names); }
private:
    EventConditions conditions_;
    bool triggered_=false, completed_=false;
};
struct DayConfig { std::vector<std::int32_t> max_actions_by_day; };
struct EnergyState {
    std::int32_t day=0, remaining=0, extra_slots=0;
    std::unordered_map<std::int32_t,std::int32_t> fines_by_day;
    std::int32_t maximum(const DayConfig&) const;
    void act() noexcept;
    void act_all() noexcept { remaining=0; }
    void add(const DayConfig&);
    void refill(const DayConfig&);
    void fine_tomorrow(std::int32_t);
};
struct ButtonState {
    std::int32_t active_count=0;
    bool active() const noexcept { return active_count>=1; }
    void set_active(bool) noexcept;
    bool accepts_alpha(float) const noexcept;
};
struct Point { float x,y; };
struct Rect { float x,y,width,height; };
class Viewport {
public:
    Viewport(float scene_width,float scene_height,Rect safe);
    std::optional<Point> to_scene(Point screen) const noexcept;
    Rect bounds() const noexcept { return bounds_; }
private:
    Rect bounds_;
    float scale_;
};
class TouchController {
public:
    using Target=std::int32_t;
    using HitTest=std::function<std::optional<Target>(Point)>;
    TouchController(Viewport viewport,HitTest hit_test);
    void down(std::int32_t,Point);
    void move(std::int32_t,Point);
    std::optional<Target> up(std::int32_t,Point);
    void cancel() noexcept;
    std::optional<Target> pressed_target() const noexcept { return target_; }
private:
    std::optional<Target> hit(Point) const;
    Viewport viewport_;
    HitTest hit_test_;
    std::optional<std::int32_t> pointer_;
    std::optional<Target> target_;
};
}
