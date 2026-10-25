#include "ninah/courier.hpp"

#include <algorithm>
#include <charconv>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <string_view>

namespace ninah {
namespace {
constexpr std::pair<std::string_view, std::int32_t> kConsumableNames[] = {
    {"Bobeer", 0}, {"Cigarette", 1}, {"Coffee", 2}, {"Enerjeka", 3},
    {"Pills", 4}, {"Mushroom", 5}, {"CatFood", 6}, {"Povistka", 7},
    {"Kombucha", 8}, {"Photo", 9}, {"Cockroach", 100},
};

std::string_view trim(std::string_view s) {
    while (!s.empty() && (s.front() == ' ' || s.front() == '\t' ||
                          s.front() == '\r' || s.front() == '\n')) s.remove_prefix(1);
    while (!s.empty() && (s.back() == ' ' || s.back() == '\t' ||
                          s.back() == '\r' || s.back() == '\n')) s.remove_suffix(1);
    return s;
}
char ascii_lower(char c) {
    return c >= 'A' && c <= 'Z' ? static_cast<char>(c + ('a' - 'A')) : c;
}
bool iequals(std::string_view a, std::string_view b) {
    if (a.size() != b.size()) return false;
    for (std::size_t i = 0; i < a.size(); ++i)
        if (ascii_lower(a[i]) != ascii_lower(b[i])) return false;
    return true;
}
std::int32_t parse_enum_value(std::string_view token) {
    token = trim(token);
    for (const auto& item : kConsumableNames)
        if (iequals(token, item.first)) return item.second;
    std::int32_t value = 0;
    const bool explicit_plus = !token.empty() && token.front() == '+';
    if (explicit_plus) token.remove_prefix(1);
    const char* begin = token.data();
    const char* end = begin + token.size();
    const auto parsed = std::from_chars(begin, end, value, 10);
    if (!token.empty() && parsed.ec == std::errc{} && parsed.ptr == end &&
        (!explicit_plus || value >= 0)) return value;
    throw std::invalid_argument("Enum.Parse failed for EConsumable: " + std::string(token));
}
std::int32_t unchecked_add(std::int32_t a, std::int32_t b) noexcept {
    const auto bits = static_cast<std::uint32_t>(a) + static_cast<std::uint32_t>(b);
    std::int32_t result;
    std::memcpy(&result, &bits, sizeof(result));
    return result;
}
std::string lower_ascii(std::string s) {
    for (auto& c : s) c = ascii_lower(c);
    return s;
}
} // namespace

Consumable parse_consumable_enum(const std::string& raw) {
    std::string_view input(raw);
    input = trim(input);
    if (input.empty()) throw std::invalid_argument("Enum.Parse failed for EConsumable: empty value");
    // Enum.Parse accepts comma-separated constants even when the enum is not
    // marked Flags; the underlying integral values are ORed by the CLR.
    std::int32_t combined = 0;
    std::size_t start = 0;
    while (start <= input.size()) {
        const auto comma = input.find(',', start);
        const auto end = comma == std::string_view::npos ? input.size() : comma;
        const auto part = input.substr(start, end - start);
        const auto value = parse_enum_value(part);
        combined = static_cast<std::int32_t>(static_cast<std::uint32_t>(combined) |
                                             static_cast<std::uint32_t>(value));
        if (comma == std::string_view::npos) break;
        start = comma + 1;
    }
    return static_cast<Consumable>(combined);
}

std::string consumable_enum_name(Consumable item) {
    const auto raw = static_cast<std::int32_t>(item);
    for (const auto& value : kConsumableNames)
        if (raw == value.second) return std::string(value.first);
    return std::to_string(raw);
}

ConsumablesDeficitService::ConsumablesDeficitService(
    Inventory& inventory, CurrentDay current_day,
    ConsumablesDeficitSaveRef save, OtherGameDeficitDataRef other_game_data,
    RandomRange random_range)
    : inventory_(inventory), current_day_(std::move(current_day)), save_(save),
      other_game_data_(std::move(other_game_data)),
      random_range_(std::move(random_range)) {}

std::vector<Consumable> ConsumablesDeficitService::eligible_items() const {
    if (!other_game_data_.items) return {};
    std::vector<Consumable> eligible;
    eligible.reserve(other_game_data_.items->size());
    for (const auto& target : *other_game_data_.items) {
        // The recovered predicate is target count >= current inventory count.
        if (target.target_count >= inventory_.count(target.item))
            eligible.push_back(target.item);
    }
    return eligible;
}

bool ConsumablesDeficitService::is_need_to_get_item() const {
    if (!current_day_ || !save_.deficit_item_day || !other_game_data_.items)
        return false;
    if (current_day_() < *save_.deficit_item_day) return false;
    return !eligible_items().empty();
}

Consumable ConsumablesDeficitService::get_deficit_item() const {
    const auto items = eligible_items();
    // RandomElementFromCollectionExtension returns default(T) for an empty list.
    if (items.empty()) return static_cast<Consumable>(0);
    if (!random_range_)
        throw std::logic_error("Unity Random.Range provider required for deficit selection");
    if (items.size() > static_cast<std::size_t>(std::numeric_limits<std::int32_t>::max()))
        throw std::length_error("deficit selection exceeds Int32 collection size");
    const auto index = random_range_(0, static_cast<std::int32_t>(items.size()));
    if (index < 0 || static_cast<std::size_t>(index) >= items.size())
        throw std::out_of_range("Unity Random.Range returned an invalid collection index");
    return items[static_cast<std::size_t>(index)];
}

void ConsumablesDeficitService::update_deficit_day() const {
    if (!current_day_ || !save_.deficit_item_day || !other_game_data_.get_random_days_count)
        return;
    *save_.deficit_item_day = unchecked_add(current_day_(),
                                            other_game_data_.get_random_days_count());
}

CourierService::CourierService(DayNightCourierRefs day_night,
                               CourierDialogHooks dialog,
                               ConsumablesDeficitService* deficit)
    : day_night_(std::move(day_night)), dialog_(std::move(dialog)),
      deficit_(deficit) {}

bool CourierService::can_order_courier() const {
    if (!day_night_.current_day || !day_night_.last_courier_ordered_day) return false;
    // DayNightController.OnCouldOrderCourier: lastCourierOrderedDay + 2 < day.
    return unchecked_add(day_night_.last_courier_ordered_day(), 2) <
           day_night_.current_day();
}

std::string CourierService::get_courier_order() const {
    std::optional<CourierOrder> order;
    for (const auto& subscriber : dialog_.get_order_subscribers) {
        if (!subscriber) continue;
        order = subscriber(); // CLR Func multicast returns the final subscriber's value.
    }
    // The source wrapper constructs DialogCourierOrderData(Bobeer, 1) when
    // the delegate is absent or returns null. No inventory effect occurs here.
    const CourierOrder display = order.value_or(CourierOrder{static_cast<Consumable>(0), 1});
    if (!dialog_.localize)
        throw std::logic_error("LocalizationExtension UI provider required for GetCourierOrder");
    const auto key = "consumable_" + lower_ascii(consumable_enum_name(display.item)) + "_name";
    return dialog_.localize(key, "UI") + " (x" + std::to_string(display.count) + ")";
}

void CourierService::order_courier(const std::string& raw_consumable,
                                   std::int32_t count) const {
    const auto item = parse_consumable_enum(raw_consumable);
    // Source OrderCourier does not call CanOrderCourier or alter the count.
    for (const auto& subscriber : dialog_.ordered_subscribers)
        if (subscriber) subscriber(item, count);
}

void CourierService::update_deficit_day() const {
    if (deficit_) deficit_->update_deficit_day();
}

bool CourierService::is_need_to_get_deficit_item() const {
    return deficit_ && deficit_->is_need_to_get_item();
}

std::string CourierService::peek_deficit_item() const {
    if (!deficit_) return {};
    return consumable_enum_name(deficit_->get_deficit_item());
}

} // namespace ninah
