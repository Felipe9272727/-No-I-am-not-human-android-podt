#include "ninah/scene_commands.hpp"
#include "ninah/dialogue_session.hpp"
#include "presentation_provider.hpp"
#include "production_characters.hpp"
#include "production_data.hpp"
#include "../third_party/nlohmann/json.hpp"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <iostream>
using Json=nlohmann::json;
std::string read(const std::filesystem::path& p){std::ifstream in(p);if(!in)throw std::runtime_error("missing recovered input");return {std::istreambuf_iterator<char>(in),{}};}
int main(){
 auto characters=ninah::production::character_catalog();
 ninah::PresentationCatalog catalog(ninah::presentation_data::characters());
 ninah::PresentationState presentation(catalog);
 ninah::SceneCommandRouter unbound(characters,&presentation);
 assert(!unbound.dispatch("wait 1"));
 assert(!unbound.dispatch("SetEmotion Sad")&&!presentation.emotion());
 assert(!unbound.dispatch("SetupGun true")&&!presentation.gun_shown());
 assert(!unbound.dispatch("DontSetupGun"));
 assert(!unbound.dispatch("ChangePose Dude_Chilling"));
 assert(!unbound.dispatch("ShowPlayerSign EYE"));
 bool begun=false,saved=false,rude=false,death=false,mushroom=false,vigilante=false;
 std::string achievement;bool achievement_option=true;int ending=0;
 ninah::StoryStateQueries queries;
 queries.required_achievement=[&](std::string_view raw,bool option){achievement=raw;achievement_option=option;};
 ninah::StoryState story({&begun,&saved,&rude,&death,&mushroom,&vigilante},queries);
 story.subscribe_ending([&]{++ending;});
 std::vector<bool> gun_events;
 ninah::SceneCommandHooks hooks;hooks.gun_state_selected=[&](bool shown){gun_events.push_back(shown);};
 ninah::SceneCommandRouter router(characters,&presentation,&story,hooks);
 assert(router.dispatch("SetupGun true")&&presentation.gun_shown().value());
 assert(router.dispatch("DontSetupGun")&&presentation.gun_shown().value());
 assert(router.dispatch("SetupGun false")&&!presentation.gun_shown().value());
 assert((gun_events==std::vector<bool>{true,false}));
 assert(router.dispatch("BeginCultists")&&begun);
 assert(router.dispatch("SaveCultists")&&saved);
 assert(router.dispatch("UnlockDeathEnding")&&death);
 assert(router.dispatch("UnlockMushroomEnding")&&mushroom);
 assert(router.dispatch("VigilanteRevealsPlayer")&&vigilante);
 assert(router.dispatch("GetAchievement COURIER_ORDER")&&achievement=="COURIER_ORDER"&&!achievement_option);
 assert(router.dispatch("Ending")&&ending==1);
 bool invalid=false;try{router.dispatch("BeginCultists extra");}catch(const std::invalid_argument&){invalid=true;}assert(invalid);
 assert(presentation.set_dialog_companion("Fatman")==ninah::PresentationResult::Applied);
 ninah::EnergyState energy;energy.day=13;energy.refill(ninah::production::day_config());
 ninah::OccupantsState occupants;
 auto inventory_state=ninah::InventoryState::initial(false);ninah::Inventory inventory(inventory_state);
 ninah::OccupantsRuntime people(characters,occupants,{},0.75f);
 ninah::DialogueCommandDispatcher commands(inventory,people,[&]{return energy.day;});
 ninah::DialogueServices functions(energy,characters,occupants.characters,inventory);
 const auto root=std::filesystem::path(__FILE__).parent_path().parent_path().parent_path();
 ninah::DialogueSession session(read(root/"narrative/program.json"),read(root/"reverse-localization/line_metadata.json"),functions,commands,characters,{},[&](const std::string& command){return router.dispatch(command);});
 const auto before=inventory.count(ninah::Consumable::Kombucha);
 auto event=Json::parse(session.start("Fatman_Asking_1_1_1"));
 int lines=0;
 for(int i=0;i<20&&event.at("type")!="stopped";++i){
  assert(event.at("type")=="line"&&!session.requires_host_command());++lines;
  event=Json::parse(session.advance());
 }
 assert(event.at("type")=="stopped"&&lines==6&&!session.failed());
 assert(inventory.count(ninah::Consumable::Kombucha)==before+1);
 const auto packet=presentation.current_dialog_packet();
 assert(packet&&packet->character=="Fatman"&&packet->emotion==-1966747463&&!packet->frames.empty());
 std::cout<<"Original Fatman route changes portrait data and inventory through one session; missing adapters remain explicit\n";
}
