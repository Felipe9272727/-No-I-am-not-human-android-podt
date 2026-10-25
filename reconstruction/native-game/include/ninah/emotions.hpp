#pragma once
#include <cstdint>
#include <optional>
#include <string>
#include <vector>
namespace ninah {
enum class AnimationCycling:std::int32_t {PlayOnce=0,Cycle=1,FixLastFrame=2};
struct SpriteRef {std::string source_file;std::int32_t file_id;std::int64_t path_id;};
struct AnimationSpec {AnimationCycling cycling;std::vector<SpriteRef> frames;std::int32_t frames_per_second;bool frames_missing;};
struct EmotionEntry {std::int32_t character_id,emotion;std::string name;AnimationSpec animation;};
class EmotionCatalog {
public:
 explicit EmotionCatalog(std::vector<EmotionEntry>);
 AnimationSpec get(std::int32_t character,std::int32_t emotion)const;
 std::optional<std::int32_t> find_name(const std::string&)const;
 const std::vector<EmotionEntry>& entries()const noexcept{return entries_;}
private:std::vector<EmotionEntry> entries_;
};
struct Vector3 {float x,y,z;};
struct DialogTransform {Vector3 position,scale;};
DialogTransform emotion_transform(float,float,float,std::optional<DialogTransform>);
}
