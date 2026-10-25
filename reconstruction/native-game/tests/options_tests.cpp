#include "ninah/options.hpp"

#include <cassert>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

using namespace ninah;

static bool has_tag(const OptionPolicy& policy, std::uint16_t tag) {
    return (policy.source_tag_mask & tag) != 0;
}

int main() {
    // Real line metadata from the original Dialogs Shared Data bundle.
    const auto energy = resolve_option_policy("line:Firefighter_WannaCheck_07ebaea");
    assert(energy.line_id_known);
    assert(has_tag(energy, generated::kLineTagEnergy));
    assert(has_tag(energy, generated::kLineTagLastLine));
    assert(energy.style_override == OptionButtonStyle::Energy);
    assert((energy.callbacks_in_registration_order ==
            std::vector<OptionCallback>{OptionCallback::EnergyConsumed}));

    const auto day_dialog = resolve_option_policy("line:talk_esenin_1_031fe56");
    assert(day_dialog.line_id_known && has_tag(day_dialog, generated::kLineTagDayDialog));
    assert(!day_dialog.style_override.has_value());
    assert((day_dialog.callbacks_in_registration_order ==
            std::vector<OptionCallback>{OptionCallback::DayDialogSelected}));

    const auto get_item = resolve_option_policy("line:0067a14");
    assert(get_item.line_id_known && has_tag(get_item, generated::kLineTagGetItem));
    assert(get_item.style_override == OptionButtonStyle::ConsumablesGet);
    assert(get_item.callbacks_in_registration_order.empty());

    const auto actual_give_item = resolve_option_policy("line:0091b28");
    assert(actual_give_item.line_id_known && has_tag(actual_give_item, generated::kLineTagGiveItem));
    assert(actual_give_item.style_override == OptionButtonStyle::ConsumablesGive);
    assert(actual_give_item.callbacks_in_registration_order.empty());

    const auto gun = resolve_option_policy("line:Alkonost_Armpit_0f065cf");
    assert(gun.line_id_known && has_tag(gun, generated::kLineTagGun));
    assert(gun.style_override == OptionButtonStyle::Gun);
    assert(gun.callbacks_in_registration_order.empty());

    const auto skip = resolve_option_policy("line:entrance_neighbour_0_02eea17");
    assert(skip.line_id_known && has_tag(skip, generated::kLineTagSkip));
    assert(skip.style_override == OptionButtonStyle::Skip);
    assert(skip.callbacks_in_registration_order.empty());

    const auto rude = resolve_option_policy("line:Entrance_Gasmask_13_1_0ae8044");
    assert(rude.line_id_known && has_tag(rude, generated::kLineTagRude));
    assert(!rude.style_override.has_value());
    assert((rude.callbacks_in_registration_order ==
            std::vector<OptionCallback>{OptionCallback::WereBadBoy}));

    // Known untagged lines retain an empty policy; unknown IDs fail closed.
    const auto known_untagged = resolve_option_policy("line:Firefighter_WannaCheck_0a3368a");
    assert(known_untagged.line_id_known && known_untagged.source_tag_mask == 0);
    assert(!known_untagged.style_override && known_untagged.callbacks_in_registration_order.empty());
    const auto unknown = resolve_option_policy("line:not-in-recovered-assets");
    assert(!unknown.line_id_known && unknown.source_tag_mask == 0);
    assert(!unknown.style_override && unknown.callbacks_in_registration_order.empty());

    // Recovered handlers only emit events. No energy amount or inventory cost is
    // encoded here; the owning gameplay subscriber decides what those mean.
    std::vector<std::string> observed;
    OptionCallbacks callbacks;
    callbacks.energy_consumed = [&] { observed.push_back("energy-consumed"); };
    callbacks.day_dialog_selected = [&] { observed.push_back("day-dialog-selected"); };
    callbacks.were_bad_boy = [&] { observed.push_back("were-bad-boy"); };
    dispatch_option_callbacks(energy, callbacks);
    dispatch_option_callbacks(day_dialog, callbacks);
    dispatch_option_callbacks(get_item, callbacks);
    dispatch_option_callbacks(actual_give_item, callbacks);
    dispatch_option_callbacks(gun, callbacks);
    dispatch_option_callbacks(skip, callbacks);
    dispatch_option_callbacks(rude, callbacks);
    assert((observed == std::vector<std::string>{"energy-consumed", "day-dialog-selected", "were-bad-boy"}));

    bool unknown_rejected = false;
    try {
        dispatch_option_callbacks(unknown, callbacks);
    } catch (const std::invalid_argument&) {
        unknown_rejected = true;
    }
    assert(unknown_rejected);
    assert((observed == std::vector<std::string>{"energy-consumed", "day-dialog-selected", "were-bad-boy"}));

    return 0;
}
