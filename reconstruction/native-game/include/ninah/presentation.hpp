#pragma once
#include <array>
#include <cstdint>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace ninah {
struct PresentationVec2 { float x=0, y=0; };
struct PresentationVec3 { float x=0, y=0, z=0; };
struct PresentationAsset { std::int32_t file_id=0; std::int64_t path_id=0; bool valid=false; };
struct PresentationPose {
 std::int32_t state=0; std::string name; PresentationAsset sprite;
 PresentationVec2 position, scale; bool cannot_interact=false;
};
struct PresentationEmotion { std::int32_t value=0; std::string name; PresentationAsset sprite; };
struct PresentationAnimation { std::int32_t emotion=0; std::string name; std::int32_t cycling=0, frames_per_second=0; std::vector<PresentationAsset> frames; };
struct PresentationOverride { std::int32_t emotion=0; PresentationVec3 position, scale; };
struct PresentationSign {
 PresentationAsset sprite, white, iris;
 std::vector<PresentationAsset> frames;
 std::int32_t cycling=0, frames_per_second=0;
 float distance_multiplier=0, min_move_duration=0, max_move_duration=0;
};
struct CharacterPresentation {
 std::string name, source_file; std::int64_t source_path_id=0; std::int32_t character_type=0;
 std::int32_t room_enum=-1; std::int64_t scene_component_path_id=0, game_object_path_id=0;
 bool authored_active_self=false, authored_active_in_hierarchy=false;
 std::int32_t initial_pose_state=0; bool has_initial_pose=false;
 bool default_imposter=false; float dialog_scale=1, room_scale=1;
 PresentationVec2 dialog_position;
 std::vector<PresentationPose> poses;
 std::vector<PresentationEmotion> emotions;
 std::vector<PresentationAnimation> emotion_animations;
 std::vector<PresentationOverride> emotion_overrides;
 // Index is sign (Eye..Ear) plus 6 for imposter variants.
 std::array<PresentationSign,12> signs{};
};
class PresentationCatalog {
public:
 explicit PresentationCatalog(std::vector<CharacterPresentation> records);
 const CharacterPresentation* find(const std::string& name) const;
 const std::vector<CharacterPresentation>& records() const noexcept { return records_; }
private: std::vector<CharacterPresentation> records_;
};
enum class PresentationResult { Applied, NotFound, InvalidValue, Unsupported };
enum class CharacterSign : std::int32_t { Eye=0, Hands=1, Teeth=2, AuraPhoto=3, Armpit=4, Ear=5 };
struct SignRenderPacket {
 std::string character, source_file; std::int64_t source_path_id=0; CharacterSign sign=CharacterSign::Eye; bool imposter=false;
 PresentationSign assets;
};
struct DialogRenderPacket {
 std::string character, source_file; std::int64_t source_path_id=0;
 std::int32_t character_type=0, emotion=0, cycling=0, frames_per_second=0;
 std::vector<PresentationAsset> frames;
 PresentationVec3 position, scale;
};
struct RoomRenderPacket {
 std::string character, source_file; std::int64_t source_path_id=0;
 std::int32_t character_type=0, room_enum=-1, pose_state=0;
 std::int64_t scene_component_path_id=0, game_object_path_id=0;
 bool authored_active_self=false, authored_active_in_hierarchy=false, cannot_interact=false;
 std::string pose_name; PresentationAsset sprite;
 PresentationVec3 position, scale;
};
struct PoseChange { std::string character; std::int32_t state=0; };
class PresentationState {
public:
 explicit PresentationState(const PresentationCatalog& catalog);
 PresentationResult set_dialog_companion(const std::string& character);
 std::optional<RoomRenderPacket> room_packet(const std::string& character) const;
 PresentationResult set_emotion(const std::string& raw);
 PresentationResult setup_gun(bool shown);
 PresentationResult dont_setup_gun();
 PresentationResult show_sign(const std::string& character, const std::string& raw_sign, bool is_imposter);
 PresentationResult show_player_sign(const std::string& raw_sign);
 PresentationResult stop_showing_sign();
 PresentationResult change_pose(const std::string& character, const std::string& raw_pose);
 PresentationResult change_pose_tomorrow(const std::string& character, const std::string& raw_pose);
 std::vector<PoseChange> apply_tomorrow_poses();
 std::optional<std::int32_t> emotion() const noexcept { return emotion_; }
 std::optional<bool> gun_shown() const noexcept { return gun_shown_; }
 const std::optional<SignRenderPacket>& active_sign() const noexcept { return active_sign_; }
 std::optional<DialogRenderPacket> current_dialog_packet() const;
 const std::vector<PoseChange>& immediate_pose_changes() const noexcept { return immediate_poses_; }
 const std::vector<PoseChange>& tomorrow_pose_changes() const noexcept { return tomorrow_poses_; }
 void clear_pose_changes();
private:
 PresentationResult parse_pose(const std::string&, std::int32_t&) const;
 const PresentationCatalog& catalog_;
 std::string dialog_companion_;
 std::optional<std::int32_t> emotion_; std::optional<bool> gun_shown_;
 std::optional<SignRenderPacket> active_sign_;
 std::vector<PoseChange> immediate_poses_, tomorrow_poses_;
 std::map<std::string,std::int32_t> live_poses_;
};
// Reproduces the recovered dialog transform operation: authored dialog
// position plus override position; uniform DialogScale plus override scale.
PresentationVec3 presentation_position(const CharacterPresentation&, const PresentationOverride*);
PresentationVec3 presentation_scale(const CharacterPresentation&, const PresentationOverride*);
}
