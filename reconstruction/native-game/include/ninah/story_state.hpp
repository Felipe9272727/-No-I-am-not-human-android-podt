#pragma once

#include <cstdint>
#include <functional>
#include <optional>
#include <stdexcept>
#include <string_view>
#include <vector>

namespace ninah {

// Models the managed NullReferenceException behavior at a missing required
// service/reference boundary in the recovered Yarn command adapters.
class NullReferenceError final : public std::runtime_error {
 public:
  explicit NullReferenceError(const char* source);
};

// Non-owning pointers to state written by GameplayEndingManager's event
// handlers and GameplayEndingCultists' save-data handlers. The caller owns
// their storage and must keep it alive for this adapter's lifetime.
struct StoryStateRefs {
  // GameplayEndingManagerSaveData.HasBegunCultists / SavedCultists.
  bool* has_begun_cultists = nullptr;
  bool* saved_cultists = nullptr;
  // DialogSaveData.EverRudeToFema.
  bool* ever_rude_to_fema = nullptr;
  // GameplayEndingDeath._isReadyToEnd.
  bool* death_is_ready = nullptr;
  // GameplayEndingMushroom._cartoonUnlocked.
  bool* mushroom_cartoon_unlocked = nullptr;
  // GameplayEndingVigilante._isRevealed.
  bool* vigilante_revealed = nullptr;
};

struct StoryStateQueries {
  // Optional managed delegate adapters. Missing delegates return false, as
  // the recovered methods do when their corresponding delegate is null.
  std::function<bool()> mushroom_condition;
  std::function<bool(std::int32_t)> seen_dream;
  std::function<bool()> ever_completed;

  // GetAchievement invokes SteamAchievements.Unlock(raw, false).
  std::function<void(std::string_view, bool)> required_achievement;
};

class StoryState final {
 public:
  using EndingSubscriber = std::function<void()>;

  explicit StoryState(StoryStateRefs refs = {}, StoryStateQueries queries = {});

  void on_begin_cultists();
  void on_save_cultists();
  void on_unlock_death_ending();
  void on_unlock_mushroom_ending();
  void on_vigilante_reveals_player();
  void on_were_bad_boy(std::optional<std::int32_t> current_character_type);

  [[nodiscard]] bool has_completed_mushroom_condition() const;
  [[nodiscard]] bool has_seen_dream(std::int32_t dream_id) const;
  [[nodiscard]] bool is_ever_completed_game() const;
  void get_achievement(std::string_view achievement_raw) const;

  // Mirrors the zero-argument Yarn Ending command. Subscribers run
  // synchronously in registration order.
  void subscribe_ending(EndingSubscriber subscriber);
  void ending() const;

 private:
  static bool& require(bool* ref, const char* source);

  StoryStateRefs refs_;
  StoryStateQueries queries_;
  std::vector<EndingSubscriber> ending_subscribers_;
};

}  // namespace ninah
