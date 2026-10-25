#include "ninah/dialogue_services.hpp"
#include "production_characters.hpp"
#include "production_data.hpp"
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <unordered_set>
std::string take(char* p){if(!p)throw std::runtime_error("missing event");std::string s(p);ninah_yarn_free_string(p);return s;}
int main(int argc,char** argv){
 if(argc!=3)throw std::runtime_error("original program and line metadata JSON paths required");
 std::ifstream input(argv[1]);if(!input)throw std::runtime_error("original program unavailable");
 const std::string program((std::istreambuf_iterator<char>(input)),{});
 std::ifstream metadata_input(argv[2]);if(!metadata_input)throw std::runtime_error("original line metadata unavailable");
 const std::string metadata((std::istreambuf_iterator<char>(metadata_input)),{});
 ninah::EnergyState energy;energy.day=13;energy.refill(ninah::production::day_config());
 auto catalog=ninah::production::character_catalog();ninah::CharactersState occupants;
 auto inventory_state=ninah::InventoryState::initial(false);inventory_state.storage.at(ninah::Consumable::Povistka)=1; // Explicit test fixture.
 std::unordered_set<ninah::Consumable> meta;
 ninah::InventoryHooks hooks;
 hooks.meta_ever_used=[&](auto item){return meta.count(item)!=0;};hooks.meta_use_consumable=[&](auto item){meta.insert(item);};
 hooks.give_povistka=[&](auto type){occupants.give_povistka(catalog,type);};
 hooks.unlock_achievement=[](const auto&){throw std::runtime_error("unexpected fixture achievement");};
 ninah::Inventory inventory(inventory_state,hooks);ninah::DialogueServices services(energy,catalog,occupants,inventory);
 auto create_vm=[&](){
  char* error=nullptr;auto* vm=ninah_yarn_create(program.c_str(),&services,ninah::DialogueServices::callback,&error);
  if(!vm)throw std::runtime_error(take(error));
  if(!ninah_yarn_load_line_metadata(vm,metadata.c_str(),&error)){ninah_yarn_destroy(vm);throw std::runtime_error(take(error));}
  return vm;
 };
 for(int pass=0;pass<2;++pass){
  if(pass){energy.act_all();}
  auto* vm=create_vm();
  take(ninah_yarn_start(vm,"Alkonost_Asking_6"));take(ninah_yarn_advance(vm));
  std::cout<<"energy="<<energy.remaining<<'\n'<<take(ninah_yarn_advance(vm))<<'\n';
  if(pass){std::cout<<take(ninah_yarn_choose(vm,1))<<'\n';}
  ninah_yarn_destroy(vm);
 }
 energy.refill(ninah::production::day_config());
 for(int pass=0;pass<2;++pass){
  auto* vm=create_vm();
  take(ninah_yarn_start(vm,"talk_alt_1"));std::cout<<"povistka="<<inventory.count(ninah::Consumable::Povistka)<<'\n'<<take(ninah_yarn_advance(vm))<<'\n';
  if(!pass){std::cout<<take(ninah_yarn_choose(vm,2))<<'\n';if(inventory.count(ninah::Consumable::Povistka)!=0||occupants.with_povistka!=std::vector<std::int32_t>{catalog.parse_name("Alt",false)}||inventory.state().povistkas_used!=1)throw std::runtime_error("original item-give route failed");}
  ninah_yarn_destroy(vm);
 }
}
