#include "ninah/arrivals.hpp"
#include "production_characters.hpp"

#include <cassert>
#include <stdexcept>

using namespace ninah;

int main() {
    const auto catalog = production::character_catalog();
    const auto day_zero = preset_visits_for_day(catalog, 0);
    assert(day_zero.size() == 1);
    assert(day_zero[0].character_id == catalog.parse_name("Neighbour", false));
    assert(day_zero[0].guest_number == 1);

    const auto day_one = preset_visits_for_day(catalog, 1);
    assert(day_one.size() == 3);
    assert(day_one[0].character_id == catalog.parse_name("Daughter", false));
    assert(day_one[0].guest_number == 1);
    assert(day_one[1].character_id == catalog.parse_name("Esenin", false));
    assert(day_one[1].guest_number == 2);
    assert(day_one[2].character_id == catalog.parse_name("Anxiety", false));
    assert(day_one[2].guest_number == 3);
    assert(preset_visits_for_day(catalog, 2).empty());

    bool rejected_negative_day = false;
    try {
        (void)preset_visits_for_day(catalog, -1);
    } catch (const std::invalid_argument&) {
        rejected_negative_day = true;
    }
    assert(rejected_negative_day);
}
