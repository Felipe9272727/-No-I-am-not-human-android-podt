#include "ninah/command_input.hpp"
#include <charconv>
#include <stdexcept>
#include <string_view>
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
void arity(const std::vector<std::string>& v,std::size_t n){if(v.size()!=n+1)throw std::invalid_argument("incorrect gameplay command argument count");}
std::string lower(std::string s){for(auto& c:s)if(c>='A'&&c<='Z')c+='a'-'A';return s;}
Consumable item(const std::string& raw){
 const std::pair<const char*,Consumable> items[]={{"bobeer",Consumable::Bobeer},{"cigarette",Consumable::Cigarette},{"coffee",Consumable::Coffee},{"enerjeka",Consumable::Enerjeka},{"pills",Consumable::Pills},{"mushroom",Consumable::Mushroom},{"catfood",Consumable::CatFood},{"povistka",Consumable::Povistka},{"kombucha",Consumable::Kombucha},{"photo",Consumable::Photo},{"cockroach",Consumable::Cockroach}};
 const auto key=lower(raw);for(const auto& entry:items)if(entry.first==key)return entry.second;
 throw std::invalid_argument("unsupported consumable identifier");
}
std::int32_t integer(const std::string& text){
 std::string_view v=text;if(v.empty())throw std::invalid_argument("empty Int32");
 if(v.front()=='+'){v.remove_prefix(1);if(v.empty()||v.front()=='-'||v.front()=='+')throw std::invalid_argument("invalid Int32 sign");}
 std::int32_t result=0;const auto parsed=std::from_chars(v.data(),v.data()+v.size(),result);
 if(parsed.ec!=std::errc{}||parsed.ptr!=v.data()+v.size())throw std::invalid_argument("invalid Int32 argument");
 return result;
}
bool boolean(const std::string& text){const auto v=lower(text);if(v=="true")return true;if(v=="false")return false;throw std::invalid_argument("boolean argument required");}
}
DialogueCommand decode_gameplay_command(const std::string& text,const CharacterCatalog& catalog){
 const auto v=words(text);if(v.empty())throw std::invalid_argument("empty Yarn command");
 const auto& name=v[0];
 const bool supported=name=="GetItem"||name=="Refuse"||name=="KillTomorrow"||name=="ExileAfterTomorrow"||name=="LetIn"||name=="AggressiveLetIn"||name=="Kill"||name=="ExileCharacter"||name=="OrderCourier"||name=="UpdateDeficitDay"||name=="ExileByFEMA"||name=="KillRoom";
 if(!supported)return UnsupportedDialogueCommand{name};
 for(const auto c:text)if(c=='\"'||c=='\''||c=='\\'||c=='\r'||c=='\n'||c=='\0')throw std::invalid_argument("unsupported quoted or multiline gameplay command");
 if(name=="GetItem"){arity(v,2);return GetItemCommand{item(v[1]),integer(v[2])};}
 if(name=="OrderCourier"){arity(v,2);return OrderCourierCommand{item(v[1]),integer(v[2])};}
 if(name=="UpdateDeficitDay"){arity(v,0);return UpdateDeficitDayCommand{};}
 if(name=="ExileByFEMA"){arity(v,1);return ExileByFEMACommand{integer(v[1])};}
 if(name=="KillRoom"){arity(v,1);return KillRoomCommand{catalog.parse_name(v[1],true)};}
 if(name=="ExileCharacter"){
  if(v.size()!=2&&v.size()!=3)throw std::invalid_argument("incorrect ExileCharacter argument count");
  return ExileCharacterCommand{catalog.parse_name(v[1],true),v.size()==3?boolean(v[2]):false};
 }
 arity(v,1);const auto character=catalog.parse_name(v[1],true);
 if(name=="Refuse")return RefuseCommand{character};
 if(name=="KillTomorrow")return KillTomorrowCommand{character};
 if(name=="ExileAfterTomorrow")return ExileAfterTomorrowCommand{character};
 if(name=="LetIn")return LetCharacterInCommand{character};
 if(name=="AggressiveLetIn")return AggressiveLetInCommand{character};
 return KillCommand{character};
}
}
