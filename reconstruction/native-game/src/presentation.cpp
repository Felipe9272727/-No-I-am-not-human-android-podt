#include "ninah/presentation.hpp"
#include "presentation_provider.hpp"
#include <algorithm>
#include <cctype>
#include <stdexcept>
#include <utility>

namespace ninah {
namespace {
std::string lower(std::string s) {
 std::transform(s.begin(),s.end(),s.begin(),[](unsigned char c){return static_cast<char>(std::tolower(c));});
 return s;
}
bool parse_integer(const std::string& s, std::int32_t& value) {
 if(s.empty()) return false;
 try { std::size_t n=0; auto v=std::stoll(s,&n,10); if(n!=s.size()||v<INT32_MIN||v>INT32_MAX)return false; value=static_cast<std::int32_t>(v); return true; }
 catch(...) { return false; }
}
std::optional<CharacterSign> sign_value(const std::string& raw) {
 const auto n=lower(raw);
 if(n=="eye"||n=="0")return CharacterSign::Eye;
 if(n=="hands"||n=="1")return CharacterSign::Hands;
 if(n=="teeth"||n=="2")return CharacterSign::Teeth;
 if(n=="auraphoto"||n=="aura_photo"||n=="3")return CharacterSign::AuraPhoto;
 if(n=="armpit"||n=="4")return CharacterSign::Armpit;
 if(n=="ear"||n=="5")return CharacterSign::Ear;
 return std::nullopt;
}
}
PresentationCatalog::PresentationCatalog(std::vector<CharacterPresentation> r):records_(std::move(r)){}
const CharacterPresentation* PresentationCatalog::find(const std::string& n) const {
 for(const auto& r:records_) if(lower(r.name)==lower(n)) return &r;
 return nullptr;
}
PresentationState::PresentationState(const PresentationCatalog& c):catalog_(c) {
 for(const auto& character:catalog_.records())
  if(character.has_initial_pose) live_poses_[character.name]=character.initial_pose_state;
}
PresentationState::Snapshot PresentationState::snapshot() const {
 return {dialog_companion_, emotion_, gun_shown_, active_sign_, immediate_poses_, tomorrow_poses_, live_poses_};
}
void PresentationState::restore(const Snapshot& s) {
 dialog_companion_=s.dialog_companion; emotion_=s.emotion; gun_shown_=s.gun_shown;
 active_sign_=s.active_sign; immediate_poses_=s.immediate_poses; tomorrow_poses_=s.tomorrow_poses; live_poses_=s.live_poses;
}
PresentationResult PresentationState::set_dialog_companion(const std::string& name) {
 const auto* c=catalog_.find(name); if(!c)return PresentationResult::NotFound;
 dialog_companion_=c->name; return PresentationResult::Applied;
}
std::optional<RoomRenderPacket> PresentationState::room_packet(const std::string& name) const {
 const auto* c=catalog_.find(name); if(!c)return std::nullopt;
 const auto live=live_poses_.find(c->name); if(live==live_poses_.end())return std::nullopt;
 const auto pose=std::find_if(c->poses.begin(),c->poses.end(),[&](const auto& p){return p.state==live->second;});
 if(pose==c->poses.end())return std::nullopt;
 return RoomRenderPacket{c->name,c->source_file,c->source_path_id,c->character_type,c->room_enum,pose->state,
  c->scene_component_path_id,c->game_object_path_id,c->authored_active_self,c->authored_active_in_hierarchy,
  pose->cannot_interact,pose->name,pose->sprite,{pose->position.x,pose->position.y,0},{pose->scale.x,pose->scale.y,0}};
}
PresentationResult PresentationState::set_emotion(const std::string& raw) {
 std::int32_t value=0;
 if(!parse_integer(raw,value)) {
  const auto key=lower(raw); bool found=false;
  for(const auto& e:presentation_data::emotion_names()) if(lower(e.first)==key) {value=e.second;found=true;break;}
  if(!found)return PresentationResult::InvalidValue;
 }
 emotion_=value; return PresentationResult::Applied;
}
PresentationResult PresentationState::setup_gun(bool shown) {
 // Visibility only. SceneCommandRouter separately requires the character
 // manager callback before acknowledging SetupGun(true).
 gun_shown_=shown;
 return PresentationResult::Applied;
}
PresentationResult PresentationState::dont_setup_gun() {
 // This is a character-manager command, not a GunSetUp visibility event.
 // SceneCommandRouter invokes the required manager adapter directly.
 return PresentationResult::Unsupported;
}
PresentationResult PresentationState::show_sign(const std::string& who,const std::string& raw,bool imposter) {
 const auto* c=catalog_.find(who); if(!c)return PresentationResult::NotFound;
 const auto parsed=sign_value(raw); if(!parsed)return PresentationResult::InvalidValue;
 const auto i=static_cast<std::size_t>(*parsed)+(imposter?6u:0u);
 const auto& assets=c->signs[i];
 if(!assets.sprite.valid && assets.frames.empty() && !assets.white.valid && !assets.iris.valid) return PresentationResult::Unsupported;
 active_sign_=SignRenderPacket{c->name,c->source_file,c->source_path_id,*parsed,imposter,assets}; return PresentationResult::Applied;
}
PresentationResult PresentationState::show_player_sign(const std::string& raw) {
 if(!sign_value(raw))return PresentationResult::InvalidValue;
 // No Sanya0/player CharacterSOData record exists in the retained source data.
 // Rendering a surrogate NPC as the player would invent game behavior.
 return PresentationResult::Unsupported;
}
PresentationResult PresentationState::stop_showing_sign() { active_sign_.reset(); return PresentationResult::Applied; }
std::optional<DialogRenderPacket> PresentationState::current_dialog_packet() const {
 if(!emotion_ || dialog_companion_.empty())return std::nullopt;
 const auto* c=catalog_.find(dialog_companion_); if(!c)return std::nullopt;
 const auto animation=std::find_if(c->emotion_animations.begin(),c->emotion_animations.end(),[&](const auto& a){return a.emotion==*emotion_;});
 if(animation==c->emotion_animations.end())return std::nullopt;
 const auto override=std::find_if(c->emotion_overrides.begin(),c->emotion_overrides.end(),[&](const auto& o){return o.emotion==*emotion_;});
 const auto* o=override==c->emotion_overrides.end()?nullptr:&*override;
 return DialogRenderPacket{c->name,c->source_file,c->source_path_id,c->character_type,*emotion_,animation->cycling,animation->frames_per_second,
   animation->frames,presentation_position(*c,o),presentation_scale(*c,o)};
}
PresentationResult PresentationState::parse_pose(const std::string& raw,std::int32_t& value) const {
 static const char* names[]={"FullSize","Staying","Sitting","Something","Corpse","Lying","Pregnant1","Pregnant2","Pregnant3","Bags","Twisted","Hanged","Burned","LostChild","LostChildCorpse","Vomit","Dude_Chilling"};
 if(parse_integer(raw,value)) return value>=0&&value<17?PresentationResult::Applied:PresentationResult::InvalidValue;
 const auto key=lower(raw);
 for(std::int32_t i=0;i<17;++i)if(lower(names[i])==key){value=i;return PresentationResult::Applied;}
 return PresentationResult::InvalidValue;
}
PresentationResult PresentationState::change_pose(const std::string& who,const std::string& raw) {
 const auto* c=catalog_.find(who); if(!c)return PresentationResult::NotFound;
 std::int32_t v=0; auto result=parse_pose(raw,v);if(result!=PresentationResult::Applied)return result;
 if(std::none_of(c->poses.begin(),c->poses.end(),[&](const auto& p){return p.state==v;}))return PresentationResult::Unsupported;
 live_poses_[c->name]=v; immediate_poses_.push_back({c->name,v}); return PresentationResult::Applied;
}
PresentationResult PresentationState::change_pose_tomorrow(const std::string& who,const std::string& raw) {
 const auto* c=catalog_.find(who); if(!c)return PresentationResult::NotFound;
 std::int32_t v=0; auto result=parse_pose(raw,v);if(result!=PresentationResult::Applied)return result;
 if(std::none_of(c->poses.begin(),c->poses.end(),[&](const auto& p){return p.state==v;}))return PresentationResult::Unsupported;
 tomorrow_poses_.push_back({c->name,v}); return PresentationResult::Applied;
}
std::vector<PoseChange> PresentationState::apply_tomorrow_poses() {
 auto applied=tomorrow_poses_;
 for(const auto& change:applied) live_poses_[change.character]=change.state;
 tomorrow_poses_.clear();
 return applied;
}
void PresentationState::clear_pose_changes(){immediate_poses_.clear();tomorrow_poses_.clear();}
PresentationVec3 presentation_position(const CharacterPresentation& c,const PresentationOverride* o) {
 return {c.dialog_position.x+(o?o->position.x:0),c.dialog_position.y+(o?o->position.y:0),0};
}
PresentationVec3 presentation_scale(const CharacterPresentation& c,const PresentationOverride* o) {
 return {c.dialog_scale+(o?o->scale.x:0),c.dialog_scale+(o?o->scale.y:0),c.dialog_scale+(o?o->scale.z:0)};
}
}
