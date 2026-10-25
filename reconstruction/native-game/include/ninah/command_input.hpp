#pragma once
#include "ninah/dialogue_commands.hpp"
#include <string>
namespace ninah {
// Decoder for the unquoted forms actually used by the recovered program.
// Unsupported command names remain typed data, never executable shell text.
DialogueCommand decode_gameplay_command(const std::string&, const CharacterCatalog&);
}
