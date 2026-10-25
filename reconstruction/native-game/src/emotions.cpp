#include "ninah/emotions.hpp"
#include <utility>
namespace ninah {
EmotionCatalog::EmotionCatalog(std::vector<EmotionEntry> e):entries_(std::move(e)){}
AnimationSpec EmotionCatalog::get(std::int32_t c,std::int32_t e)const{
 for(const auto& r:entries_)if(r.character_id==c&&r.emotion==e)return r.animation;
 return {AnimationCycling::PlayOnce,{},8,true};
}
std::optional<std::int32_t> EmotionCatalog::find_name(const std::string& n)const{for(const auto& e:entries_)if(e.name==n)return e.emotion;return std::nullopt;}
DialogTransform emotion_transform(float x,float y,float s,std::optional<DialogTransform> d){auto delta=d.value_or(DialogTransform{{0,0,0},{0,0,0}});return {{x+delta.position.x,y+delta.position.y,0},{s+delta.scale.x,s+delta.scale.y,s+delta.scale.z}};}
}
