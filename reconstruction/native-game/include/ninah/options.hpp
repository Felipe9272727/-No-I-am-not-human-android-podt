#pragma once

#include "production_line_metadata.hpp"

#include <functional>
#include <optional>
#include <string_view>
#include <vector>

namespace ninah {

// Values recovered from _Code.Characters.DialogSystem.EDialogButtonStyle.
enum class OptionButtonStyle : unsigned char {
    Energy = 2,
    ConsumablesGet = 3,
    ConsumablesGive = 4,
    Gun = 5,
    Skip = 7,
};

// These are signals raised by the recovered FakeOptionView callbacks. They
// name events; they do not encode energy costs or inventory effects.
enum class OptionCallback : unsigned char {
    EnergyConsumed,
    DayDialogSelected,
    WereBadBoy,
};

struct OptionPolicy {
    bool line_id_known = false;
    std::uint16_t source_tag_mask = 0;
    std::optional<OptionButtonStyle> style_override;
    std::vector<OptionCallback> callbacks_in_registration_order;
};

struct OptionCallbacks {
    std::function<void()> energy_consumed;
    std::function<void()> day_dialog_selected;
    std::function<void()> were_bad_boy;
};

const generated::ProductionLineMetadata* find_production_line_metadata(std::string_view line_id) noexcept;
OptionPolicy resolve_option_policy(std::string_view line_id);
void dispatch_option_callbacks(const OptionPolicy& policy, const OptionCallbacks& callbacks);

} // namespace ninah
