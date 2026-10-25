#include "ninah/arrivals.hpp"
#include <algorithm>
#include <stdexcept>

namespace ninah {

void VisitorScheduler::stage(std::int32_t character_id, std::int32_t order, GameEvent event) {
    if (prepared_) throw std::logic_error("cannot stage after visitor batch preparation");
    const auto& conditions = event.conditions();
    if (conditions.days.size() != 1)
        throw std::invalid_argument("visitor conditions must identify exactly one day");
    if (batch_day_ && *batch_day_ != conditions.days.front())
        throw std::invalid_argument("visitor scheduler accepts a single-day batch only");
    batch_day_ = conditions.days.front();
    visits_.push_back({character_id, order, std::move(event), false});
}

void VisitorScheduler::subscribe_soon(Callback callback) {
    if (!callback) throw std::invalid_argument("empty soon subscriber");
    soon_subscribers_.push_back(std::move(callback));
}

void VisitorScheduler::subscribe_arrival(Callback callback) {
    if (!callback) throw std::invalid_argument("empty arrival subscriber");
    arrival_subscribers_.push_back(std::move(callback));
}

void VisitorScheduler::update(std::int32_t day, TimeOfDay time, float now,
                              float last_daytime_change,
                              std::unordered_set<std::string>& completed_events) {
    if (!prepared_) {
        std::stable_sort(visits_.begin(), visits_.end(),
                         [](const StagedVisit& a, const StagedVisit& b) { return a.order < b.order; });
        std::vector<std::string> prior_names;
        for (auto& visit : visits_) {
            auto prerequisites = visit.event.conditions().necessary_events;
            for (const auto& name : prior_names) {
                if (std::find(prerequisites.begin(), prerequisites.end(), name) == prerequisites.end())
                    prerequisites.push_back(name);
            }
            visit.event.set_necessary_events(std::move(prerequisites));
            prior_names.push_back(visit.event.conditions().name);
        }
        prepared_ = true;
    }
    if (batch_day_ && day != *batch_day_) return;

    for (auto& visit : visits_) {
        if (!visit.warned_soon && visit.event.check(day, time, now, last_daytime_change - 1.0f,
                                                   completed_events, true)) {
            visit.warned_soon = true;
            for (const auto& callback : soon_subscribers_) callback(visit);
        }
        if (visit.event.check(day, time, now, last_daytime_change, completed_events)) {
            for (const auto& callback : arrival_subscribers_) callback(visit);
        }
    }
}

} // namespace ninah
