#include "../../native-game/third_party/nlohmann/json.hpp"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>

namespace ninah::current {
std::string create(const std::string&, const std::string&);
std::string action(const std::string&);
}
using Json = nlohmann::json;

std::string read(const std::filesystem::path& path) {
  std::ifstream file(path);
  if (!file) throw std::runtime_error("missing source input");
  return {std::istreambuf_iterator<char>(file), {}};
}
Json call(const Json& action) {
  auto result = Json::parse(ninah::current::action(action.dump()));
  assert(result.at("type") == "state");
  return result;
}
Json act(const Json& action) {
  auto result = call(action);
  assert(result.at("error").is_null());
  return result;
}
bool active_object(const Json& state, const std::string& name) {
  for (const auto& object : state.at("room_objects"))
    if (object.at("name") == name) return object.at("active").get<bool>();
  return false;
}
Json admit_neighbour(Json state, std::size_t entrance_branch) {
  state = act({{"action", "campaign_tick"}, {"elapsed_ms", 999}});
  assert(state.at("campaign").at("door_waiting") == false);
  state = act({{"action", "campaign_tick"}, {"elapsed_ms", 1000}});
  assert(state.at("campaign").at("door_waiting") == true);
  state = act({{"action", "open_door"}});
  assert(state.at("view_mode") == "room" && state.at("room") == 5);
  assert(state.at("dialogue").at("line_id") == "line:entrance_neighbour_0_054308e");
  const auto first_line = state.at("dialogue");
  auto blocked_exit = call({{"action", "enter_world"}});
  assert(!blocked_exit.at("error").is_null());
  assert(blocked_exit.at("view_mode") == "room" && blocked_exit.at("dialogue") == first_line);
  state = act({{"action", "save"}});
  state = act({{"action", "advance"}});
  assert(state.at("dialogue").at("type") == "options");
  state = act({{"action", "load"}});
  assert(state.at("dialogue") == first_line);
  state = act({{"action", "advance"}});
  const auto options = state.at("dialogue").at("options");
  assert(options.size() >= 2 && options.at(0).at("enabled") && options.at(1).at("enabled"));
  assert(entrance_branch < options.size());
  state = act({{"action", "choose"}, {"index", entrance_branch}});
  for (int i = 0; i < 100 && !state.at("campaign").at("neighbour_inside").get<bool>(); ++i) {
    const auto event = state.at("dialogue");
    if (event.is_null()) break;
    const auto type = event.at("type").get<std::string>();
    if (type == "line") state = act({{"action", "advance"}});
    else if (type == "options") {
      std::size_t available = event.at("options").size();
      for (std::size_t j = 0; j < event.at("options").size(); ++j)
        if (event.at("options").at(j).at("enabled").get<bool>()) { available = j; break; }
      assert(available < event.at("options").size());
      state = act({{"action", "choose"}, {"index", available}});
    } else if (type == "stopped") break;
    else assert(false && "unexpected entrance dialogue event");
  }
  assert(state.at("phase") == "playing");
  assert(state.at("campaign").at("neighbour_inside") == true);
  assert(state.at("campaign").at("neighbour_can_talk") == false);
  assert(state.at("campaign").at("neighbour_room") == 0);
  assert(state.at("campaign").at("inside_occupant_types").size() == 1);
  assert(state.at("campaign").at("inside_occupant_types").at(0) == 3);
  assert(state.at("view_mode") == "world");
  state = act({{"action", "enter_room"}, {"room", 0}});
  assert(state.at("view_mode") == "room" && state.at("campaign").at("neighbour_can_talk") == true);
  assert(active_object(state, "Neighbour"));
  return state;
}
Json finish_first_inside_talk(Json state, std::size_t asking_choice) {
  state = act({{"action", "actor_talk"}, {"character", "Neighbour"}});
  assert(state.at("room") == 0 && state.at("dialogue").at("type") == "line");
  assert(state.at("campaign").at("neighbour_can_talk") == false);
  state = act({{"action", "save"}});
  for (int i = 0; i < 12 && state.at("dialogue").at("type") != "options"; ++i)
    state = act({{"action", "advance"}});
  assert(state.at("dialogue").at("type") == "options");
  assert(state.at("campaign").at("fridge_active") == true);
  const auto asking_options = state.at("dialogue").at("options");
  assert(asking_options.size() == 2 && asking_choice < asking_options.size());
  assert(asking_options.at(asking_choice).at("enabled") == true);

  // Restoring the save made before the fridge command restores both the Yarn
  // cursor and the UI toggle, then lets the same source command run once.
  state = act({{"action", "load"}});
  assert(state.at("campaign").at("fridge_active") == false);
  for (int i = 0; i < 12 && state.at("dialogue").at("type") != "options"; ++i)
    state = act({{"action", "advance"}});
  assert(state.at("campaign").at("fridge_active") == true);
  state = act({{"action", "choose"}, {"index", asking_choice}});
  for (int i = 0; i < 120 && state.at("phase") == "playing"; ++i) {
    const auto event = state.at("dialogue");
    if (event.is_null()) break;
    const auto type = event.at("type").get<std::string>();
    if (type == "line") state = act({{"action", "advance"}});
    else if (type == "options") {
      std::size_t available = event.at("options").size();
      for (std::size_t j = 0; j < event.at("options").size(); ++j)
        if (event.at("options").at(j).at("enabled").get<bool>()) { available = j; break; }
      assert(available < event.at("options").size());
      state = act({{"action", "choose"}, {"index", available}});
    } else if (type == "stopped") break;
    else assert(false && "unexpected inside dialogue event");
  }
  assert(state.at("phase") == "boundary");
  assert(state.at("campaign").at("boundary").get<std::string>().find("talk_neighbour_1") != std::string::npos);
  assert(state.at("campaign").at("neighbour_phone_unlocked") == true);
  const auto boundary_state = state;
  state = act({{"action", "save"}});
  state = act({{"action", "menu"}});
  state = act({{"action", "load"}});
  assert(state.at("phase") == "boundary");
  assert(state.at("campaign") == boundary_state.at("campaign"));
  assert(state.at("campaign").at("inside_occupant_types").size() == 1);
  assert(state.at("campaign").at("neighbour_phone_unlocked") == true);
  assert(state.at("campaign").at("neighbour_phone_number") == boundary_state.at("campaign").at("neighbour_phone_number"));
  assert(!active_object(state, "Neighbour"));
  return state;
}

int main(int argc, char** argv) {
  assert(argc == 2);
  const auto root = std::filesystem::path(argv[1]);
  auto state = Json::parse(ninah::current::create(
      read(root / "narrative/program.json"),
      read(root / "reverse-localization/line_metadata.json")));

  // A clean launch stays on the menu; the old isolated tool routes remain
  // available and retain their original day-13 fixture.
  assert(state.at("type") == "state" && state.at("phase") == "menu");
  assert(state.at("view_mode") == "world");
  assert(state.at("world_pose").at("position") == Json::array({-3.9849998951,1.5839999765,-6.998000145}));
  assert(state.at("world_navigation").at("room_doors").size() == 6);
  assert(state.at("world_navigation").at("room_doors").at(0).at("collider_path_id") == 2425);
  assert(state.at("world_navigation").at("room_doors").at(0).at("position") == Json::array({-2.108930531,1.391007798,-11.845447361}));
  assert(state.at("world_navigation").at("entrance_interaction").at("collider_path_id") == 2432);
  assert(state.at("world_navigation").at("entrance_interaction").at("linked_room") == 5);
  assert(state.at("world_navigation").at("entrance_interaction").at("position") == Json::array({-4.121358213,1.466307888,-4.229543804}));
  assert(state.at("energy") == 1 && state.at("day") == 0);
  assert(state.at("menu").at("can_continue") == false);
  state = act({{"action", "scenario"}, {"name", "fatman"}});
  assert(state.at("phase") == "tools" && state.at("day") == 13 && state.at("energy") == 4);
  const int before = state.at("inventory").at("Kombucha");
  for (int i = 0; i < 20 && state.at("inventory").at("Kombucha") == before; ++i)
    state = act({{"action", "advance"}});
  assert(state.at("inventory").at("Kombucha") == before + 1);
  assert(state.at("dialogue").at("type") == "line");
  const auto saved_line = state.at("dialogue");
  state = act({{"action", "save"}});
  state = act({{"action", "advance"}});
  assert(state.at("dialogue").at("type") == "stopped");
  state = act({{"action", "focus"}, {"character", "Mother"}});
  state = act({{"action", "load"}});
  assert(state.at("character") == "Fatman" && state.at("dialogue") == saved_line);
  state = act({{"action", "advance"}});
  assert(state.at("inventory").at("Kombucha") == before + 1);

  state = act({{"action", "scenario"}, {"name", "firefighter"}});
  for (int i = 0; i < 15 && state.at("dialogue").at("type") != "stopped"; ++i)
    state = act({{"action", "advance"}});
  assert(state.at("refused_count") == 1);
  state = act({{"action", "scenario"}, {"name", "alkonost"}});
  state = act({{"action", "advance"}});
  assert(state.at("dialogue").at("type") == "options");
  state = act({{"action", "choose"}, {"index", 1}});
  assert(state.at("energy") == 3);
  state = act({{"action", "focus"}, {"character", "Mother"}});
  state = act({{"action", "pose_tomorrow"}, {"pose", "LostChild"}});
  auto pose = [](const Json& value) {
    for (const auto& object : value.at("room_objects"))
      if (object.at("name") == "Mother") return object.at("pose").get<std::string>();
    return std::string{};
  };
  assert(pose(state) != "LostChild");
  state = act({{"action", "next_pose_day"}});
  assert(pose(state) == "LostChild");
  state = act({{"action", "inspect"}, {"sign", "Hands"}});
  assert(!state.at("sign").is_null());

  // Menu -> serialized intro captions -> source-confirmed video callback ->
  // first entrance event. No intro Yarn VM or later day transition is invented.
  state = act({{"action", "new_game"}});
  assert(state.at("phase") == "intro" && state.at("day") == 0);
  assert(state.at("energy") == 1 && state.at("room") == 5);
  assert(state.at("inventory").at("Bobeer") == 8);
  assert(state.at("inventory").at("Kombucha") == 1);
  assert(state.at("intro").at("duration_ms") == 72000);
  assert(state.at("intro").at("can_skip") == false);
  auto rejected_skip = call({{"action", "skip_intro"}});
  assert(!rejected_skip.at("error").is_null() && rejected_skip.at("phase") == "intro");
  const std::pair<int, std::string> captions[] = {{10000, "Intro_1"}, {20000, "Intro_2"},
      {28000, "Intro_3"}, {43000, "Intro_4"}, {59000, "Intro_5"}};
  for (const auto& caption : captions) {
    state = act({{"action", "intro_tick"}, {"elapsed_ms", caption.first}});
    assert(state.at("intro").at("node") == caption.second);
    assert(!state.at("intro").at("subtitle_line_ids").empty());
  }
  state = act({{"action", "intro_tick"}, {"elapsed_ms", 72000}});
  assert(state.at("intro").at("subtitle_line_ids").empty());
  state = act({{"action", "intro_video_finished"}});
  assert(state.at("phase") == "playing");
  assert(state.at("campaign").at("day") == 0);
  assert(state.at("campaign").at("time") == "night");
  assert(state.at("campaign").at("phone_numbers_initialized") == true);
  assert(state.at("campaign").at("phone_number_count") == 15);
  assert(state.at("campaign").at("neighbour_phone_number").get<std::string>().size() == 6);
  assert(state.at("campaign").at("door_waiting") == false);
  // Both authored entrance branches converge on LetIn Neighbour; the first
  // in-house dialogue then exposes either Asking_1 or Asking_2 before the
  // boundary. No day change is synthesized after those known nodes.
  state = admit_neighbour(state, 0);
  state = act({{"action", "enter_room"}, {"room", 0}});
  assert(state.at("room") == 0 && active_object(state, "Neighbour"));
  state = finish_first_inside_talk(state, 0);

  state = act({{"action", "new_game"}});
  const auto initial_pose_revision = state.at("world_pose").at("revision").get<std::int64_t>();
  state = act({{"action", "save"}, {"world_pose", {{"position", Json::array({-5.0,1.9,-7.1})},{"yaw",30.0},{"pitch",20.0},{"revision",-900}}}});
  const auto custom_pose = state.at("world_pose");
  assert(custom_pose.at("revision") > initial_pose_revision);
  auto rejected_pose = call({{"action", "save"}, {"world_pose", {{"position", Json::array({1001.0,1.9,-7.1})},{"yaw",0.0},{"pitch",0.0}}}});
  assert(!rejected_pose.at("error").is_null() && rejected_pose.at("world_pose") == custom_pose);
  state = act({{"action", "load"}});
  assert(state.at("world_pose").at("position") == custom_pose.at("position"));
  assert(state.at("world_pose").at("yaw") == 30.0 && state.at("world_pose").at("pitch") == 20.0);
  assert(state.at("world_pose").at("revision") > custom_pose.at("revision"));
  state = act({{"action", "new_game"}});
  state = act({{"action", "intro_tick"}, {"elapsed_ms", 72000}});
  state = act({{"action", "intro_video_finished"}});
  state = admit_neighbour(state, 1);
  state = finish_first_inside_talk(state, 1);

  std::cout << "Current Android host: menu, intro captions, first Neighbour admission/talk, "
               "legacy tools routes, and in-memory snapshots passed\n";
}
