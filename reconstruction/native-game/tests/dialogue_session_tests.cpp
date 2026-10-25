#include "ninah/dialogue_session.hpp"
#include "production_characters.hpp"
#include "production_data.hpp"
#include "../third_party/nlohmann/json.hpp"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
using Json=nlohmann::json;
std::string read(const std::filesystem::path& path){std::ifstream in(path);if(!in)throw std::runtime_error("missing original test input");return {std::istreambuf_iterator<char>(in),{}};}
struct Fixture{
 ninah::EnergyState energy;
 ninah::CharacterCatalog characters=ninah::production::character_catalog();
 ninah::OccupantsState occupants;
 ninah::InventoryState inventory_state=ninah::InventoryState::initial(false);
 ninah::Inventory inventory{inventory_state};
 ninah::OccupantsRuntime people{characters,occupants,{},0.75f};
 ninah::DialogueCommandDispatcher commands{inventory,people,[this]{return energy.day;}};
 ninah::DialogueServices functions{energy,characters,occupants.characters,inventory};
 Fixture(){energy.day=13;energy.refill(ninah::production::day_config());}
};
int main(){
 const auto root=std::filesystem::path(__FILE__).parent_path().parent_path().parent_path();
 const auto program=read(root/"narrative/program.json"),metadata=read(root/"reverse-localization/line_metadata.json");
 {
  Fixture f;ninah::DialogueSession session(program,metadata,f.functions,f.commands,f.characters);
  const auto before=f.inventory.count(ninah::Consumable::Kombucha);auto event=Json::parse(session.start("Fatman_Asking_1_1_1"));
  std::vector<std::string> presentation;
  for(int i=0;i<30&&event.at("type")!="stopped";++i){
   if(event.at("type")=="command"){
    assert(event.at("requires_host")==true&&session.requires_host_command());
    bool advance_rejected=false;try{session.advance();}catch(const std::logic_error&){advance_rejected=true;}assert(advance_rejected);
    bool stale_rejected=false;try{session.acknowledge_host_command("stale");}catch(const std::invalid_argument&){stale_rejected=true;}assert(stale_rejected);
    const auto text=event.at("command").get<std::string>();presentation.push_back(text);
    event=Json::parse(session.acknowledge_host_command(text));
   }else{assert(event.at("type")=="line");assert(!event.at("metadata").is_null());event=Json::parse(session.advance());}
  }
  assert(event.at("type")=="stopped"&&!session.failed());
  assert((presentation==std::vector<std::string>{"SetEmotion Sad","SetEmotion Base"}));
  assert(f.inventory.count(ninah::Consumable::Kombucha)==before+1);
  event=Json::parse(session.start("Firefighter_Entrance_GoAway"));
  for(int i=0;i<10&&event.at("type")!="stopped";++i){assert(event.at("type")=="line");event=Json::parse(session.advance());}
  assert(event.at("type")=="stopped");assert(f.occupants.refused==std::vector<std::int32_t>{f.characters.parse_name("Firefighter",true)});
 }
 {
  Fixture f;ninah::DialogueSession session(program,metadata,f.functions,f.commands,f.characters);
  auto event=Json::parse(session.start("Alkonost_Asking_6"));assert(event.at("type")=="command");
  event=Json::parse(session.acknowledge_host_command(event.at("command")));
  event=Json::parse(session.advance());assert(event.at("type")=="options");
  bool missing_rejected=false;try{session.choose(1);}catch(const std::logic_error&){missing_rejected=true;}
  assert(missing_rejected&&!session.failed()&&f.energy.remaining==4);
 }
 {
  Fixture f;int notifications=0;ninah::OptionCallbacks callbacks;
  // Explicit host wiring fixture. This test does not assert that all original
  // campaign subscribers have already been reconstructed.
  callbacks.energy_consumed=[&]{++notifications;f.energy.act();};
  ninah::DialogueSession session(program,metadata,f.functions,f.commands,f.characters,callbacks);
  auto event=Json::parse(session.start("Alkonost_Asking_6"));event=Json::parse(session.acknowledge_host_command(event.at("command")));event=Json::parse(session.advance());
  assert(event.at("type")=="options");event=Json::parse(session.choose(1));assert(event.at("type")!="error");assert(notifications==1&&f.energy.remaining==3);
 }
 {
  Fixture f;const std::string broken=R"({"nodes":{"N":{"instructions":[{"opcode":3,"operands":["GetItem Coffee invalid",0]},{"opcode":15,"operands":[]}]}}})";
  ninah::DialogueSession session(broken,R"({"line_metadata":{}})",f.functions,f.commands,f.characters);
  const auto before=f.inventory.count(ninah::Consumable::Coffee);const auto event=Json::parse(session.start("N"));
  assert(event.at("type")=="error"&&session.failed());assert(f.inventory.count(ninah::Consumable::Coffee)==before);
  bool rejected=false;try{session.advance();}catch(const std::logic_error&){rejected=true;}assert(rejected);
 }
 std::cout<<"Original item reward/refusal execute through the session; pending UI effects, selection hooks and failures remain explicit\n";
}
