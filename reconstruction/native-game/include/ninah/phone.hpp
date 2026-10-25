#pragma once
#include <cstdint>
#include <functional>
#include <map>
#include <string>
#include <vector>
namespace ninah {
enum class PhoneSubscriber : std::int32_t { None=0, Forrest=1, FEMA=2, Neighbour=3, Psychics=4, AURACAM=5, Extrasens=6, BestSonFamily=7, MothersHusband=8, AlkonostsHusband=9, Daughter=10, PhoneRoulette=11, AngersWife=12, FEMARecruiter=13, ForeignEmbassy=14, DaughtersFriend=15 };
struct PhoneNumberEntry { PhoneSubscriber subscriber; std::string number; };
// Insertion-ordered representation preserves Unity Dictionary enumeration order.
struct PhoneNumbers {
    std::vector<PhoneNumberEntry> entries;
    bool contains(PhoneSubscriber) const noexcept;
    const std::string* find(PhoneSubscriber) const noexcept;
    void add(PhoneSubscriber, std::string); // Dictionary.Add: duplicate key throws.
};
using FixedPhoneNumbers=std::map<PhoneSubscriber,std::string>;
struct PhoneRandom {
    std::function<std::int32_t(std::int32_t,std::int32_t)> range_int;
    std::function<float(float,float)> range_float;
};
class PhoneNumberService {
public:
    PhoneNumberService(FixedPhoneNumbers,PhoneRandom);
    void generate_numbers(PhoneNumbers&) const;
    std::string generate_phone_number(const PhoneNumbers&) const;
    static std::string get_number_by_subscriber(const PhoneNumbers&,PhoneSubscriber);
    static bool try_get_subscriber_by_phone(const PhoneNumbers&,const std::string&,PhoneSubscriber&);
private:
    std::int32_t int_range(std::int32_t,std::int32_t) const;
    float float_range(float,float) const;
    FixedPhoneNumbers fixed_; PhoneRandom random_;
};
}
