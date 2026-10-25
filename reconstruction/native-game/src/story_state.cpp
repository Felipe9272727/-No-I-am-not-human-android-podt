#include "ninah/story_state.hpp"

#include <string>
#include <utility>

namespace ninah {

NullReferenceError::NullReferenceError(const char* source)
    : std::runtime_error(std::string("null required story reference: ") + source) {}

StoryState::StoryState(StoryStateRefs refs, StoryStateQueries queries)
    : refs_(refs), queries_(std::move(queries)) {}

bool& StoryState::require(bool* ref, const char* source) {
  if (ref == nullptr) {
    throw NullReferenceError(source);
  }
  return *ref;
}

void StoryState::on_begin_cultists() {
  require(refs_.has_begun_cultists, "has_begun_cultists") = true;
}

void StoryState::on_save_cultists() {
  require(refs_.saved_cultists, "saved_cultists") = true;
}

void StoryState::on_unlock_death_ending() {
  require(refs_.death_is_ready, "death_is_ready") = true;
}

void StoryState::on_unlock_mushroom_ending() {
  require(refs_.mushroom_cartoon_unlocked, "mushroom_cartoon_unlocked") = true;
}

void StoryState::on_vigilante_reveals_player() {
  require(refs_.vigilante_revealed, "vigilante_revealed") = true;
}

void StoryState::on_were_bad_boy(
    std::optional<std::int32_t> current_character_type) {
  if (!current_character_type.has_value()) {
    throw NullReferenceError("current_dialog_character");
  }
  if (*current_character_type == 14) {
    require(refs_.ever_rude_to_fema, "ever_rude_to_fema") = true;
  }
}

bool StoryState::has_completed_mushroom_condition() const {
  return queries_.mushroom_condition ? queries_.mushroom_condition() : false;
}

bool StoryState::has_seen_dream(std::int32_t dream_id) const {
  return queries_.seen_dream ? queries_.seen_dream(dream_id) : false;
}

bool StoryState::is_ever_completed_game() const {
  return queries_.ever_completed ? queries_.ever_completed() : false;
}

void StoryState::get_achievement(std::string_view achievement_raw) const {
  if (!queries_.required_achievement) {
    throw NullReferenceError("required_achievement");
  }
  queries_.required_achievement(achievement_raw, false);
}

void StoryState::subscribe_ending(EndingSubscriber subscriber) {
  ending_subscribers_.push_back(std::move(subscriber));
}

void StoryState::ending() const {
  // C# multicast delegates invoke a snapshot. This also permits a callback to
  // register another subscriber without invalidating the current dispatch.
  const auto subscribers = ending_subscribers_;
  for (const auto& subscriber : subscribers) {
    if (subscriber) {
      subscriber();
    }
  }
}

}  // namespace ninah
