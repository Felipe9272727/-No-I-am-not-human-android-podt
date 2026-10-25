#include "ninah/phone.hpp"
#include <stdexcept>
#include <utility>
namespace ninah { namespace {
bool valid_number(const std::string& s){if(s.size()!=6)return false;for(char c:s)if(c<'0'||c>'9')return false;return true;}
char digit(std::int32_t n){if(n<0||n>9)throw std::out_of_range("phone digit outside 0..9");return static_cast<char>('0'+n);}
}
bool PhoneNumbers::contains(PhoneSubscriber s)const noexcept{for(auto& e:entries)if(e.subscriber==s)return true;return false;}
const std::string* PhoneNumbers::find(PhoneSubscriber s)const noexcept{for(auto& e:entries)if(e.subscriber==s)return &e.number;return nullptr;}
void PhoneNumbers::add(PhoneSubscriber s,std::string n){if(contains(s))throw std::logic_error("Dictionary.Add duplicate phone subscriber key");entries.push_back({s,std::move(n)});}
PhoneNumberService::PhoneNumberService(FixedPhoneNumbers f,PhoneRandom r):fixed_(std::move(f)),random_(std::move(r)){if(!random_.range_int||!random_.range_float)throw std::invalid_argument("explicit RNG callbacks are required");for(auto& x:fixed_)if(!valid_number(x.second))throw std::invalid_argument("fixed phone number must be six digits");}
std::int32_t PhoneNumberService::int_range(std::int32_t a,std::int32_t b)const{auto x=random_.range_int(a,b);if(x<a||x>=b)throw std::out_of_range("integer RNG violates Unity Range bounds");return x;}
float PhoneNumberService::float_range(float a,float b)const{auto x=random_.range_float(a,b);if(x<a||x>b)throw std::out_of_range("float RNG violates Unity Range bounds");return x;}
std::string PhoneNumberService::generate_phone_number(const PhoneNumbers& current)const{for(;;){const auto pattern=int_range(0,5);std::string n;n.reserve(6);for(int p=0;p<6;++p){int source=-1;if(pattern==0&&p==5)source=3;else if(pattern==1&&p==3)source=0;else if(pattern==2&&p==2)source=0;else if(pattern==3&&p==5)source=0;else if(pattern==4&&p==5)source=1;if(source>=0){n.push_back(n.at(static_cast<std::size_t>(source)));continue;}if(pattern==4&&p==4&&float_range(0.f,1.f)<0.66f){int prev=n.at(1)-'0';int delta=int_range(0,2)==1?1:-1;n.push_back(digit((prev+delta+10)%10));continue;}n.push_back(digit(int_range(0,10)));}if(!valid_number(n))throw std::logic_error("generator did not produce six digits");bool duplicate=false;for(auto& e:current.entries)if(e.number==n){duplicate=true;break;}if(duplicate||n.compare(0,3,n,3,3)==0)continue;return n;}}
void PhoneNumberService::generate_numbers(PhoneNumbers& saved)const{for(int raw=1;raw<=15;++raw){auto s=static_cast<PhoneSubscriber>(raw);auto f=fixed_.find(s);if(f!=fixed_.end())saved.add(s,f->second);else saved.add(s,generate_phone_number(saved));}}
std::string PhoneNumberService::get_number_by_subscriber(const PhoneNumbers& saved,PhoneSubscriber s){auto p=saved.find(s);return p?*p:"000000";}
bool PhoneNumberService::try_get_subscriber_by_phone(const PhoneNumbers& saved,const std::string& n,PhoneSubscriber& out){for(auto& e:saved.entries)if(e.number==n){out=e.subscriber;return true;}out=PhoneSubscriber::None;return false;}
}
