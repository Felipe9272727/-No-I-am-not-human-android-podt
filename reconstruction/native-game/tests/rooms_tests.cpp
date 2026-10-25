#include "ninah/rooms.hpp"
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace ninah;
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }

RoomServices hooks(std::vector<std::string>& trace, bool open = false) {
    RoomServices h;
    h.dialog_is_open = [&, open] { trace.push_back("open?"); return open; };
    h.current_dialog_index = [&](std::int32_t) { trace.push_back("index"); return 3; };
    h.set_dialog_companion = [&](std::optional<std::int32_t> id) { require(id == 17, "companion id"); trace.push_back("companion"); };
    h.run_dialog = [&](const std::string& node, std::optional<std::int32_t> camera) { require(node == "talk_doc_3", "talk node"); require(camera == 42, "linked camera"); trace.push_back("run"); };
    h.show_subtitle = [&](const std::string& node) { require(node == "bedroom_window", "serialized subtitle node"); trace.push_back("subtitle"); };
    h.add_dialog_ended = [&](std::function<void(bool, bool)> callback) { require(bool(callback), "ended callback"); trace.push_back("ended+"); };
    return h;
}
void factory_data() {
    const auto& d = narrative_objects();
    require(d.size() == 9 && d[0].object_type == 0 && std::string(d[0].node) == "bedroom_window", "factory entries");
    require(d[0].room == RoomId::Bedroom && d[0].anchored_position.x == -274.0f && d[0].anchored_position.y == 177.0f, "serialized Unity coordinates");
    require(d[8].room == RoomId::Pantry && std::string(d[8].node) == "pantry_box", "last factory entry");
}
void lifecycle_order() {
    std::vector<std::string> trace;
    RoomRouter r(hooks(trace));
    r.subscribe([&](RoomEvent e) { trace.push_back(e == RoomEvent::Entered ? "entered" : "left"); });
    r.enter([&] { trace.push_back("inner"); });
    r.leave([&] { trace.push_back("deactivate"); });
    require(trace == std::vector<std::string>{"entered", "inner", "left", "deactivate"}, "room lifecycle order");
}
void character_gates_and_route() {
    std::vector<std::string> trace;
    RoomRouter r(hooks(trace));
    CharacterClick c{17, "Doc", true, false, false};
    require(r.click_character(c, 42) == CharacterClickResult::DialogStarted, "valid dialog starts");
    require(trace == std::vector<std::string>{"open?", "companion", "index", "run"}, "service call order");
    trace.clear(); c.pose_found = false;
    require(r.click_character(c, 42) == CharacterClickResult::RejectedPoseMissing, "missing pose rejects");
    trace.clear(); c.pose_found = true; c.pose_cannot_interact = true;
    require(r.click_character(c, 42) == CharacterClickResult::RejectedPoseCannotInteract, "CannotInteract rejects");
    trace.clear(); c.pose_cannot_interact = false; c.killed = true;
    require(r.click_character(c, 42) == CharacterClickResult::KilledByRoomHandler, "killed route rejects");
    require(trace == std::vector<std::string>{"open?"}, "blocked route has no service effects");
}
void open_gate_narrative_and_counts() {
    std::vector<std::string> trace;
    RoomRouter open_router(hooks(trace, true));
    require(open_router.click_character({17, "Doc", true, false, false}, 42) == CharacterClickResult::RejectedDialogOpen, "open dialog rejects click");
    require(trace == std::vector<std::string>{"open?"}, "open gate has no side effects");
    trace.clear(); RoomRouter n(hooks(trace));
    n.click_narrative(narrative_objects()[0], [](bool, bool) {});
    require(trace == std::vector<std::string>{"subtitle", "ended+"}, "narrative dispatch and callback order");
    TalkCounts counts;
    require(counts.get(5) == 0, "empty save count starts at index zero");
    counts.add(5); require(counts.get(5) == 0, "absent max clamps to zero");
    counts.set_max_talks(5, 3); require(counts.get(5) == 1, "max talks stores count-1");
    counts.add(5); counts.add(5); require(counts.get(5) == 2, "talk index clamps at stored maximum");
}
int main() { factory_data(); lifecycle_order(); character_gates_and_route(); open_gate_narrative_and_counts(); std::cout << "4 room-routing regression groups passed\n"; }
