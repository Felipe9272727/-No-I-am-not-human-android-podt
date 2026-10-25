#include "ninah/presentation.hpp"
#include "presentation_provider.hpp"
#include <cassert>
#include <cmath>

int main(){
 using namespace ninah;
 PresentationCatalog catalog(presentation_data::characters());
 PresentationState state(catalog);
 assert(catalog.records().size()==61);
 const auto* alkonost=catalog.find("alkonost");
 assert(alkonost && alkonost->source_path_id==2607);
 const auto* ballerina=catalog.find("Ballerina");
 assert(ballerina && ballerina->emotion_animations.size()==6);
 bool found_ballerina_animation=false;
 for(const auto& animation:ballerina->emotion_animations)if(animation.name=="Ballerina_Dodge1"){
  found_ballerina_animation=true;
  assert(animation.frames.size()==3 && animation.frames_per_second==8);
 }
 assert(found_ballerina_animation);
 const auto mother_initial=state.room_packet("Mother");
 assert(mother_initial && mother_initial->source_file=="sharedassets0.assets");
 assert(mother_initial->source_path_id==2650 && mother_initial->character_type==37);
 assert(mother_initial->room_enum==1 && mother_initial->scene_component_path_id==4558);
 assert(mother_initial->game_object_path_id==503 && !mother_initial->authored_active_self);
 assert(mother_initial->pose_state==2 && mother_initial->pose_name=="Sitting");
 assert(mother_initial->sprite.path_id==1901 && mother_initial->position.z==0 && mother_initial->scale.z==0);
 assert(!mother_initial->cannot_interact);
 const auto fan_initial=state.room_packet("Fan");
 assert(fan_initial && fan_initial->pose_name=="Sitting" && fan_initial->sprite.path_id==1748);
 assert(fan_initial->room_enum==3 && fan_initial->scene_component_path_id==4613);
 assert(state.set_emotion("Sad")==PresentationResult::Applied);
 assert(state.emotion() && *state.emotion()==696031014);
 assert(state.set_emotion("-1966747463")==PresentationResult::Applied);
 assert(state.emotion() && *state.emotion()==-1966747463);
 assert(state.set_emotion("DefinitelyNotAnEmotion")==PresentationResult::InvalidValue);
 assert(state.emotion() && *state.emotion()==-1966747463);
 assert(!state.current_dialog_packet());
 assert(state.set_dialog_companion("NoSuchGuest")==PresentationResult::NotFound);
 assert(state.set_dialog_companion("Dude")==PresentationResult::Applied);
 assert(state.set_emotion("Dude_Smoke")==PresentationResult::Applied);
 const auto packet=state.current_dialog_packet();
 assert(packet && packet->character=="Dude" && packet->character_type==43);
 assert(packet->source_file=="sharedassets0.assets" && packet->source_path_id==2626);
 assert(packet->emotion==-1871267688 && packet->frames.size()==32);
 assert(std::fabs(packet->position.x-(-172.0f))<.0001f);
 assert(std::fabs(packet->position.y-(-84.5f))<.0001f && packet->position.z==0);
 assert(std::fabs(packet->scale.x-1.734998f)<.0001f);
 assert(std::fabs(packet->scale.y-1.734998f)<.0001f);
 assert(std::fabs(packet->scale.z-1.734998f)<.0001f);

 CharacterPresentation transformed; transformed.dialog_position={100,-20}; transformed.dialog_scale=.75f;
 PresentationOverride override; override.position={5,8,91}; override.scale={.25f,-.1f,2};
 const auto pos=presentation_position(transformed,&override);
 const auto scale=presentation_scale(transformed,&override);
 assert(pos.x==105 && pos.y==-12 && pos.z==0);
 assert(std::fabs(scale.x-1.0f)<.0001f && std::fabs(scale.y-.65f)<.0001f && std::fabs(scale.z-2.75f)<.0001f);

 assert(state.setup_gun(true)==PresentationResult::Applied && state.gun_shown().value());
 assert(state.setup_gun(false)==PresentationResult::Applied && !state.gun_shown().value());
 assert(state.setup_gun(true)==PresentationResult::Applied && state.gun_shown().value());
 assert(state.dont_setup_gun()==PresentationResult::Unsupported && state.gun_shown().value());
 assert(state.show_sign("Alkonost","Eye",false)==PresentationResult::Applied);
 assert(state.active_sign() && state.active_sign()->assets.white.path_id==1682);
 assert(state.active_sign()->source_file=="sharedassets0.assets" && state.active_sign()->source_path_id==2607);
 assert(state.show_sign("Alkonost","Hands",false)==PresentationResult::Applied);
 assert(state.active_sign()->assets.sprite.valid && state.active_sign()->assets.sprite.path_id==1598);
 assert(state.show_sign("Alkonost","Teeth",false)==PresentationResult::Applied);
 assert(state.active_sign()->assets.sprite.valid && state.active_sign()->assets.sprite.path_id==1849);
 assert(state.show_sign("Alkonost","Eye",true)==PresentationResult::Applied);
 assert(state.active_sign() && state.active_sign()->imposter);
 assert(state.show_sign("nobody","Eye",false)==PresentationResult::NotFound);
 assert(state.show_sign("Alkonost","not a sign",false)==PresentationResult::InvalidValue);
 assert(state.stop_showing_sign()==PresentationResult::Applied && !state.active_sign());
 assert(state.show_player_sign("Eye")==PresentationResult::Unsupported);
 assert(state.show_player_sign("bogus")==PresentationResult::InvalidValue);

 assert(state.change_pose("Alkonost","FullSize")==PresentationResult::Unsupported);
 assert(state.change_pose("Alkonost","Sitting")==PresentationResult::Applied);
 assert(state.immediate_pose_changes().size()==1 && state.immediate_pose_changes()[0].state==2);
 assert(state.change_pose("Fan","Vomit")==PresentationResult::Applied);
 const auto fan_vomit=state.room_packet("fan");
 assert(fan_vomit && fan_vomit->pose_state==15 && fan_vomit->pose_name=="Vomit");
 assert(fan_vomit->sprite.path_id==2083 && fan_vomit->cannot_interact);
 assert(fan_vomit->position.x==-132 && fan_vomit->position.y==-137);
 assert(fan_vomit->scale.x>6.29f && fan_vomit->scale.x<6.31f && fan_vomit->scale.z==0);
 assert(state.change_pose_tomorrow("Mother","LostChild")==PresentationResult::Applied);
 assert(state.tomorrow_pose_changes().size()==1 && state.tomorrow_pose_changes()[0].state==13);
 const auto mother_before_day=state.room_packet("Mother");
 assert(mother_before_day && mother_before_day->pose_state==2 && mother_before_day->sprite.path_id==1901);
 const auto applied=state.apply_tomorrow_poses();
 assert(applied.size()==1 && applied[0].character=="Mother" && applied[0].state==13);
 const auto mother_lost_child=state.room_packet("Mother");
 assert(mother_lost_child && mother_lost_child->pose_state==13 && mother_lost_child->pose_name=="LostChild");
 assert(mother_lost_child->sprite.path_id==1728);
 assert(mother_lost_child->position.x>518.5f && mother_lost_child->position.x<518.7f);
 assert(mother_lost_child->position.y> -230.9f && mother_lost_child->position.y< -230.7f);
 assert(!mother_lost_child->cannot_interact);
 assert(state.tomorrow_pose_changes().empty());
 assert(state.change_pose("nobody","Sitting")==PresentationResult::NotFound);
 state.clear_pose_changes();
 assert(state.immediate_pose_changes().empty() && state.tomorrow_pose_changes().empty());
}
