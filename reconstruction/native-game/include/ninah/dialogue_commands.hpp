#pragma once

#include "ninah/characters.hpp"
#include "ninah/courier.hpp"
#include "ninah/inventory.hpp"
#include "ninah/occupants.hpp"

#include <cstdint>
#include <functional>
#include <string>
#include <variant>
#include <vector>

namespace ninah {

// These are already parsed, typed Yarn arguments. The Rust VM adapter is
// responsible for decoding Yarn data before constructing one of these values.
// In particular, this API does not interpret command strings as shell text.
struct GetItemCommand {
    Consumable item;
    std::int32_t count;
};
struct RefuseCommand {
    std::int32_t character_type;
};
struct KillTomorrowCommand {
    std::int32_t character_type;
};
struct ExileAfterTomorrowCommand {
    std::int32_t character_type;
};
struct LetCharacterInCommand {
    std::int32_t character_type;
};
struct AggressiveLetInCommand {
    std::int32_t character_type;
};
struct KillCommand {
    std::int32_t character_type;
};
struct ExileCharacterCommand {
    std::int32_t character_type;
    bool show_in_dialog = false;
};
struct OrderCourierCommand {
    Consumable item;
    std::int32_t count;
};
struct UpdateDeficitDayCommand {};
struct ExileByFEMACommand {
    std::int32_t count;
};
struct KillRoomCommand {
    std::int32_t character_type;
};
struct UnsupportedDialogueCommand {
    std::string name;
};

using DialogueCommand = std::variant<GetItemCommand, RefuseCommand,
                                     KillTomorrowCommand,
                                     ExileAfterTomorrowCommand,
                                     LetCharacterInCommand,
                                     AggressiveLetInCommand, KillCommand,
                                     ExileCharacterCommand,
                                     OrderCourierCommand,
                                     UpdateDeficitDayCommand,
                                     ExileByFEMACommand, KillRoomCommand,
                                     UnsupportedDialogueCommand>;

struct LetInInputs {
    float is_human_fema_rating;
    float character_fema_bonus;
    float min_imposters_percent;
    float max_imposters_percent;
};

class DialogueCommandDispatcher {
public:
    DialogueCommandDispatcher(Inventory& inventory, OccupantsRuntime& occupants,
                              std::function<std::int32_t()> current_day = {},
                              std::function<LetInInputs(std::int32_t)> let_in_inputs = {},
                              std::function<void(std::int32_t)> show_exile_dialog = {},
                              CourierService* courier = nullptr,
                              std::function<void(std::int32_t)> exile_by_fema = {},
                              std::function<void(std::int32_t)> kill_room_service = {});

    void dispatch(const DialogueCommand& command);

    // The full list is checked for unsupported commands before the first
    // mutation. Runtime failures from a supported command still propagate.
    void dispatch_all(const std::vector<DialogueCommand>& commands);

private:
    static void validate_supported(const DialogueCommand& command);
    void validate_ready(const DialogueCommand& command) const;
    void let_in(std::int32_t character_type, bool exile_old_character);

    Inventory& inventory_;
    OccupantsRuntime& occupants_;
    std::function<std::int32_t()> current_day_;
    std::function<LetInInputs(std::int32_t)> let_in_inputs_;
    std::function<void(std::int32_t)> show_exile_dialog_;
    CourierService* courier_;
    std::function<void(std::int32_t)> exile_by_fema_;
    std::function<void(std::int32_t)> kill_room_service_;
};

} // namespace ninah
