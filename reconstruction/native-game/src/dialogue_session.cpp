#include "ninah/dialogue_session.hpp"
#include "../third_party/nlohmann/json.hpp"
#include <stdexcept>
#include <memory>
#include <utility>
#include <cstdint>
#include <iomanip>
#include <sstream>
namespace ninah {
namespace {
std::string take(char* raw){
 std::unique_ptr<char,decltype(&ninah_yarn_free_string)> owner(raw,ninah_yarn_free_string);
 if(!owner)throw std::runtime_error("Yarn bridge returned no event");
 return std::string(owner.get());
}
// A portable corruption checksum, not an authentication mechanism.
std::string checksum(const std::string& text){
 std::uint64_t value=14695981039346656037ULL;
 for(const unsigned char c:text){value^=c;value*=1099511628211ULL;}
 std::ostringstream out;out<<std::hex<<std::setw(16)<<std::setfill('0')<<value;return out.str();
}
void require_strings(const nlohmann::json& value){
 if(!value.is_array()||value.size()>4096)throw std::invalid_argument("invalid saved substitutions");
 for(const auto& entry:value)if(!entry.is_string())throw std::invalid_argument("saved substitution must be a string");
}
void check_metadata(const nlohmann::json& event,const nlohmann::json& metadata){
 const auto id=event.at("line_id").get<std::string>();
 require_strings(event.at("substitutions"));
 nlohmann::json expected=nullptr;
 const auto& rows=metadata.at("line_metadata");
 if(rows.contains(id)){
  const auto& source=rows.at(id).at("metadata").at(0);
  expected={{"node_name",source.at("node_name")},{"tags",source.at("tags")}};
 }
 if(event.at("metadata")!=expected)throw std::invalid_argument("saved line metadata differs from loaded source");
}
}
DialogueSession::DialogueSession(const std::string& program,const std::string& metadata,
 DialogueServices& services,DialogueCommandDispatcher& commands,const CharacterCatalog& characters,OptionCallbacks selection_callbacks,
 std::function<bool(const std::string&)> immediate_command_handler):commands_(commands),characters_(characters),selection_callbacks_(std::move(selection_callbacks)),immediate_command_handler_(std::move(immediate_command_handler)),program_text_(program),metadata_text_(metadata),metadata_fingerprint_(checksum(nlohmann::json::parse(metadata).dump())){
 char* error=nullptr;vm_=ninah_yarn_create(program.c_str(),&services,DialogueServices::callback,&error);
 if(!vm_)throw std::runtime_error(error?take(error):"cannot create Yarn runtime");
 if(!ninah_yarn_load_line_metadata(vm_,metadata.c_str(),&error)){
  ninah_yarn_destroy(vm_);vm_=nullptr;throw std::runtime_error(error?take(error):"cannot load original metadata");
 }
}
DialogueSession::~DialogueSession(){ninah_yarn_destroy(vm_);}
void DialogueSession::require_usable()const{if(failed_)throw std::logic_error("failed dialogue session requires explicit recovery");}
std::string DialogueSession::drive(char* raw){
 try{
  for(std::size_t count=0;;++count){
   auto event=nlohmann::json::parse(take(std::exchange(raw,nullptr)));
   if(event.at("type")!="command"){
    needs_ack_=false;if(event.at("type")=="error")failed_=true;
    current_=event.dump();return current_;
   }
   const auto text=event.at("command").get<std::string>();
   const auto command=decode_gameplay_command(text,characters_);
   if(count>=1024)throw std::runtime_error("synchronous command budget exceeded");
   if(std::holds_alternative<UnsupportedDialogueCommand>(command)){
    if(immediate_command_handler_&&immediate_command_handler_(text)){
     raw=ninah_yarn_advance(vm_);continue;
    }
    needs_ack_=true;event["requires_host"]=true;current_=event.dump();return current_;
   }
   commands_.dispatch(command);raw=ninah_yarn_advance(vm_);
  }
 }catch(const std::exception& e){
  if(raw)ninah_yarn_free_string(raw);
  failed_=true;needs_ack_=false;current_=nlohmann::json({{"type","error"},{"error",e.what()},{"session_failed",true}}).dump();return current_;
 }
}
std::string DialogueSession::start(const std::string& node){
 require_usable();if(started_&&nlohmann::json::parse(current_).at("type")!="stopped")throw std::logic_error("dialogue is still active");
 started_=true;return drive(ninah_yarn_start(vm_,node.c_str()));
}
std::string DialogueSession::advance(){
 require_usable();if(!started_)throw std::logic_error("dialogue was not started");
 const auto event=nlohmann::json::parse(current_);
 if(event.at("type")=="stopped")return current_;
 if(event.at("type")!="line")throw std::logic_error("choose an option or perform the pending host command first");
 return drive(ninah_yarn_advance(vm_));
}
std::string DialogueSession::choose(std::size_t index){
 require_usable();if(!started_)throw std::logic_error("dialogue was not started");
 const auto event=nlohmann::json::parse(current_);
 if(event.at("type")!="options")throw std::logic_error("no pending dialogue choices");
 const auto& options=event.at("options");if(index>=options.size()||!options.at(index).at("enabled").get<bool>())throw std::invalid_argument("unavailable dialogue choice");
 const auto policy=resolve_option_policy(options.at(index).at("line_id").get<std::string>());
 if(!policy.line_id_known)throw std::logic_error("original choice metadata unavailable");
 for(const auto callback:policy.callbacks_in_registration_order){
  const bool ready=callback==OptionCallback::EnergyConsumed?static_cast<bool>(selection_callbacks_.energy_consumed):callback==OptionCallback::DayDialogSelected?static_cast<bool>(selection_callbacks_.day_dialog_selected):static_cast<bool>(selection_callbacks_.were_bad_boy);
  if(!ready)throw std::logic_error("choice gameplay subscriber is required");
 }
 try{dispatch_option_callbacks(policy,selection_callbacks_);}catch(...){failed_=true;throw;}
 return drive(ninah_yarn_choose(vm_,index));
}
std::string DialogueSession::acknowledge_host_command(const std::string& expected){
 require_usable();if(!needs_ack_)throw std::logic_error("no pending host command");
 if(nlohmann::json::parse(current_).at("command")!=expected)throw std::invalid_argument("stale host command acknowledgement");
 needs_ack_=false;return drive(ninah_yarn_advance(vm_));
}
std::string DialogueSession::dump_snapshot()const{
 require_usable();char* error=nullptr;
 char* raw=ninah_yarn_dump_snapshot(vm_,&error);
 if(!raw)throw std::runtime_error(error?take(error):"cannot save Yarn runtime");
 const auto runtime=nlohmann::json::parse(take(raw));
 const nlohmann::json payload={{"runtime",runtime},{"event",started_?nlohmann::json::parse(current_):nlohmann::json(nullptr)},
  {"started",started_},{"needs_ack",needs_ack_},{"metadata_fingerprint",metadata_fingerprint_}};
 return nlohmann::json({{"format","ninah-dialogue-session-snapshot"},{"version",1},{"payload",payload},{"checksum_fnv1a64",checksum(payload.dump())}}).dump();
}
void DialogueSession::restore_snapshot(const std::string& text){
 // Prepare and validate everything before changing the VM. The VM restore is
 // atomic; subsequent swaps cannot allocate or call an external subscriber.
 if(text.size()>32*1024*1024)throw std::invalid_argument("dialogue snapshot too large");
 const auto envelope=nlohmann::json::parse(text);
 if(envelope.at("format")!="ninah-dialogue-session-snapshot"||envelope.at("version")!=1)
  throw std::invalid_argument("unsupported dialogue snapshot version");
 const auto& payload=envelope.at("payload");
 if(envelope.at("checksum_fnv1a64")!=checksum(payload.dump()))throw std::invalid_argument("dialogue snapshot checksum mismatch");
 if(payload.at("metadata_fingerprint")!=metadata_fingerprint_)throw std::invalid_argument("dialogue metadata changed");
 const bool started=payload.at("started").get<bool>(),ack=payload.at("needs_ack").get<bool>();
 const auto& runtime=payload.at("runtime");const auto& state=runtime.at("state");
 const auto& event=payload.at("event");
 const auto node=state.at("node").get<std::string>();
 const auto pc=state.at("pc").get<std::size_t>();
 const bool halted=state.at("halted").get<bool>();
 if(!started){
  if(!event.is_null()||ack||!node.empty()||pc!=0||!halted||!state.at("options").empty())
   throw std::invalid_argument("invalid unstarted dialogue snapshot");
 }else{
  const auto type=event.at("type").get<std::string>();
  if(type!="line"&&type!="command"&&type!="options"&&type!="stopped")throw std::invalid_argument("invalid saved dialogue event");
  if(ack!=(type=="command")||halted!=(type=="stopped"))throw std::invalid_argument("saved dialogue event disagrees with runtime state");
  const auto program=nlohmann::json::parse(program_text_);
  const auto& instructions=program.at("nodes").at(node).at("instructions");
  if(type!="stopped"){
   if(pc==0||pc>instructions.size())throw std::invalid_argument("invalid saved event cursor");
   const auto& instruction=instructions.at(pc-1);
   const int expected=type=="line"?2:type=="command"?3:5;
   if(instruction.at("opcode")!=expected)throw std::invalid_argument("saved event disagrees with original instruction");
   if(type=="line"&&instruction.at("operands").at(0)!=event.at("line_id"))throw std::invalid_argument("saved line disagrees with original instruction");
   if(type=="command"){
    if(event.at("command").get<std::string>().empty()||event.at("requires_host")!=true)throw std::invalid_argument("invalid pending host command");
    const auto& operands=instruction.at("operands");
    if((operands.size()<2||operands.at(1)==0)&&operands.at(0)!=event.at("command"))throw std::invalid_argument("saved command differs from original instruction");
   }
  }
  const auto metadata=nlohmann::json::parse(metadata_text_);
  if(type=="line")check_metadata(event,metadata);
  if(type=="options"){
   const auto& visible=event.at("options");const auto& pending=state.at("options");
   if(!visible.is_array()||visible.empty()||visible.size()!=pending.size())throw std::invalid_argument("saved choices disagree with runtime");
   for(std::size_t i=0;i<visible.size();++i){
    const auto& a=visible.at(i);const auto& b=pending.at(i);
    check_metadata(a,metadata);
    if(a.at("line_id")!=b.at("line").at("string_id")||a.at("substitutions")!=b.at("line").at("substitutions")||a.at("destination")!=b.at("destination")||a.at("enabled")!=b.at("enabled"))
     throw std::invalid_argument("saved choice differs from pending runtime choice");
   }
  }
 }
 auto current=started?event.dump():std::string{};const auto runtime_text=runtime.dump();char* error=nullptr;
 if(!ninah_yarn_restore_snapshot(vm_,runtime_text.c_str(),&error))throw std::invalid_argument(error?take(error):"cannot restore Yarn runtime");
 current_.swap(current);started_=started;needs_ack_=ack;failed_=false;
}
}
