#include "ninah/occupants.hpp"

#include <cassert>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace ninah;

static CharacterData character(int type, int place, bool imposter = false, bool random = false) {
    return CharacterData{type, "C" + std::to_string(type), 0, place, imposter,
                         true, false, random, {}, {}, 0};
}
static OccupantsHooks hooks(std::vector<std::string>& order, OccupantsState* state = nullptr) {
    OccupantsHooks h;
    h.room_kill_character = [&order, state](int id) {
        order.push_back("room-kill:" + std::to_string(id));
        if (state) assert(!state->killed.empty() && state->killed.back() == id);
        return true;
    };
    h.room_exile_character = [&](int id) { order.push_back("room-exile:" + std::to_string(id)); return true; };
    h.room_add_character = [&](int room, int id, bool silent) {
        (void)room;
        order.push_back("room-add:" + std::to_string(id) + (silent ? ":silent" : ":normal"));
        return true;
    };
    h.character_removed = [&](int id) { order.push_back("removed:" + std::to_string(id)); };
    h.character_added = [&order, state](int id, bool loaded) {
        if (state) assert(state->are_imposters.find(id) != state->are_imposters.end());
        order.push_back("added:" + std::to_string(id) + (loaded ? ":load" : ":new"));
    };
    h.unity_random_value = [&] { order.push_back("random-value"); return 0.1f; };
    h.unity_random_range = [&](int min, int max) { order.push_back("random-range"); assert(min == 0 && max == 2); return 1; };
    h.screamer_showed = [&](int id) { order.push_back("screamer:" + std::to_string(id)); };
    h.generate_baby_events = [&](int day) { order.push_back("baby-events:" + std::to_string(day)); };
    h.record_special_new_arrival = [&](int id) { order.push_back("special-arrival:" + std::to_string(id)); };
    h.record_kill_effects = [&](int id, bool by_player, bool imposter) {
        order.push_back("record:" + std::to_string(id) + (by_player ? ":player" : ":other") + (imposter ? ":imposter" : ":human"));
    };
    h.unlock_achievement = [&](const std::string& id) { order.push_back("achievement:" + id); };
    return h;
}

int main() {
    {
        CharacterCatalog catalog({character(1, 1), character(2, 2)});
        OccupantsState state;
        std::vector<std::string> order;
        OccupantsRuntime runtime(catalog, state, hooks(order), 0.75f);
        runtime.refuse(1); runtime.refuse(1); runtime.kill_tomorrow(2);
        runtime.exile_after_tomorrow(2, [] { return 5; });
        assert((state.refused == std::vector<int>{1, 1}));
        assert((state.self_kill_next_day == std::vector<int>{2}));
        assert((state.exiles_on_days.at(7) == std::vector<int>{2}));
    }
    {
        CharacterCatalog catalog({character(3, 3, true)});
        OccupantsState state;
        state.characters.inside = {3}; state.characters.with_povistka = {3, 3}; state.fema_rating[3] = .5f;
        std::vector<std::string> order;
        OccupantsRuntime runtime(catalog, state, hooks(order, &state), .75f);
        runtime.kill(3, true);
        assert((state.killed == std::vector<int>{3}));
        assert(state.innocents_killed_by_player.empty() && state.killed_by_imposters.empty());
        assert(state.characters.with_povistka == std::vector<int>{3});
        assert(state.fema_rating.count(3) == 0);
        const std::vector<std::string> expected{"room-kill:3", "random-value", "screamer:3",
            "record:3:player:imposter", "removed:3", "achievement:KILL_IMPOSTER"};
        assert(order == expected);
    }
    {
        CharacterCatalog catalog({character(4, 4), character(5, 5, true)});
        OccupantsState state; state.characters.inside = {4, 5}; state.came_in_days = {{4, 2}, {5, 2}};
        std::vector<std::string> order; OccupantsRuntime runtime(catalog, state, hooks(order), .75f);
        assert(runtime.possible_characters_to_kill(3).empty());
        assert((runtime.possible_characters_to_kill(4) == std::vector<int>{4}));
    }
    {
        CharacterCatalog catalog({character(6, 6), character(7, 7)});
        OccupantsState state; state.characters.inside = {6, 7};
        state.fema_rating = {{6, .5f}, {7, 1.f}}; state.exiles_on_days[7] = {6}; state.killed_today = {7};
        std::vector<std::string> order; OccupantsRuntime runtime(catalog, state, hooks(order), .75f);
        runtime.begin_new_day(7, .25f);
        assert(state.fema_rating.count(6) == 0 && state.fema_rating.at(7) == 1.25f);
        assert(state.characters.inside == std::vector<int>{7});
        assert(state.exiled == std::vector<int>{6} && state.killed_today.empty());
        assert((order == std::vector<std::string>{"room-exile:6", "removed:6", "achievement:WEEK1_IMPOSTERS_DOESNT_KILL"}));
    }
    {
        CharacterCatalog catalog({character(8, 8, false, true), character(9, 9)});
        OccupantsState state; state.characters.inside = {9}; state.came_in_days = {{9, 1}};
        state.fema_rating[9] = .2f;
        std::vector<std::string> order; OccupantsRuntime runtime(catalog, state, hooks(order, &state), .75f);
        const auto result = runtime.let_in(8, false, .2f, .1f, 0.f, .4f, [] { return 2; });
        assert(result == LetInResult::Added);
        assert((state.characters.inside == std::vector<int>{9, 8}));
        assert((state.came_in_days == std::vector<std::pair<int,int>>{{9, 1}, {8, 2}}));
        assert(std::abs(state.fema_rating.at(8) - .3f) < .0001f);
        assert(!catalog.at(8).is_imposter); // Range callback returned 1, not 0.
        assert(state.are_imposters.at(8) == false);
        const std::vector<std::string> expected{"room-add:8:normal", "random-range", "added:8:new"};
        assert(order == expected);
    }
    {
        CharacterCatalog catalog({character(10, 10), character(11, 10)});
        OccupantsState state; state.characters.inside = {10};
        std::vector<std::string> order; OccupantsRuntime runtime(catalog, state, hooks(order), .75f);
        assert(runtime.let_in(11, false, .2f, 0.f, .05f, .4f, {}) == LetInResult::PlaceAlreadyTaken);
        assert(state.characters.inside == std::vector<int>{10});
        assert(order.empty());
        assert(runtime.let_in(11, true, .2f, 0.f, .05f, .4f, {}) == LetInResult::Added);
        assert((state.exiled == std::vector<int>{10}));
        assert(state.characters.inside == std::vector<int>{11});
        assert(order[0] == "room-exile:10" && order[1] == "removed:10");
        assert(order[2] == "room-add:11:normal" && order[3] == "added:11:new");
    }
    {
        CharacterCatalog catalog({character(19, 19), character(51, 51)});
        OccupantsState state; std::vector<std::string> order;
        OccupantsRuntime runtime(catalog, state, hooks(order), .75f);
        assert(runtime.let_in(19, false, .2f, 0.f, .05f, .4f, {}) == LetInResult::Added);
        assert(runtime.let_in(51, false, .2f, 0.f, .05f, .4f, {}) == LetInResult::Added);
        assert(order[0] == "room-add:19:normal" && order[1] == "baby-events:0" && order[2] == "added:19:new");
        assert(order[3] == "room-add:51:normal" && order[4] == "special-arrival:51" && order[5] == "added:51:new");
    }
    std::cout << "occupants tests passed\n";
}
