#include "ninah/story_state.hpp"

#include <cassert>
#include <string>
#include <vector>

using ninah::NullReferenceError;
using ninah::StoryState;
using ninah::StoryStateQueries;
using ninah::StoryStateRefs;

int main() {
  bool begun = false;
  bool saved = false;
  bool rude = false;
  bool death = false;
  bool mushroom = false;
  bool vigilante = false;
  StoryState state({&begun, &saved, &rude, &death, &mushroom, &vigilante});

  state.on_begin_cultists();
  state.on_save_cultists();
  state.on_unlock_death_ending();
  state.on_unlock_mushroom_ending();
  state.on_vigilante_reveals_player();
  assert(begun && saved && death && mushroom && vigilante);

  state.on_were_bad_boy(2);
  assert(!rude);
  state.on_were_bad_boy(14);
  assert(rude);

  bool absent_character_threw = false;
  try {
    state.on_were_bad_boy(std::nullopt);
  } catch (const NullReferenceError&) {
    absent_character_threw = true;
  }
  assert(absent_character_threw);

  StoryState empty;
  bool missing_flag_threw = false;
  try {
    empty.on_begin_cultists();
  } catch (const NullReferenceError&) {
    missing_flag_threw = true;
  }
  assert(missing_flag_threw);

  assert(!empty.has_completed_mushroom_condition());
  assert(!empty.has_seen_dream(1));
  assert(!empty.is_ever_completed_game());

  std::string achievement;
  bool unlock_parameter = true;
  StoryStateQueries queries;
  queries.required_achievement = [&](std::string_view raw, bool parameter) {
    achievement = raw;
    unlock_parameter = parameter;
  };
  StoryState with_achievement({}, queries);
  with_achievement.get_achievement("NINAH_TEST");
  assert(achievement == "NINAH_TEST");
  assert(!unlock_parameter);

  std::vector<int> order;
  state.subscribe_ending([&] { order.push_back(1); });
  state.subscribe_ending([&] { order.push_back(2); });
  state.ending();
  assert((order == std::vector<int>{1, 2}));

  bool missing_achievement_threw = false;
  try {
    empty.get_achievement("NINAH_TEST");
  } catch (const NullReferenceError&) {
    missing_achievement_threw = true;
  }
  assert(missing_achievement_threw);
}
