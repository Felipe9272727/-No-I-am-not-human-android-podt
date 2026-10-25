#include "ninah/command_input.hpp"
#include "production_characters.hpp"
#include "../third_party/nlohmann/json.hpp"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
int main(){
 auto catalog=ninah::production::character_catalog();
 const auto item=std::get<ninah::GetItemCommand>(ninah::decode_gameplay_command("GetItem coffee +2",catalog));
 assert(item.item==ninah::Consumable::Coffee&&item.count==2);
 const auto exile=std::get<ninah::ExileCharacterCommand>(ninah::decode_gameplay_command("ExileCharacter WheelChair TrUe",catalog));
 assert(exile.character_type==catalog.parse_name("Wheelchair",true)&&exile.show_in_dialog);
 const auto courier=std::get<ninah::OrderCourierCommand>(ninah::decode_gameplay_command("OrderCourier CatFood 2",catalog));
 assert(courier.item==ninah::Consumable::CatFood&&courier.count==2);
 assert(std::holds_alternative<ninah::UpdateDeficitDayCommand>(ninah::decode_gameplay_command("UpdateDeficitDay",catalog)));
 assert(std::get<ninah::ExileByFEMACommand>(ninah::decode_gameplay_command("ExileByFEMA 2",catalog)).count==2);
 assert(std::get<ninah::KillRoomCommand>(ninah::decode_gameplay_command("KillRoom Buddy",catalog)).character_type==catalog.parse_name("Buddy",true));
 for(const auto& text:{"GetItem Coffee 2147483648","GetItem Coffee 1.0","GetItem Coffee +-1","ExileCharacter Buddy what","LetIn NoSuchId","Refuse Buddy\nKill Buddy"}){
  bool rejected=false;try{(void)ninah::decode_gameplay_command(text,catalog);}catch(const std::invalid_argument&){rejected=true;}assert(rejected);
 }
 assert(std::holds_alternative<ninah::UnsupportedDialogueCommand>(ninah::decode_gameplay_command("Sound Characters_cat_meow_01",catalog)));
 const auto root=std::filesystem::path(__FILE__).parent_path().parent_path().parent_path();
 std::ifstream input(root/"narrative/program.json");assert(input);nlohmann::json program;input>>program;
 std::size_t decoded=0,forwarded=0;
 for(const auto& node:program.at("nodes"))for(const auto& instruction:node.at("instructions")){
  if(instruction.at("opcode")!=3)continue;
  auto text=instruction.at("operands").at(0).get<std::string>();
  // Explicit interpolation fixture: the VM tests separately validate substitution.
  if(const auto index=text.find("{0}");index!=std::string::npos)text.replace(index,3,"Coffee");
  const auto command=ninah::decode_gameplay_command(text,catalog);
  if(std::holds_alternative<ninah::UnsupportedDialogueCommand>(command))++forwarded;else ++decoded;
 }
 assert(decoded==396&&forwarded==3647);
 std::cout<<"396 original gameplay command instances decoded; 3647 other commands remain explicit host requests\n";
}
