#include "ninah/dialogue_session.hpp"
#include "production_characters.hpp"
#include "production_data.hpp"
#include "../third_party/nlohmann/json.hpp"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
using Json=nlohmann::json;
std::string read(const std::filesystem::path& path){
 std::ifstream in(path);if(!in)throw std::runtime_error("missing recovered test input");
 return {std::istreambuf_iterator<char>(in),{}};
}
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
  Fixture f;int effects=0;
  auto presentation=[&](const std::string& text){assert(text.rfind("SetEmotion ",0)==0);++effects;return true;};
  ninah::DialogueSession source(program,metadata,f.functions,f.commands,f.characters,{},presentation);
  auto event=Json::parse(source.start("Fatman_Asking_1_1_1"));
  const auto before=f.inventory.count(ninah::Consumable::Kombucha);
  for(int i=0;i<20&&f.inventory.count(ninah::Consumable::Kombucha)==before;++i){assert(event.at("type")=="line");event=Json::parse(source.advance());}
  assert(event.at("type")=="line"&&event.at("line_id")=="line:Fatman_Asking_1_1_1_04bcea8");
  assert(effects==2&&f.inventory.count(ninah::Consumable::Kombucha)==before+1);
  const auto saved=source.dump_snapshot();
  // Gameplay state is an explicit part of the host's save transaction.
  Fixture restored;restored.inventory_state=f.inventory_state;
  ninah::DialogueSession target(program,metadata,restored.functions,restored.commands,restored.characters,{},presentation);
  target.restore_snapshot(saved);assert(target.current_event()==source.current_event());
  assert(Json::parse(target.advance()).at("type")=="stopped");
  assert(restored.inventory.count(ninah::Consumable::Kombucha)==before+1&&effects==2);
  auto corrupt=Json::parse(saved);corrupt["payload"]["event"]["line_id"]="wrong";
  const auto previous=target.dump_snapshot();bool rejected=false;
  try{target.restore_snapshot(corrupt.dump());}catch(const std::exception&){rejected=true;}
  assert(rejected&&target.dump_snapshot()==previous);
 }
 {
  Fixture f;ninah::DialogueSession source(program,metadata,f.functions,f.commands,f.characters);
  auto event=Json::parse(source.start("Alkonost_Asking_6"));
  assert(event.at("type")=="command");const auto command=event.at("command").get<std::string>();
  const auto saved=source.dump_snapshot();
  ninah::DialogueSession target(program,metadata,f.functions,f.commands,f.characters);
  target.restore_snapshot(saved);assert(target.requires_host_command());
  bool blocked=false;try{target.advance();}catch(const std::logic_error&){blocked=true;}assert(blocked);
  assert(Json::parse(target.acknowledge_host_command(command)).at("type")=="line");
  assert(Json::parse(source.acknowledge_host_command(command)).at("type")=="line");
  event=Json::parse(source.advance());assert(event.at("type")=="options");
  const auto choices=source.dump_snapshot();
  int energy_notifications=0;ninah::OptionCallbacks callbacks;
  callbacks.energy_consumed=[&]{++energy_notifications;f.energy.act();};
  ninah::DialogueSession choice_target(program,metadata,f.functions,f.commands,f.characters,callbacks);
  choice_target.restore_snapshot(choices);assert(choice_target.current_event()==source.current_event());
  assert(energy_notifications==0&&f.energy.remaining==4);
  event=Json::parse(choice_target.choose(1));assert(event.at("type")!="error");
  assert(energy_notifications==1&&f.energy.remaining==3);
 }
 {
  Fixture f;const std::string p=R"({"nodes":{"N":{"instructions":[{"opcode":3,"operands":["wait 1",0]},{"opcode":15,"operands":[]}]}}})";
  const std::string m=R"({"line_metadata":{}})";
  ninah::DialogueSession source(p,m,f.functions,f.commands,f.characters);
  const auto initial=source.dump_snapshot();source.start("N");source.restore_snapshot(initial);
  bool blocked=false;try{source.advance();}catch(const std::logic_error&){blocked=true;}assert(blocked);
  const auto pending=Json::parse(source.start("N"));assert(pending.at("command")=="wait 1");
  // A snapshot from a different graph cannot overwrite a currently active one.
  ninah::DialogueSession other(R"({"nodes":{"M":{"instructions":[]}}})",m,f.functions,f.commands,f.characters);
  const auto old=other.dump_snapshot();bool rejected=false;
  try{other.restore_snapshot(source.dump_snapshot());}catch(const std::exception&){rejected=true;}
  assert(rejected&&other.dump_snapshot()==old);
 }
 std::cout<<"Dialogue snapshots preserve visible choices/host requests and resume after original rewards without replay\n";
}
