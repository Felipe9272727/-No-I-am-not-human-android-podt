#pragma once
#include "ninah/command_input.hpp"
#include "ninah/dialogue_services.hpp"
#include "ninah/options.hpp"
#include <functional>
#include <string>
namespace ninah {
// Owns the Yarn handle; referenced gameplay services must outlive the session.
// Calls are serialized and non-reentrant, as required by the underlying C ABI.
class DialogueSession {
public:
 DialogueSession(const std::string& program,const std::string& metadata,
                 DialogueServices&,DialogueCommandDispatcher&,const CharacterCatalog&,OptionCallbacks selection_callbacks={},
                 std::function<bool(const std::string&)> immediate_command_handler={});
 ~DialogueSession();
 DialogueSession(const DialogueSession&)=delete;
 DialogueSession& operator=(const DialogueSession&)=delete;
 std::string start(const std::string& node);
 std::string advance();
 std::string choose(std::size_t index);
 // Only call after the Android host has actually performed the returned command.
 // The expected text rejects acknowledgements from an older asynchronous request.
 std::string acknowledge_host_command(const std::string& expected_command);
 // Saves the dialogue cursor and visible event only. The host must checkpoint
 // inventory, occupants and all other gameplay state in the same transaction.
 // Restoration invokes no gameplay callbacks and replays no emitted command.
 std::string dump_snapshot()const;
 void restore_snapshot(const std::string&);
 bool requires_host_command()const noexcept{return needs_ack_;}
 bool failed()const noexcept{return failed_;}
 const std::string& current_event()const noexcept{return current_;}
private:
 std::string drive(char*);
 void require_usable()const;
 NinahYarnHandle* vm_=nullptr;
 DialogueCommandDispatcher& commands_;
 const CharacterCatalog& characters_;
 OptionCallbacks selection_callbacks_;
 // Return true only after completing an implemented, synchronous effect.
 // Return false without effects to leave an asynchronous command to the host.
 std::function<bool(const std::string&)> immediate_command_handler_;
 std::string program_text_,metadata_text_,metadata_fingerprint_;
 std::string current_;
 bool started_=false,needs_ack_=false,failed_=false;
};
}
