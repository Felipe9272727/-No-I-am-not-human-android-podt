#include "ninah/phone.hpp"
#include "production_phone.hpp"

#include <cassert>
#include <iostream>

int main() {
    const auto fixed = ninah::production::fixed_phone_numbers();
    assert(fixed.size() == 3);
    assert(fixed.at(ninah::PhoneSubscriber::FEMA) == "000451");
    assert(fixed.at(ninah::PhoneSubscriber::Psychics) == "777460");
    assert(fixed.at(ninah::PhoneSubscriber::PhoneRoulette) == "891533");

    ninah::PhoneNumbers numbers;
    for (const auto& entry : fixed) {
        numbers.add(entry.first, entry.second);
    }
    assert(ninah::PhoneNumberService::get_number_by_subscriber(
               numbers, ninah::PhoneSubscriber::FEMA) == "000451");
    ninah::PhoneSubscriber subscriber = ninah::PhoneSubscriber::None;
    assert(ninah::PhoneNumberService::try_get_subscriber_by_phone(
        numbers, "891533", subscriber));
    assert(subscriber == ninah::PhoneSubscriber::PhoneRoulette);
    std::cout << "Verified production phone provider values passed\n";
}
