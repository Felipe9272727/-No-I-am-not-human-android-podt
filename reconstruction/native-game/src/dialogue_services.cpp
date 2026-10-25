#include "ninah/dialogue_services.hpp"
#include <cerrno>
#include <cmath>
#include <cstdlib>
#include <limits>
#include <stdexcept>
namespace ninah {
namespace {
constexpr const char* CHARACTER_NAMES[]={
 "Sanya","TV","Courier","Neighbour","Esenin","Anxiety","Daughter","Cold","Fan","Prophet",
 "SuperFake","Widow","Scammer","Doc","Gasmask","WolfHound","Hunter","NotTrue","Greatmother","Sexy",
 "Phone","Anger","Luka","FormerFema","Foreigner","Alkonost","Blind","Marauder","Nun","TaxiDriver",
 "Firefighter","Fugitive","Teacher","Edgar","Raskolnikov","GraveDigger","Provocateur","Mother","Wifefema","Vigilante",
 "Theorist","Buddy","FortuneTeller","Dude","Bestson","BigLebowski","Couple","Fatman","Wheelchair","CultistOne",
 "CultistTwo","CultistThree","CultistPriest","Ballerina","Intruder","MushroomEater","Miner","Sirin","Empty","Twins",
 "Player","Jacob","StaticBoy","Tourist","Unstable","Rocker","Experienced","Jacket","Tough","Bald",
 "Nervous","Leper","Fairytaller","FunnyGuy","Alt"
};
constexpr const char* DREAM_NAMES[]={"Ball","StrangeMorning","BodyEater","Mushroom","DameDaNeDaMeYoDameNaNoYo"};
void arity(std::size_t n,std::size_t expected){if(n!=expected)throw std::invalid_argument("invalid game-function arity");}
std::string string_arg(const NinahYarnArg& a){if(a.tag!=3||!a.text)throw std::invalid_argument("string argument required");return a.text;}
std::int32_t int_arg(const NinahYarnArg& a){if(a.tag!=1||!std::isfinite(a.number)||std::trunc(a.number)!=a.number||a.number<std::numeric_limits<std::int32_t>::min()||a.number>std::numeric_limits<std::int32_t>::max())throw std::invalid_argument("integral Int32 argument required");return static_cast<std::int32_t>(a.number);}
std::string lower(std::string s){for(auto& c:s)if(c>='A'&&c<='Z')c+='a'-'A';return s;}
std::int32_t enum_arg(const std::string& raw,const char* const* names,std::size_t count,const char* type){
 const auto normalized=lower(raw);
 for(std::size_t i=0;i<count;++i)if(normalized==lower(names[i]))return static_cast<std::int32_t>(i);
 std::string trimmed=raw;
 const auto first=trimmed.find_first_not_of(" \t\r\n\f\v");
 if(first!=std::string::npos){const auto last=trimmed.find_last_not_of(" \t\r\n\f\v");trimmed=trimmed.substr(first,last-first+1);}
 if(!trimmed.empty()){
  char* end=nullptr;errno=0;const auto value=std::strtoll(trimmed.c_str(),&end,10);
  if(errno!=ERANGE&&end==trimmed.c_str()+trimmed.size()&&end!=trimmed.c_str()&&value>=std::numeric_limits<std::int32_t>::min()&&value<=std::numeric_limits<std::int32_t>::max())return static_cast<std::int32_t>(value);
 }
 throw std::invalid_argument(std::string("invalid ")+type+" enum identifier");
}
std::string enum_name(std::int32_t value,const char* const* names,std::size_t count){return value>=0&&static_cast<std::size_t>(value)<count?names[value]:std::to_string(value);}
std::string consumable_name(Consumable item){
 switch(item){case Consumable::Bobeer:return "Bobeer";case Consumable::Cigarette:return "Cigarette";case Consumable::Coffee:return "Coffee";case Consumable::Enerjeka:return "Enerjeka";case Consumable::Pills:return "Pills";case Consumable::Mushroom:return "Mushroom";case Consumable::CatFood:return "CatFood";case Consumable::Povistka:return "Povistka";case Consumable::Kombucha:return "Kombucha";case Consumable::Photo:return "Photo";case Consumable::Cockroach:return "Cockroach";}
 return std::to_string(static_cast<std::int32_t>(item));
}
std::string localize(const DialogueServiceHooks& hooks,const std::string& key){if(!hooks.localize)throw std::logic_error("dialogue service unavailable: localization");return hooks.localize(key,"UI");}
template<class T>const T& require_hook(const T& hook,const char* name){if(!hook)throw std::logic_error(std::string("dialogue service unavailable: ")+name);return hook;}
Consumable item_arg(const NinahYarnArg& a){
 const std::pair<const char*,Consumable> values[]={{"bobeer",Consumable::Bobeer},{"cigarette",Consumable::Cigarette},{"coffee",Consumable::Coffee},{"enerjeka",Consumable::Enerjeka},{"pills",Consumable::Pills},{"mushroom",Consumable::Mushroom},{"catfood",Consumable::CatFood},{"povistka",Consumable::Povistka},{"kombucha",Consumable::Kombucha},{"photo",Consumable::Photo},{"cockroach",Consumable::Cockroach}};
 const auto name=lower(string_arg(a));for(const auto& v:values)if(name==v.first)return v.second;
 throw std::invalid_argument("unknown consumable identifier");
}
PhoneSubscriber phone_arg(const NinahYarnArg& a){
 const char* names[]={"none","forrest","fema","neighbour","psychics","auracam","extrasens","bestsonfamily","mothershusband","alkonostshusband","daughter","phoneroulette","angerswife","femarecruiter","foreignembassy","daughtersfriend"};
 const auto name=lower(string_arg(a));for(int i=0;i<16;++i)if(name==names[i])return static_cast<PhoneSubscriber>(i);
 throw std::invalid_argument("unknown phone subscriber");
}
std::string boolean(bool v){return v?"true":"false";}
std::string quote(const std::string& s){
 const char* hex="0123456789abcdef";std::string out="\"";
 for(unsigned char c:s){if(c=='"'||c=='\\'){out+='\\';out+=static_cast<char>(c);}else if(c<32){out+="\\u00";out+=hex[c>>4];out+=hex[c&15];}else out+=static_cast<char>(c);}
 return out+'"';
}
}
DialogueServices::DialogueServices(EnergyState& e,CharacterCatalog& c,CharactersState& o,Inventory& i,const PhoneNumbers* p,DialogueServiceHooks h):energy_(e),catalog_(c),occupants_(o),inventory_(i),phones_(p),hooks_(std::move(h)){}
std::optional<std::string> DialogueServices::evaluate(const std::string& f,const NinahYarnArg* a,std::size_t n){
 if(!a&&n)throw std::invalid_argument("null argument array");
 if(f=="GetEnergy"){arity(n,0);return std::to_string(energy_.remaining);}
 if(f=="GetItemCount"){arity(n,1);return std::to_string(inventory_.count(item_arg(a[0])));}
 if(f=="IsNobodyHome"){arity(n,0);return boolean(occupants_.inside.empty());}
 if(f=="GetInnocentsCount"){arity(n,0);return std::to_string(occupants_.innocents_count(catalog_));}
 if(f=="IsAlive"){arity(n,1);return boolean(occupants_.alive_inside(catalog_.parse_name(string_arg(a[0]),true)));}
 if(f=="IsImposter"){
  arity(n,1);const auto name=string_arg(a[0]);for(const auto& c:catalog_.records())if(c.name==name)return boolean(c.is_imposter);return "false";
 }
 if(f=="IsCharacterPlaceEmpty"){arity(n,1);return boolean(occupants_.place_empty(catalog_,catalog_.parse_name(string_arg(a[0]),true)));}
 if(f=="TryGiveItem"||f=="TryGiveItemFor"){
  arity(n,f=="TryGiveItem"?2:3);const auto recipient=n==3?catalog_.parse_name(string_arg(a[2]),true):0;
  return boolean(inventory_.try_give_item(item_arg(a[0]),int_arg(a[1]),recipient));
 }
 if(f=="CanOrderCourier"){arity(n,0);return boolean(require_hook(hooks_.can_order_courier,"CanOrderCourier")().value_or(false));}
 if(f=="GetCourierOrder"){
  arity(n,0);auto order=require_hook(hooks_.get_courier_order,"GetCourierOrder")();
  // Native wrapper substitutes new DialogCourierOrderData(Bobeer, 1) for a null result.
  const CourierOrder resolved=order.value_or(CourierOrder{Consumable::Bobeer,1});
  const auto key="consumable_"+lower(consumable_name(resolved.item))+"_name";
  return quote(localize(hooks_,key)+" (x"+std::to_string(resolved.count)+")");
 }
 if(f=="GetCharacterOnPlace"){
  arity(n,1);const auto requested=enum_arg(string_arg(a[0]),CHARACTER_NAMES,sizeof(CHARACTER_NAMES)/sizeof(CHARACTER_NAMES[0]),"character");
  const auto* target=catalog_.find(requested);
  const auto& place_of=require_hook(hooks_.get_current_place,"GetCharacterOnPlace current-place lookup");
  std::int32_t result=0; // Enumerable.FirstOrDefault(ECharacterType) returns enum value zero.
  for(const auto occupant:occupants_.inside){if(target&&place_of(occupant)==target->place){result=occupant;break;}}
  const auto key="characterName_"+enum_name(result,CHARACTER_NAMES,sizeof(CHARACTER_NAMES)/sizeof(CHARACTER_NAMES[0]));
  return quote(localize(hooks_,key));
 }
 if(f=="HasCompletedMushroomCondition"){arity(n,0);return boolean(require_hook(hooks_.has_completed_mushroom_condition,"HasCompletedMushroomCondition")().value_or(false));}
 if(f=="HasSeenDream"){
  arity(n,1);const auto dream=enum_arg(string_arg(a[0]),DREAM_NAMES,sizeof(DREAM_NAMES)/sizeof(DREAM_NAMES[0]),"dream");
  return boolean(require_hook(hooks_.has_seen_dream,"HasSeenDream")(dream).value_or(false));
 }
 if(f=="IsEverCompletedGame"){arity(n,0);return boolean(require_hook(hooks_.is_ever_completed_game,"IsEverCompletedGame")().value_or(false));}
 if(f=="IsNeedToGetDeficitItem"){arity(n,0);return boolean(require_hook(hooks_.is_need_to_get_deficit_item,"IsNeedToGetDeficitItem")().value_or(false));}
 if(f=="LocalizeItem"){arity(n,1);return quote(localize(hooks_,"consumable_"+lower(string_arg(a[0]))+"_name"));}
 if(f=="PeekDeficitItem"){
  arity(n,0);const auto peeked=require_hook(hooks_.peek_deficit_item,"PeekDeficitItem")();
  // Native wrapper converts a null callback result to the empty string.
  return quote(peeked.value_or(""));
 }
 if(f=="GetPhoneNumber"){
  arity(n,1);if(!phones_)throw std::logic_error("phone-number state unavailable");
  return quote(PhoneNumberService::get_number_by_subscriber(*phones_,phone_arg(a[0])));
 }
 return std::nullopt;
}
const char* DialogueServices::callback(void* user,const char* name,const NinahYarnArg* args,std::size_t count)noexcept{
 if(!user||!name)return nullptr;
 auto& self=*static_cast<DialogueServices*>(user);
 try{auto value=self.evaluate(name,args,count);if(!value){self.error_=std::string("unimplemented game function: ")+name;return nullptr;}self.error_.clear();self.result_=*value;return self.result_.c_str();}
 catch(const std::exception& e){self.error_=e.what();return nullptr;}
 catch(...){self.error_="unknown game-service failure";return nullptr;}
}
}
