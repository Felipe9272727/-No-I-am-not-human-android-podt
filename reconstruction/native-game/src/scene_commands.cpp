#include "ninah/scene_commands.hpp"
#include <stdexcept>
#include <utility>
#include <vector>
namespace ninah {
namespace {
std::vector<std::string> words(const std::string& text){
 std::vector<std::string> out;std::size_t i=0;
 while(i<text.size()){
  while(i<text.size()&&(text[i]==' '||text[i]=='\t'))++i;
  const auto begin=i;while(i<text.size()&&text[i]!=' '&&text[i]!='\t')++i;
  if(begin!=i)out.push_back(text.substr(begin,i-begin));
 }return out;
}
bool boolean(std::string text){
 for(auto& c:text)if(c>='A'&&c<='Z')c+='a'-'A';
 if(text=="true")return true;
 if(text=="false")return false;
 throw std::invalid_argument("scene command requires a boolean");
}
void arity(const std::vector<std::string>& v,std::size_t count){
 if(v.size()!=count+1)throw std::invalid_argument("incorrect scene command argument count");
}
bool applied(PresentationResult result){
 if(result==PresentationResult::InvalidValue)throw std::invalid_argument("invalid presentation enum value");
 return result==PresentationResult::Applied;
}
}
SceneCommandRouter::SceneCommandRouter(const CharacterCatalog& characters,
 PresentationState* presentation,StoryState* story,SceneCommandHooks hooks)
 :characters_(characters),presentation_(presentation),story_(story),hooks_(std::move(hooks)){}
bool SceneCommandRouter::dispatch(const std::string& text){
 const auto v=words(text);if(v.empty())throw std::invalid_argument("empty scene command");
 const auto& name=v[0];
 const bool known=name=="SetEmotion"||name=="SetupGun"||name=="DontSetupGun"||name=="ShowSign"||name=="ShowPlayerSign"||name=="StopShowingSign"||name=="ChangePose"||name=="ChangePoseTomorrow"||name=="BeginCultists"||name=="SaveCultists"||name=="UnlockDeathEnding"||name=="UnlockMushroomEnding"||name=="VigilanteRevealsPlayer"||name=="GetAchievement"||name=="Ending";
 if(!known)return false;
 for(const auto c:text)if(c=='\"'||c=='\''||c=='\\'||c=='\r'||c=='\n'||c=='\0')throw std::invalid_argument("unsupported quoted or multiline scene command");
 if(name=="GetAchievement"){
  arity(v,1);if(!story_)return false;story_->get_achievement(v[1]);return true;
 }
 if(name=="BeginCultists"||name=="SaveCultists"||name=="UnlockDeathEnding"||name=="UnlockMushroomEnding"||name=="VigilanteRevealsPlayer"||name=="Ending"){
  arity(v,0);if(!story_)return false;
  if(name=="BeginCultists")story_->on_begin_cultists();
  else if(name=="SaveCultists")story_->on_save_cultists();
  else if(name=="UnlockDeathEnding")story_->on_unlock_death_ending();
  else if(name=="UnlockMushroomEnding")story_->on_unlock_mushroom_ending();
  else if(name=="VigilanteRevealsPlayer")story_->on_vigilante_reveals_player();
  else story_->ending();
  return true;
 }
 if(name=="DontSetupGun"){
  arity(v,0);if(!hooks_.gun_state_selected)return false;
  hooks_.gun_state_selected(false);return true;
 }
 if(name=="ChangePose"&&v.size()==2)return false; // Original one-argument anomaly remains unresolved.
 const auto count=name=="ShowSign"||name=="ChangePose"||name=="ChangePoseTomorrow"?2u:name=="StopShowingSign"?0u:1u;
 arity(v,count);if(!presentation_)return false;
 if(name=="SetEmotion"){
  // Missing character/animation data must not be acknowledged as rendered.
  auto candidate=*presentation_;
  if(!applied(candidate.set_emotion(v[1]))||!candidate.current_dialog_packet())return false;
  return applied(presentation_->set_emotion(v[1]));
 }
 if(name=="SetupGun"){
  const auto shown=boolean(v[1]);
  if(shown&&!hooks_.gun_state_selected)return false;
  if(shown)hooks_.gun_state_selected(true);
  return applied(presentation_->setup_gun(shown));
 }
 if(name=="ShowSign"){
  const auto& character=characters_.at(characters_.parse_name(v[1],true));
  return applied(presentation_->show_sign(character.name,v[2],character.is_imposter));
 }
 if(name=="ShowPlayerSign")return applied(presentation_->show_player_sign(v[1]));
 if(name=="StopShowingSign")return applied(presentation_->stop_showing_sign());
 const auto& character=characters_.at(characters_.parse_name(v[1],true));
 return applied(name=="ChangePose"?presentation_->change_pose(character.name,v[2]):presentation_->change_pose_tomorrow(character.name,v[2]));
}
}
