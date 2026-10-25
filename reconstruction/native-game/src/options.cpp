#include "ninah/options.hpp"

#include <algorithm>
#include <stdexcept>

namespace ninah {
namespace {

bool has_tag(std::uint16_t mask, std::uint16_t bit) noexcept {
    return (mask & bit) != 0;
}

} // namespace

const generated::ProductionLineMetadata* find_production_line_metadata(std::string_view line_id) noexcept {
    const auto& rows = generated::kProductionLineMetadata;
    const auto it = std::lower_bound(rows.begin(), rows.end(), line_id,
        [](const generated::ProductionLineMetadata& row, std::string_view key) {
            return row.line_id < key;
        });
    if (it == rows.end() || it->line_id != line_id) return nullptr;
    return &*it;
}

OptionPolicy resolve_option_policy(std::string_view line_id) {
    OptionPolicy result;
    const auto* metadata = find_production_line_metadata(line_id);
    if (!metadata) return result;
    result.line_id_known = true;
    result.source_tag_mask = metadata->tag_mask;

    // FakeOptionView.set_Option tests style tags in this order. If malformed
    // metadata combines several style tags, the later native SelectStyle call
    // wins; production data currently has no conflicting style-tag sets.
    if (has_tag(metadata->tag_mask, generated::kLineTagEnergy))
        result.style_override = OptionButtonStyle::Energy;
    if (has_tag(metadata->tag_mask, generated::kLineTagGetItem))
        result.style_override = OptionButtonStyle::ConsumablesGet;
    if (has_tag(metadata->tag_mask, generated::kLineTagGiveItem))
        result.style_override = OptionButtonStyle::ConsumablesGive;
    if (has_tag(metadata->tag_mask, generated::kLineTagGun))
        result.style_override = OptionButtonStyle::Gun;

    // The native setter registers these callbacks in this order, independently
    // of the style-only tags. The energy callback does not specify a quantity.
    if (has_tag(metadata->tag_mask, generated::kLineTagEnergy))
        result.callbacks_in_registration_order.push_back(OptionCallback::EnergyConsumed);
    if (has_tag(metadata->tag_mask, generated::kLineTagDayDialog))
        result.callbacks_in_registration_order.push_back(OptionCallback::DayDialogSelected);
    if (has_tag(metadata->tag_mask, generated::kLineTagSkip))
        result.style_override = OptionButtonStyle::Skip;
    if (has_tag(metadata->tag_mask, generated::kLineTagRude))
        result.callbacks_in_registration_order.push_back(OptionCallback::WereBadBoy);

    // `lastline` is retained in the provider but has no tag-specific effect in
    // FakeOptionView.set_Option; another native consumer is outside this unit.
    return result;
}

void dispatch_option_callbacks(const OptionPolicy& policy, const OptionCallbacks& callbacks) {
    // Host integration policy: reject missing source metadata before running
    // game-facing callbacks. This explicit guard is not asserted as original UI behavior.
    if (!policy.line_id_known) throw std::invalid_argument("option line metadata is unavailable");
    for (const auto callback : policy.callbacks_in_registration_order) {
        switch (callback) {
            case OptionCallback::EnergyConsumed:
                if (callbacks.energy_consumed) callbacks.energy_consumed();
                break;
            case OptionCallback::DayDialogSelected:
                if (callbacks.day_dialog_selected) callbacks.day_dialog_selected();
                break;
            case OptionCallback::WereBadBoy:
                if (callbacks.were_bad_boy) callbacks.were_bad_boy();
                break;
        }
    }
}

} // namespace ninah
