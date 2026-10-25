#include "ninah/rooms.hpp"
#include <algorithm>
#include <cctype>
#include <stdexcept>

namespace ninah {

const std::vector<NarrativeObject>& narrative_objects() {
    static const std::vector<NarrativeObject> data{
        {0, RoomId::Bedroom, "Bedroom_Curtain", "bedroom_window", {-274.0f, 177.0f}},
        {1, RoomId::Bedroom, "Bedroom_Nightstand", "bedroom_nightstand", {190.9f, -108.0f}},
        {2, RoomId::Bathroom, "Bathroom_Window", "bathroom_window", {-14.8f, 464.4f}},
        {3, RoomId::BigRoom, "BigRoom_Cross", "bigroom_cross", {220.5f, 259.5f}},
        {4, RoomId::BigRoom, "BigRoom_Toy", "bigroom_toy", {-305.5f, 187.1f}},
        {5, RoomId::Kitchen, "Kitchen_Cupboards", "kitchen_cupboards", {-309.3f, 381.6f}},
        {6, RoomId::Office, "Office_Pictures", "office_pictures", {-692.9f, 274.1f}},
        {7, RoomId::Office, "Office_Magazine", "office_magazine", {156.5f, -258.2f}},
        {8, RoomId::Pantry, "Pantry_Box", "pantry_box", {203.0f, 228.0f}},
    };
    return data;
}

std::int32_t TalkCounts::get(std::int32_t type) const noexcept {
    auto current = current_.find(type), maximum = max_talk_index_.find(type);
    const auto value = current == current_.end() ? 0 : current->second;
    const auto max_value = maximum == max_talk_index_.end() ? 0 : maximum->second;
    return std::min(std::max(value, 0), max_value);
}
void TalkCounts::add(std::int32_t type) {
    auto [it, inserted] = current_.try_emplace(type, 1);
    if (!inserted) it->second = static_cast<std::int32_t>(static_cast<std::uint32_t>(it->second) + 1U);
}
void TalkCounts::set_max_talks(std::int32_t type, std::int32_t count) {
    max_talk_index_[type] = static_cast<std::int32_t>(static_cast<std::uint32_t>(count) - 1U);
}

RoomRouter::RoomRouter(RoomServices services) : services_(std::move(services)) {
    if (!services_.dialog_is_open || !services_.current_dialog_index || !services_.set_dialog_companion ||
        !services_.run_dialog || !services_.show_subtitle || !services_.add_dialog_ended)
        throw std::invalid_argument("RoomRouter requires all dialog service hooks");
}
void RoomRouter::subscribe(Subscriber subscriber) {
    if (!subscriber) throw std::invalid_argument("empty room subscriber");
    subscribers_.push_back(std::move(subscriber));
}
void RoomRouter::publish(RoomEvent event) { for (const auto& callback : subscribers_) callback(event); }
void RoomRouter::enter(const std::function<void()>& inner) {
    if (!inner) throw std::invalid_argument("EnterInner must be supplied explicitly");
    publish(RoomEvent::Entered);
    inner();
}
void RoomRouter::leave(const std::function<void()>& deactivate) {
    if (!deactivate) throw std::invalid_argument("view deactivation must be supplied explicitly");
    publish(RoomEvent::Left);
    deactivate();
}
CharacterClickResult RoomRouter::click_character(const CharacterClick& click, std::optional<std::int32_t> camera) {
    if (services_.dialog_is_open()) return CharacterClickResult::RejectedDialogOpen;
    if (!click.pose_found) return CharacterClickResult::RejectedPoseMissing;
    if (click.pose_cannot_interact) return CharacterClickResult::RejectedPoseCannotInteract;
    if (click.killed) return CharacterClickResult::KilledByRoomHandler;
    std::string name = click.character_type_name;
    std::transform(name.begin(), name.end(), name.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    services_.set_dialog_companion(click.character_type);
    const auto index = services_.current_dialog_index(click.character_type);
    services_.run_dialog("talk_" + name + "_" + std::to_string(index), camera);
    return CharacterClickResult::DialogStarted;
}
void RoomRouter::click_narrative(const NarrativeObject& object, DialogEnded ended) {
    if (!ended) throw std::invalid_argument("narrative end callback is required");
    services_.show_subtitle(object.node);
    services_.add_dialog_ended(std::move(ended));
}

} // namespace ninah
