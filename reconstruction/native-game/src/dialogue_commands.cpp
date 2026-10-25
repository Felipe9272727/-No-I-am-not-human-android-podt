#include "ninah/dialogue_commands.hpp"

#include <stdexcept>
#include <utility>

namespace ninah {

DialogueCommandDispatcher::DialogueCommandDispatcher(
    Inventory& inventory, OccupantsRuntime& occupants,
    std::function<std::int32_t()> current_day,
    std::function<LetInInputs(std::int32_t)> let_in_inputs,
    std::function<void(std::int32_t)> show_exile_dialog,
    CourierService* courier,
    std::function<void(std::int32_t)> exile_by_fema,
    std::function<void(std::int32_t)> kill_room_service)
    : inventory_(inventory), occupants_(occupants),
      current_day_(std::move(current_day)),
      let_in_inputs_(std::move(let_in_inputs)),
      show_exile_dialog_(std::move(show_exile_dialog)), courier_(courier),
      exile_by_fema_(std::move(exile_by_fema)),
      kill_room_service_(std::move(kill_room_service)) {}

void DialogueCommandDispatcher::validate_supported(
    const DialogueCommand& command) {
    if (const auto* unsupported =
            std::get_if<UnsupportedDialogueCommand>(&command)) {
        throw std::invalid_argument("unsupported Yarn command: " +
                                    unsupported->name);
    }
}

void DialogueCommandDispatcher::validate_ready(
    const DialogueCommand& command) const {
    if ((std::holds_alternative<LetCharacterInCommand>(command) ||
         std::holds_alternative<AggressiveLetInCommand>(command)) &&
        !let_in_inputs_) {
        throw std::logic_error("LetIn production input provider is required");
    }
    if (const auto* exile = std::get_if<ExileCharacterCommand>(&command)) {
        if (exile->show_in_dialog && !show_exile_dialog_) {
            throw std::logic_error("ExileCharacter dialog callback is required");
        }
    }
    if (std::holds_alternative<ExileAfterTomorrowCommand>(command) &&
        !current_day_) {
        throw std::logic_error("ExileAfterTomorrow current-day callback is required");
    }
    if ((std::holds_alternative<OrderCourierCommand>(command) ||
         std::holds_alternative<UpdateDeficitDayCommand>(command)) &&
        !courier_) {
        throw std::logic_error("CourierService is required for courier commands");
    }
    if (std::holds_alternative<KillRoomCommand>(command) &&
        !kill_room_service_) {
        throw std::logic_error("KillRoom room-manager callback is required");
    }
}

void DialogueCommandDispatcher::let_in(std::int32_t character_type,
                                       bool exile_old_character) {
    const auto inputs = let_in_inputs_(character_type);
    (void)occupants_.let_in(character_type, exile_old_character,
                            inputs.is_human_fema_rating,
                            inputs.character_fema_bonus,
                            inputs.min_imposters_percent,
                            inputs.max_imposters_percent, current_day_);
}

void DialogueCommandDispatcher::dispatch(const DialogueCommand& command) {
    validate_supported(command);
    validate_ready(command);
    if (const auto* get_item = std::get_if<GetItemCommand>(&command)) {
        inventory_.add(get_item->item, get_item->count);
    } else if (const auto* refuse = std::get_if<RefuseCommand>(&command)) {
        occupants_.refuse(refuse->character_type);
    } else if (const auto* kill = std::get_if<KillTomorrowCommand>(&command)) {
        occupants_.kill_tomorrow(kill->character_type);
    } else if (const auto* exile =
                   std::get_if<ExileAfterTomorrowCommand>(&command)) {
        occupants_.exile_after_tomorrow(exile->character_type, current_day_);
    } else if (const auto* let = std::get_if<LetCharacterInCommand>(&command)) {
        // The original LetCharacterIn wrapper passes false for the manager's
        // exile-old-from-place parameter.
        let_in(let->character_type, false);
    } else if (const auto* let = std::get_if<AggressiveLetInCommand>(&command)) {
        // AggressiveLetCharacterIn passes true for the same manager parameter.
        let_in(let->character_type, true);
    } else if (const auto* kill = std::get_if<KillCommand>(&command)) {
        // Yarn Kill calls Kill(CharacterSOData, isByPlayer: true).
        occupants_.kill(kill->character_type, true);
    } else if (const auto* exile =
                   std::get_if<ExileCharacterCommand>(&command)) {
        occupants_.exile(exile->character_type);
        if (exile->show_in_dialog)
            show_exile_dialog_(exile->character_type);
    } else if (const auto* order = std::get_if<OrderCourierCommand>(&command)) {
        courier_->order_courier(consumable_enum_name(order->item), order->count);
    } else if (std::holds_alternative<UpdateDeficitDayCommand>(command)) {
        courier_->update_deficit_day();
    } else if (const auto* exile = std::get_if<ExileByFEMACommand>(&command)) {
        // The source wrapper invokes a static multicast Action. Its invocation
        // is harmless when no subscriber is registered.
        if (exile_by_fema_) exile_by_fema_(exile->count);
    } else if (const auto* kill_room = std::get_if<KillRoomCommand>(&command)) {
        // KillRoom is a distinct room-manager action, not OccupantsRuntime::kill.
        kill_room_service_(kill_room->character_type);
    }
}

void DialogueCommandDispatcher::dispatch_all(
    const std::vector<DialogueCommand>& commands) {
    for (const auto& command : commands) {
        validate_supported(command);
        validate_ready(command);
    }
    for (const auto& command : commands) dispatch(command);
}

} // namespace ninah
