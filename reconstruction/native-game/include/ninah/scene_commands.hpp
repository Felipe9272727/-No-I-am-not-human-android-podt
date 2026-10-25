#pragma once
#include "ninah/characters.hpp"
#include "ninah/presentation.hpp"
#include "ninah/story_state.hpp"
#include <functional>
#include <string>
namespace ninah {
struct SceneCommandHooks {
 // Original ICharactersManager operation required by SetupGun(true) and
 // DontSetupGun. It is separate from the GunSetUp visibility event.
 std::function<void(bool)> gun_state_selected;
};
// Synchronous scene/story command adapter for DialogueSession. False means
// no effect was applied and the command must remain a pending host request.
// This updates source render data; the Android host must render those packets.
class SceneCommandRouter {
public:
 SceneCommandRouter(const CharacterCatalog&,PresentationState* = nullptr,
                    StoryState* = nullptr,SceneCommandHooks = {});
 bool dispatch(const std::string&);
private:
 const CharacterCatalog& characters_;
 PresentationState* presentation_;
 StoryState* story_;
 SceneCommandHooks hooks_;
};
}
