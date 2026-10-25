#pragma once

#include "ninah/core.hpp"
#include <functional>
#include <string>
#include <unordered_set>
#include <vector>

namespace ninah {

struct StagedVisit {
    std::int32_t character_id;
    std::int32_t order;
    GameEvent event;
    bool warned_soon = false;
};

// One invocation of GenerateCharacterDingDongsForDay. A batch is explicitly
// restricted to one configured day; cross-day prerequisite chains are invalid.
class VisitorScheduler {
public:
    using Callback = std::function<void(StagedVisit&)>;
    void stage(std::int32_t character_id, std::int32_t order, GameEvent event);
    void subscribe_soon(Callback callback);
    void subscribe_arrival(Callback callback);
    const std::vector<StagedVisit>& visits() const noexcept { return visits_; }

    // The native preflight calls Check with lastDaytimeChange - 1 and isFake=true;
    // a successful probe is one second early and does not consume the event.
    void update(std::int32_t day, TimeOfDay time, float now,
                float last_daytime_change,
                std::unordered_set<std::string>& completed_events);

private:
    std::optional<std::int32_t> batch_day_;
    bool prepared_ = false;
    std::vector<StagedVisit> visits_;
    std::vector<Callback> soon_subscribers_;
    std::vector<Callback> arrival_subscribers_;
};

} // namespace ninah
