#pragma once
#include "ninah/core.hpp"
#include "ninah/characters.hpp"
#include "ninah/inventory.hpp"
#include "ninah/phone.hpp"
#include "ninah/courier.hpp"
#include "ninah/yarn_bridge.h"
#include <functional>
#include <optional>
#include <string>
namespace ninah {
// State owned by other recovered game services stays behind typed host hooks.
// Missing hooks are reported as errors; they are not replaced with guessed state.
struct DialogueServiceHooks {
 // An absent hook is an unwired host error. A present hook returning nullopt
 // represents the source wrapper's null delegate, which returns false.
 std::function<std::optional<bool>()> can_order_courier;
 std::function<std::optional<CourierOrder>()> get_courier_order;
 std::function<std::optional<bool>()> has_completed_mushroom_condition;
 std::function<std::optional<bool>(std::int32_t)> has_seen_dream;
 std::function<std::optional<bool>()> is_ever_completed_game;
 std::function<std::optional<bool>()> is_need_to_get_deficit_item;
 std::function<std::optional<std::string>()> peek_deficit_item;
 std::function<std::int32_t(std::int32_t)> get_current_place;
 // Arguments follow LocalizationExtension.GetLocalization(key, table).
 std::function<std::string(const std::string&,const std::string&)> localize;
};

class DialogueServices {
public:
 DialogueServices(EnergyState&,CharacterCatalog&,CharactersState&,Inventory&,
                  const PhoneNumbers* phones=nullptr,DialogueServiceHooks hooks={});
 static const char* callback(void*,const char*,const NinahYarnArg*,std::size_t) noexcept;
 const std::string& last_error()const noexcept{return error_;}
private:
 std::optional<std::string> evaluate(const std::string&,const NinahYarnArg*,std::size_t);
 EnergyState& energy_;CharacterCatalog& catalog_;CharactersState& occupants_;Inventory& inventory_;
 const PhoneNumbers* phones_;DialogueServiceHooks hooks_;std::string result_,error_;
};
}
