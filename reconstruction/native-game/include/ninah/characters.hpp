#pragma once
#include <cstdint>
#include <string>
#include <vector>
namespace ninah {
struct CharacterVisit {std::int32_t day;std::int32_t guest_number;};
struct CharacterData {
    std::int32_t type;
    std::string name;
    std::int32_t room,place;
    bool is_imposter,can_exile,is_preset,randomly_generated_status;
    std::vector<std::int32_t> allowed_days;
    std::vector<CharacterVisit> visits;
    std::int32_t minimum_games_completed;
};
class CharacterCatalog {
public:
    explicit CharacterCatalog(std::vector<CharacterData>);
    const CharacterData* find(std::int32_t)const noexcept;
    const CharacterData& at(std::int32_t)const;
    std::int32_t parse_name(const std::string&,bool ignore_case)const;
    const std::vector<CharacterData>& records()const noexcept{return records_;}
    void set_imposter(std::int32_t,bool);
private:std::vector<CharacterData> records_;
};
struct CharactersState {
    std::vector<std::int32_t> inside,with_povistka;
    bool alive_inside(std::int32_t)const noexcept;
    bool place_empty(const CharacterCatalog&,std::int32_t)const;
    std::size_t innocents_count(const CharacterCatalog&)const;
    void give_povistka(const CharacterCatalog&,std::int32_t);
};
}
