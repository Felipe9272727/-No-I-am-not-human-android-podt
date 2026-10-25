#include "ninah/characters.hpp"
#include <algorithm>
#include <stdexcept>
#include <unordered_set>
#include <utility>
namespace ninah {
CharacterCatalog::CharacterCatalog(std::vector<CharacterData> r):records_(std::move(r)){
    std::unordered_set<std::int32_t> ids;for(const auto& c:records_)if(!ids.insert(c.type).second)throw std::invalid_argument("duplicate character ID");
}
const CharacterData* CharacterCatalog::find(std::int32_t t)const noexcept{for(const auto& c:records_)if(c.type==t)return &c;return nullptr;}
const CharacterData& CharacterCatalog::at(std::int32_t t)const{const auto* c=find(t);if(!c)throw std::out_of_range("missing character SO");return *c;}
std::int32_t CharacterCatalog::parse_name(const std::string& name,bool fold)const{
    auto lower=[fold](std::string s){if(fold)for(auto& c:s)if(c>='A'&&c<='Z')c+='a'-'A';return s;};
    for(const auto& c:records_)if(lower(c.name)==lower(name))return c.type;
    throw std::invalid_argument("unknown character identifier");
}
void CharacterCatalog::set_imposter(std::int32_t t,bool v){for(auto& c:records_)if(c.type==t){c.is_imposter=v;return;}throw std::out_of_range("missing character SO");}
bool CharactersState::alive_inside(std::int32_t t)const noexcept{return std::find(inside.begin(),inside.end(),t)!=inside.end();}
bool CharactersState::place_empty(const CharacterCatalog& c,std::int32_t t)const{const auto p=c.at(t).place;for(const auto& r:c.records())if(r.place==p&&alive_inside(r.type))return false;return true;}
std::size_t CharactersState::innocents_count(const CharacterCatalog& c)const{return std::count_if(inside.begin(),inside.end(),[&c](auto t){return !c.at(t).is_imposter;});}
void CharactersState::give_povistka(const CharacterCatalog& c,std::int32_t t){if(c.find(t))with_povistka.push_back(t);}
}
