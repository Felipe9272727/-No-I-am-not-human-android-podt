#include "ninah/phone.hpp"
#include <cassert>
#include <deque>
#include <iostream>
#include <stdexcept>
struct ScriptedRng { std::deque<int> ints; std::deque<float> floats; int calls=0; int get(int a,int b){++calls;if(ints.empty())throw std::runtime_error("unexpected int RNG");int x=ints.front();ints.pop_front();assert(x>=a&&x<b);return x;} float get(float a,float b){if(floats.empty())throw std::runtime_error("unexpected float RNG");float x=floats.front();floats.pop_front();assert(x>=a&&x<=b);return x;} ninah::PhoneRandom callbacks(){return {[this](int a,int b){return get(a,b);},[this](float a,float b){return get(a,b);}};} };
using S=ninah::PhoneSubscriber;
int main(){
 {ScriptedRng r{{0,1,2,3,4,5},{}};ninah::PhoneNumberService s({},r.callbacks());assert(s.generate_phone_number({})=="123454");}
 {ScriptedRng r{{1,4,0,1,2,3},{}};ninah::PhoneNumberService s({},r.callbacks());assert(s.generate_phone_number({})=="401423");}
 {ScriptedRng r{{2,8,9,2,3,4},{}};ninah::PhoneNumberService s({},r.callbacks());assert(s.generate_phone_number({})=="898234");}
 {ScriptedRng r{{3,1,2,3,4,5},{}};ninah::PhoneNumberService s({},r.callbacks());assert(s.generate_phone_number({})=="123451");}
 {ScriptedRng r{{4,2,7,3,4,0,1},{0.1f}};ninah::PhoneNumberService s({},r.callbacks());assert(s.generate_phone_number({})=="273467");}
 {ScriptedRng r{{3,5,5,5,5,5,0,1,2,3,4,5,1,1,2,3,4,5},{}};ninah::PhoneNumberService s({},r.callbacks());ninah::PhoneNumbers n;n.add(S::Forrest,"123454");assert(s.generate_phone_number(n)=="123145");}
 {ninah::PhoneNumbers n;n.add(S::FEMA,"000451");n.add(S::Psychics,"777460");S out=S::None;assert(ninah::PhoneNumberService::try_get_subscriber_by_phone(n,"000451",out)&&out==S::FEMA);assert(!ninah::PhoneNumberService::try_get_subscriber_by_phone(n,"451",out)&&out==S::None);n.add(S::PhoneRoulette,"000451");assert(ninah::PhoneNumberService::try_get_subscriber_by_phone(n,"000451",out)&&out==S::FEMA);assert(ninah::PhoneNumberService::get_number_by_subscriber(n,static_cast<S>(99))=="000000");}
 {ninah::PhoneNumbers n;n.add(S::Forrest,"123456");bool threw=false;try{n.add(S::Forrest,"654321");}catch(const std::logic_error&){threw=true;}assert(threw);}
 {ScriptedRng r{{0,1,2,3,4,5},{}};ninah::PhoneNumberService s({},r.callbacks());ninah::PhoneNumbers n;n.add(S::Forrest,"999999");bool threw=false;try{s.generate_numbers(n);}catch(const std::logic_error&){threw=true;}assert(threw);}
 std::cout<<"Phone patterns, retries, exact lookup and Dictionary.Add passed\n";
}
