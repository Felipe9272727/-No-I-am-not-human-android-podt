#pragma once

#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace ninah {

enum class RoomId : std::int32_t { Kitchen = 0, Office = 1, BigRoom = 2, Bathroom = 3, Pantry = 4, Entrance = 5, Bedroom = 6 };
struct RoomPoint { float x; float y; };
struct NarrativeObject { std::int32_t object_type; RoomId room; const char* name; const char* node; RoomPoint anchored_position; };
const std::vector<NarrativeObject>& narrative_objects();

class TalkCounts {
public:
    std::int32_t get(std::int32_t character_type) const noexcept;
    void add(std::int32_t character_type);
    void set_max_talks(std::int32_t character_type, std::int32_t count);
private:
    std::unordered_map<std::int32_t, std::int32_t> current_;
    std::unordered_map<std::int32_t, std::int32_t> max_talk_index_;
};

struct RoomServices {
    std::function<bool()> dialog_is_open;
    std::function<std::int32_t(std::int32_t)> current_dialog_index;
    std::function<void(std::optional<std::int32_t>)> set_dialog_companion;
    std::function<void(const std::string&, std::optional<std::int32_t>)> run_dialog;
    std::function<void(const std::string&)> show_subtitle;
    std::function<void(std::function<void(bool, bool)>)> add_dialog_ended;
};

struct CharacterClick { std::int32_t character_type; std::string character_type_name; bool pose_found; bool pose_cannot_interact; bool killed; };
enum class CharacterClickResult { RejectedDialogOpen, RejectedPoseMissing, RejectedPoseCannotInteract, KilledByRoomHandler, DialogStarted };
enum class RoomEvent { Entered, Left };

class RoomRouter {
public:
    using Subscriber = std::function<void(RoomEvent)>;
    using DialogEnded = std::function<void(bool, bool)>;
    explicit RoomRouter(RoomServices services);
    void subscribe(Subscriber subscriber);
    void enter(const std::function<void()>& enter_inner);
    void leave(const std::function<void()>& deactivate_view);
    CharacterClickResult click_character(const CharacterClick&, std::optional<std::int32_t> linked_camera);
    void click_narrative(const NarrativeObject&, DialogEnded on_ended);
private:
    void publish(RoomEvent);
    RoomServices services_;
    std::vector<Subscriber> subscribers_;
};

} // namespace ninah
