#include "ninah/arrivals.hpp"
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace ninah;
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }

GameEvent event(const std::string& name, std::int32_t day, float delay = 3.0f, bool repeat = false) {
    return GameEvent(EventConditions{name, {day}, TimeOfDay::Night, delay, {}, repeat});
}

void stable_order_and_ties() {
    VisitorScheduler scheduler;
    scheduler.stage(8, 20, event("late", 4));
    scheduler.stage(7, 10, event("first", 4));
    scheduler.stage(6, 10, event("tie", 4));
    const auto& visits = scheduler.visits();
    require(visits.size() == 3, "all staged visits retained");
    // Sorting/preparation occurs on first update.
    std::vector<std::int32_t> order;
    std::unordered_set<std::string> completed;
    scheduler.subscribe_arrival([&](StagedVisit& v) {
        order.push_back(v.character_id);
        completed.insert(v.event.conditions().name);
    });
    scheduler.update(4, TimeOfDay::Night, 103.0f, 100.0f, completed);
    require(order == std::vector<std::int32_t>{7, 6, 8}, "sort by order and preserve stable ties");
}

void preflight_is_one_second_early_and_non_consuming() {
    VisitorScheduler scheduler;
    scheduler.stage(3, 0, event("arrival", 2));
    std::vector<std::string> callbacks;
    scheduler.subscribe_soon([&](StagedVisit&) { callbacks.push_back("soon"); });
    scheduler.subscribe_arrival([&](StagedVisit&) { callbacks.push_back("arrival"); });
    std::unordered_set<std::string> completed;
    scheduler.update(2, TimeOfDay::Night, 102.0f, 100.0f, completed);
    require(callbacks == std::vector<std::string>{"soon"}, "last-change minus one warns one second early");
    scheduler.update(2, TimeOfDay::Night, 103.0f, 100.0f, completed);
    require(callbacks == std::vector<std::string>{"soon", "arrival"}, "real check still succeeds at delay");
}

void only_completed_names_unlock_prior_visits() {
    VisitorScheduler scheduler;
    scheduler.stage(1, 0, event("prior", 5));
    scheduler.stage(2, 1, event("next", 5));
    std::vector<std::string> arrived;
    scheduler.subscribe_arrival([&](StagedVisit& visit) { arrived.push_back(visit.event.conditions().name); });
    std::unordered_set<std::string> completed;
    scheduler.update(5, TimeOfDay::Night, 103.0f, 100.0f, completed);
    require(arrived == std::vector<std::string>{"prior"}, "triggered prior event is not completion");
    completed.insert("prior");
    scheduler.update(5, TimeOfDay::Night, 104.0f, 100.0f, completed);
    require(arrived == std::vector<std::string>{"prior", "next"}, "completion name unlocks chained visit");
}

void single_day_batch_guard() {
    VisitorScheduler scheduler;
    scheduler.stage(1, 0, event("day_one", 1));
    bool rejected = false;
    try { scheduler.stage(2, 1, event("day_two", 2)); }
    catch (const std::invalid_argument&) { rejected = true; }
    require(rejected, "cannot chain dependencies across day batches");

    VisitorScheduler multiple_days;
    rejected = false;
    try { multiple_days.stage(1, 0, GameEvent(EventConditions{"many", {1, 2}, TimeOfDay::Night, 0, {}, false})); }
    catch (const std::invalid_argument&) { rejected = true; }
    require(rejected, "each staged condition needs exactly one explicit day");
}

int main() {
    stable_order_and_ties();
    preflight_is_one_second_early_and_non_consuming();
    only_completed_names_unlock_prior_visits();
    single_day_batch_guard();
    std::cout << "4 arrival-scheduler regression groups passed\n";
}
