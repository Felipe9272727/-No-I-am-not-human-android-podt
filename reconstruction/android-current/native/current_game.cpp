// Current C++ gameplay host. Original Windows programs are never loaded.
#include "ninah/dialogue_session.hpp"
#include "ninah/arrivals.hpp"
#include "ninah/scene_commands.hpp"
#include "ninah/progression.hpp"
#include "presentation_provider.hpp"
#include "production_characters.hpp"
#include "production_data.hpp"
#include "production_phone.hpp"
#include "morning_config.hpp"
#include "../../native-game/third_party/nlohmann/json.hpp"

#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <memory>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef __ANDROID__
#include <jni.h>
#endif

namespace ninah::current {
using Json = nlohmann::json;
struct WorldPose { std::array<double,3> position{{-3.9849998951,1.5839999765,-6.998000145}}; double yaw=0.0,pitch=0.0; std::int64_t revision=0; };
Json vector(PresentationVec3 v) { return Json::array({v.x, v.y, v.z}); }
Json asset(const std::string& source, PresentationAsset a) {
  return a.valid && a.path_id ? Json(source + ":" + std::to_string(a.path_id))
                              : Json(nullptr);
}
Json frames(const std::string& source, const std::vector<PresentationAsset>& refs) {
  auto result = Json::array();
  for (const auto& ref : refs)
    if (ref.valid && ref.path_id) result.push_back(asset(source, ref));
  return result;
}
Json world_doors(){
  return Json::array({
    {{"name","Door1 (Kitchen)"},{"room",0},{"pivot_position",Json::array({-1.792855551,0.272407818,-13.871147252})},{"position",Json::array({-2.108930531,1.391007798,-11.845447361})},{"collider_path_id",2425},{"collider_size",Json::array({0.05,1.99,0.86})}},
    {{"name","Door2 (Office)"},{"room",1},{"pivot_position",Json::array({0.040144027,0.272407818,-13.862922288})},{"position",Json::array({-0.269097944,1.328732762,-11.819597414})},{"collider_path_id",2449},{"collider_size",Json::array({0.05,1.99,0.86})}},
    {{"name","Door3 (BigRoom)"},{"room",2},{"pivot_position",Json::array({0.949718850,0.272407818,-6.767097535})},{"position",Json::array({0.984968848,1.328732762,-8.829222446})},{"collider_path_id",2452},{"collider_size",Json::array({0.05,1.99,0.86})}},
    {{"name","Door4 (Bathroom)"},{"room",3},{"pivot_position",Json::array({-0.879880927,0.272407818,-7.454472552})},{"position",Json::array({-2.986656064,1.272332790,-7.755272878})},{"collider_path_id",2453},{"collider_size",Json::array({0.70,1.9,0.05})}},
    {{"name","Door5 (Pantry)"},{"room",4},{"pivot_position",Json::array({-7.132056070,0.272407818,-9.514247353})},{"position",Json::array({-5.079330890,1.286432748,-9.424947624})},{"collider_path_id",2460},{"collider_size",Json::array({0.64,2.02,0.10})}},
    {{"name","Door6 (Bedroom)"},{"room",6},{"pivot_position",Json::array({5.122018877,0.272407818,-10.235697302})},{"position",Json::array({3.142143797,1.318157759,-10.524747603})},{"collider_path_id",2439},{"collider_size",Json::array({0.86,1.99,0.05})}}
  });
}
Json entrance_interaction(){
  return {{"name","Peephole_LookAtObjectTrigger"},{"room",5},{"position",Json::array({-4.121358213,1.466307888,-4.229543804})},
    {"gameobject_path_id",81},{"monobehaviour_path_id",3929},{"raycast_target_gameobject_path_id",142},{"collider_path_id",2432},
    {"is_trigger",false},{"layer","Default"},{"collider_size",Json::array({0.00986942742,0.00099928433,0.02041645907})},
    {"proximity_trigger_collider_path_id",2412},{"proximity_trigger_position",Json::array({-4.117005650,0.098784393,-4.535772429})},{"linked_room",5}};
}

struct Flags { bool begun=false, saved=false, rude=false, death=false, mushroom=false, vigilante=false; };

class Context {
 public:
  Context(std::string program, std::string metadata)
      : program_(std::move(program)), metadata_(std::move(metadata)),
        characters_(production::character_catalog()),
        inventory_state_(InventoryState::initial(false)), inventory_(inventory_state_),
        catalog_(presentation_data::characters()),
        presentation_(std::make_unique<PresentationState>(catalog_)),
        phone_service_(production::fixed_phone_numbers(),PhoneRandom{
          [this](std::int32_t lo,std::int32_t hi){return random_range(lo,hi);},
          [this](float lo,float hi){std::uniform_real_distribution<float>d(lo,hi);return d(rng_);}}),
        deficit_targets_{{Consumable::Enerjeka,2},{Consumable::Cigarette,0},
                         {Consumable::Coffee,1},{Consumable::CatFood,0},
                         {Consumable::Kombucha,1},{Consumable::Povistka,0}},
        deficit_service_(inventory_, [this]{return energy_.day;},
          ConsumablesDeficitSaveRef{&deficit_item_day_},
          OtherGameDeficitDataRef{&deficit_targets_, [this]{return random_range(2,4);}},
          [this](std::int32_t lo,std::int32_t hi){return random_range(lo,hi);}),
        people_(characters_,occupants_,occupant_hooks(),0.75f),
        commands_(inventory_,people_,[this]{return energy_.day;},
          [this](std::int32_t type){return let_in_inputs(type);}),
        functions_(energy_,characters_,occupants_.characters,inventory_,&phone_numbers_,
                   dialogue_service_hooks()),
        story_({&flags_.begun,&flags_.saved,&flags_.rude,&flags_.death,&flags_.mushroom,&flags_.vigilante},
               story_queries()) {
    energy_.day=0; energy_.remaining=1; room_=5; phase_="menu"; rebuild_router();
  }

  Json action(const Json& a) {
    error_.clear();
    try {
      const auto name=a.at("action").get<std::string>();
      if(name=="scenario") scenario(a.at("name").get<std::string>());
      else if(name=="new_game") new_game();
      else if(name=="menu") { session_.reset(); phase_="menu"; log("Menu aberto"); }
      else if(name=="continue_game") {
        if(saved_) load();
        else if(phase_=="boundary"&&boundary_return_phase_=="playing") {
          phase_="playing"; log("Última cena conhecida retomada; nenhum avanço foi executado");
        } else throw std::logic_error("Nenhuma cena salva disponível para continuar");
      } else if(name=="intro_tick") {
        if(phase_=="intro") {
          const auto t=a.at("elapsed_ms").get<std::int64_t>();
          if(t<0) throw std::invalid_argument("Tempo de introdução inválido");
          intro_elapsed_ms_=std::max(intro_elapsed_ms_,std::min<std::int64_t>(t,72000));
        }
      } else if(name=="skip_intro") {
        throw std::logic_error("Não há comando de pulo confirmado para a introdução");
      } else if(name=="intro_video_finished") finish_intro_video();
      else if(name=="campaign_tick") {
        if(phase_=="playing"&&!transition_pending_) {
          const auto t=a.at("elapsed_ms").get<std::int64_t>();
          if(t<0) throw std::invalid_argument("Tempo de campanha inválido");
          campaign_elapsed_ms_=std::max(campaign_elapsed_ms_,t);
          if(energy_.day==0&&progression_.time_of_day==TimeOfDay::Night&&!door_opened_
             &&!night_events_complete()&&campaign_elapsed_ms_>=1000)door_waiting_=true;
        }
      } else if(name=="open_door") open_door();
      else if(name=="sleep") sleep();
      else if(name=="complete_day_transition") complete_day_transition();
      else if(name=="watch_morning_tv") watch_morning_tv();
      else if(name=="enter_world") {
        if(transition_pending_)throw std::logic_error("A virada de dia ainda está em andamento");
        if(session_&&!is_stopped(session_.get()))throw std::logic_error("A conversa atual ainda está ativa");
        view_mode_="world";
      } else if(name=="enter_room") {
        if(transition_pending_)throw std::logic_error("A virada de dia ainda está em andamento");
        const int destination=a.at("room").get<int>();
        if(session_&&!is_stopped(session_.get()))throw std::logic_error("A conversa atual ainda está ativa");
        if(phase_!="playing"||destination<0||destination>6)throw std::logic_error("Cômodo não disponível para navegação");
        room_=destination;view_mode_="room";
      }
      else if(name=="actor_talk") actor_talk(a.at("character").get<std::string>());
      else if(name=="room") {
        const int room=a.at("room").get<int>();
        if(room<0||room>6) throw std::invalid_argument("Cômodo inválido");
        room_=room;
      } else if(name=="focus") {
        if(phase_!="tools") throw std::logic_error("Foco de personagem só está disponível nas ferramentas");
        focus(a.at("character").get<std::string>());
      } else if(name=="advance"||name=="choose") {
        if(!session_) throw std::logic_error("Não há diálogo ativo");
        const int kombucha=inventory_.count(Consumable::Kombucha);
        const auto refused=occupants_.refused.size();
        if(name=="advance") session_->advance(); else session_->choose(a.at("index").get<std::size_t>());
        if(inventory_.count(Consumable::Kombucha)!=kombucha) log("Kombucha recebida pelo comando original GetItem");
        if(occupants_.refused.size()!=refused) log("Visitante recusado pelo núcleo C++");
        if(phase_=="playing"&&is_stopped(session_.get())) finish_current_dialogue();
      } else if(name=="inspect") {
        if(!router_->dispatch("ShowSign "+character_+" "+a.at("sign").get<std::string>()))
          throw std::logic_error("Esse sinal ainda não possui apresentação integrada");
      } else if(name=="stop_sign") presentation_->stop_showing_sign();
      else if(name=="pose"||name=="pose_tomorrow") {
        const auto pose=a.at("pose").get<std::string>();
        if(!router_->dispatch((name=="pose"?"ChangePose ":"ChangePoseTomorrow ")+character_+" "+pose))
          throw std::logic_error("Pose não disponível para este personagem");
        log(name=="pose"?"Pose atual alterada":"Pose agendada para a próxima virada de teste");
      } else if(name=="next_pose_day") {
        const auto applied=presentation_->apply_tomorrow_poses();
        log(std::to_string(applied.size())+" poses futuras aplicadas; isto não avança a campanha");
      } else if(name=="save") {
        if(a.contains("world_pose")&&!a.at("world_pose").is_null()) set_world_pose(a.at("world_pose"));
        save();
      }
      else if(name=="export_save") {
        if(!saved_) throw std::logic_error("Nenhum estado salvo disponível para exportar");
        Json result=state();result["save"]=encode_saved();return result;
      }
      else if(name=="import_save") {
        const Json& input=a.at("save");
        Json payload=input.is_string()?Json::parse(input.get<std::string>()):input;
        import_saved(payload);
      }
      else if(name=="load") load();
      else if(name!="state") throw std::invalid_argument("Ação de teste desconhecida");
    } catch(const std::exception& e) {
      error_=e.what(); log(error_);
    }
    return state();
  }

  Json state() const {
    Json result={{"type","state"},{"phase",phase_},{"campaign_complete",false},
      {"view_mode",view_mode_},{"world_pose",{{"position",Json::array({world_pose_.position[0],world_pose_.position[1],world_pose_.position[2]})},
        {"yaw",world_pose_.yaw},{"pitch",world_pose_.pitch},{"revision",world_pose_.revision}}},
      {"world_navigation",{{"room_doors",world_doors()},{"entrance_interaction",entrance_interaction()},{"camera_fov_deg",60.0},{"camera_near_clip",0.1},{"camera_far_clip",1000.0}}},
      {"character",character_},{"room",room_},{"day",energy_.day},{"energy",energy_.remaining},
      {"inventory",Json::object()},{"refused_count",occupants_.refused.size()},
      {"dialogue",session_?Json::parse(session_->current_event()):Json(nullptr)},
      {"portrait",nullptr},{"sign",nullptr},{"room_objects",Json::array()},
      {"fridge_active",fridge_active_},{"error",error_.empty()?Json(nullptr):Json(error_)},
      {"logs",logs_},{"save_available",static_cast<bool>(saved_)},
      {"save_scope","snapshot JSON versionado"}};
    for(const auto item:{Consumable::Bobeer,Consumable::Coffee,Consumable::Enerjeka,
                         Consumable::Povistka,Consumable::Kombucha})
      result["inventory"][consumable_enum_name(item)]=inventory_.count(item);
    if(phase_=="menu") result["menu"]={{"can_continue",static_cast<bool>(saved_)}};
    if(phase_=="intro") result["intro"]={{"video_asset","intro/Intro_Final_2_NO_SUBTITLES.mp4"},
      {"duration_ms",72000},{"elapsed_ms",intro_elapsed_ms_},{"node",intro_node(intro_elapsed_ms_)},
      {"subtitle_line_ids",intro_line_ids(intro_elapsed_ms_)},{"can_skip",false}};
    if(phase_=="playing"||phase_=="boundary") {
      const bool neighbour_inside=contains(occupants_.characters.inside,3);
      const auto* neighbour_data=characters_.find(3);
      const char* daytime=progression_.time_of_day==TimeOfDay::Day?"day":"night";
      Json c={{"day",energy_.day},{"time",daytime},{"time_of_day",daytime},{"energy",energy_.remaining},
        {"can_sleep",can_sleep()},{"transition_pending",transition_pending_},{"transition_target","day"},
        {"morning_tv_pending",morning_tv_pending_},{"morning_tv_complete",morning_tv_complete_},
        {"can_watch_morning_tv",can_watch_morning_tv()},
        {"didnt_check_signs_days",didnt_check_signs_days_},
        {"night_events_complete",night_events_complete()},
        {"door_waiting",door_waiting_},{"visitor",door_waiting_?"Neighbour":""},
        {"visitor_type",door_waiting_?3:0},{"fridge_active",fridge_active_},
        {"neighbour_inside",neighbour_inside},
        {"neighbour_can_talk",phase_=="playing"&&view_mode_=="room"&&neighbour_inside&&neighbour_data&&room_==neighbour_data->room&&!session_&&!neighbour_talk_completed_},
        {"neighbour_talk_count",committed_neighbour_talks_+pending_neighbour_talks_},
        {"neighbour_room",neighbour_data?neighbour_data->room:-1},
        {"view_mode",view_mode_},
        {"inside_occupant_types",occupants_.characters.inside},
        {"elapsed_ms",campaign_elapsed_ms_}};
      c["next_day_preset_visits"]=Json::array();
      for(const auto& slot:preset_visits_for_day(characters_,energy_.day+1)){
        const auto* scheduled=characters_.find(slot.character_id);
        if(scheduled)c["next_day_preset_visits"].push_back({{"character_type",slot.character_id},
          {"character",scheduled->name},{"day",slot.day},{"guest_number",slot.guest_number}});
      }
      c["phone_numbers_initialized"]=phones_initialized_;
      c["phone_number_count"]=phone_numbers_.entries.size();
      c["neighbour_phone_number"]=PhoneNumberService::get_number_by_subscriber(phone_numbers_,PhoneSubscriber::Neighbour);
      c["neighbour_phone_unlocked"]=std::find(unlocked_phone_subscribers_.begin(),unlocked_phone_subscribers_.end(),
        static_cast<std::int32_t>(PhoneSubscriber::Neighbour))!=unlocked_phone_subscribers_.end();
      if(phase_=="boundary") c["boundary"]=boundary_reason_;
      result["campaign"]=std::move(c);
    }
    if(const auto p=presentation_->current_dialog_packet()) result["portrait"]={{"character",p->character},{"emotion",p->emotion},{"frames",frames(p->source_file,p->frames)},
      {"fps",p->frames_per_second},{"cycling",p->cycling},{"position",vector(p->position)},{"scale",vector(p->scale)}};
    if(const auto& s=presentation_->active_sign()) result["sign"]={{"character",s->character},{"kind",static_cast<int>(s->sign)},
      {"sprite",asset(s->source_file,s->assets.sprite)},{"white",asset(s->source_file,s->assets.white)},
      {"iris",asset(s->source_file,s->assets.iris)},{"frames",frames(s->source_file,s->assets.frames)},
      {"fps",s->assets.frames_per_second},{"cycling",s->assets.cycling}};
    for(const auto& c:catalog_.records()) if(const auto p=presentation_->room_packet(c.name)) {
      const bool active=phase_=="tools" ? c.name==character_ :
        ((phase_=="playing"||phase_=="boundary")&&view_mode_=="room"&&room_==p->room_enum&&contains(occupants_.characters.inside,c.character_type));
      result["room_objects"].push_back({{"name",c.name},{"room",p->room_enum},{"pose",p->pose_name},
        {"asset",asset(p->source_file,p->sprite)},{"position",vector(p->position)},{"scale",vector(p->scale)},
        {"cannot_interact",p->cannot_interact},{"active",active},{"authored_active",p->authored_active_self}});
    }
    return result;
  }

 private:
  struct Snapshot {
    ProgressionState progression; InventoryState inventory; OccupantsState occupants; Flags flags;
    PhoneNumbers phone_numbers; std::vector<std::int32_t> unlocked_phone_subscribers; bool phones_initialized;
    WorldPose world_pose; std::string view_mode;
    CharacterCatalog characters; PresentationState presentation; std::mt19937 rng;
    std::int32_t deficit_day; std::string character,dialogue,phase,boundary_return_phase,boundary_reason,active_node;
    std::int64_t intro_elapsed_ms,campaign_elapsed_ms; int room;
    bool has_session,door_waiting,door_opened,fridge_active,neighbour_talk_completed;
    std::int32_t completed_preset_visits;
    bool transition_pending,morning_tv_pending,morning_tv_complete;
    std::int32_t didnt_check_signs_days,pending_neighbour_talks,committed_neighbour_talks;
    std::string completed_dialogue_snapshot;
    PresentationState::Snapshot presentation_snapshot;
    explicit Snapshot(const Context& c):progression(c.progression_),inventory(c.inventory_state_),occupants(c.occupants_),
      flags(c.flags_),phone_numbers(c.phone_numbers_),unlocked_phone_subscribers(c.unlocked_phone_subscribers_),
      phones_initialized(c.phones_initialized_),world_pose(c.world_pose_),view_mode(c.view_mode_),characters(c.characters_),presentation(*c.presentation_),rng(c.rng_),deficit_day(c.deficit_item_day_),
      character(c.character_),dialogue(c.session_?c.session_->dump_snapshot():std::string{}),phase(c.phase_),
      boundary_return_phase(c.boundary_return_phase_),boundary_reason(c.boundary_reason_),active_node(c.active_node_),
      intro_elapsed_ms(c.intro_elapsed_ms_),campaign_elapsed_ms(c.campaign_elapsed_ms_),room(c.room_),
      has_session(static_cast<bool>(c.session_)),door_waiting(c.door_waiting_),door_opened(c.door_opened_),
      fridge_active(c.fridge_active_),neighbour_talk_completed(c.neighbour_talk_completed_),
      completed_preset_visits(c.completed_preset_visits_),transition_pending(c.transition_pending_),
      morning_tv_pending(c.morning_tv_pending_),morning_tv_complete(c.morning_tv_complete_),
      didnt_check_signs_days(c.didnt_check_signs_days_),pending_neighbour_talks(c.pending_neighbour_talks_),
      committed_neighbour_talks(c.committed_neighbour_talks_),completed_dialogue_snapshot(c.completed_dialogue_snapshot_),
      presentation_snapshot(c.presentation_->snapshot()){}
  };
  std::uint64_t content_id() const {
    std::uint64_t h=1469598103934665603ull;
    auto add=[&](const std::string& text){for(unsigned char c:text){h^=c;h*=1099511628211ull;}h^=0xff;h*=1099511628211ull;};
    add(program_);add(metadata_);return h;
  }
  std::string content_id_text() const { std::ostringstream out;out<<std::hex<<std::setw(16)<<std::setfill('0')<<content_id();return out.str(); }
  Json encode_saved() const {
    const auto& s=*saved_; std::ostringstream random; random<<s.rng;
    Json inventory=Json::array(); for(const auto& [item,count]:s.inventory.storage) inventory.push_back({static_cast<int>(item),count});
    Json ever=Json::array(),today=Json::array();for(auto item:s.inventory.ever_used)ever.push_back(static_cast<int>(item));for(auto item:s.inventory.today_used)today.push_back(static_cast<int>(item));
    Json phones=Json::array(); for(const auto& e:s.phone_numbers.entries) phones.push_back({static_cast<int>(e.subscriber),e.number});
    Json fema=Json::array(); for(const auto& [id,value]:s.occupants.fema_rating) fema.push_back({id,value});
    Json fines=Json::array(); for(const auto& [day,value]:s.progression.energy.fines_by_day) fines.push_back({day,value});
    Json imposters=Json::array(); for(const auto& [id,value]:s.occupants.are_imposters) imposters.push_back({id,value});
    Json exiles=Json::array(); for(const auto& [day,ids]:s.occupants.exiles_on_days) exiles.push_back({day,ids});
    Json visits=Json::array(); for(auto [id,day]:s.occupants.came_in_days) visits.push_back({id,day});
    Json characters=Json::array(); for(const auto& c:s.characters.records()) characters.push_back({{"id",c.type},{"imposter",c.is_imposter}});
    const auto& p=s.presentation_snapshot;
    Json pose=[](const std::vector<PoseChange>& v){Json out=Json::array();for(const auto& x:v)out.push_back({x.character,x.state});return out;}(p.immediate_poses);
    Json tomorrow=[](const std::vector<PoseChange>& v){Json out=Json::array();for(const auto& x:v)out.push_back({x.character,x.state});return out;}(p.tomorrow_poses);
    Json live=Json::object();for(const auto& [name,value]:p.live_poses)live[name]=value;
    Json pres={{"dialog_companion",p.dialog_companion},{"emotion",p.emotion?Json(*p.emotion):Json(nullptr)},
      {"gun_shown",p.gun_shown?Json(*p.gun_shown):Json(nullptr)},{"immediate",pose},{"tomorrow",tomorrow},{"live",live}};
    Json sign=nullptr;if(p.active_sign)sign={{"character",p.active_sign->character},{"source",p.active_sign->source_file},
      {"path",p.active_sign->source_path_id},{"sign",static_cast<int>(p.active_sign->sign)},{"imposter",p.active_sign->imposter}};
    pres["sign"]=sign;
    return {{"magic","NINAH-SAVE"},{"version",1},{"content_id",content_id_text()},
      {"progression",{{"day",s.progression.energy.day},{"remaining",s.progression.energy.remaining},{"extra",s.progression.energy.extra_slots},
        {"fines",fines},{"time",static_cast<int>(s.progression.time_of_day)},
        {"last",s.progression.last_change},{"accumulated",s.progression.accumulated_time},{"leave",s.progression.can_leave_rooms},
        {"blocked",s.progression.imposters_killing_blocked},{"murdered",s.progression.was_somebody_murdered},{"body_ready",s.progression.bodyeater_ready},
        {"repair",s.progression.repair_after_bodyeater},{"courier_day",s.progression.last_courier_ordered_day},{"coffee_days",s.progression.coffee_days}}},
      {"inventory",{{"storage",inventory},{"ever",ever},{"today",today},{"povistkas_used",s.inventory.povistkas_used}}},
      {"occupants",{{"inside",s.occupants.characters.inside},{"with_povistka",s.occupants.characters.with_povistka},
        {"killed",s.occupants.killed},{"exiled",s.occupants.exiled},{"refused",s.occupants.refused},{"self_kill",s.occupants.self_kill_next_day},
        {"innocents_killed",s.occupants.innocents_killed_by_player},{"killed_by_imposters",s.occupants.killed_by_imposters},{"killed_today",s.occupants.killed_today},
        {"fema",fema},{"imposters",imposters},{"exiles_days",exiles},{"came_in",visits}}},
      {"characters",characters},{"rng",random.str()},{"deficit_day",s.deficit_day},{"flags",{{"begun",s.flags.begun},{"saved",s.flags.saved},{"rude",s.flags.rude},{"death",s.flags.death},{"mushroom",s.flags.mushroom},{"vigilante",s.flags.vigilante}}},
      {"phone_numbers",phones},{"unlocked",s.unlocked_phone_subscribers},{"phones_initialized",s.phones_initialized},
      {"world_pose",{{"position",s.world_pose.position},{"yaw",s.world_pose.yaw},{"pitch",s.world_pose.pitch},{"revision",s.world_pose.revision}}},
      {"view_mode",s.view_mode},{"character",s.character},{"dialogue",s.dialogue},{"has_session",s.has_session},
      {"phase",s.phase},{"boundary_return",s.boundary_return_phase},{"boundary_reason",s.boundary_reason},{"active_node",s.active_node},
      {"intro_elapsed",s.intro_elapsed_ms},{"campaign_elapsed",s.campaign_elapsed_ms},{"room",s.room},
      {"door_waiting",s.door_waiting},{"door_opened",s.door_opened},{"fridge",s.fridge_active},{"neighbour_talk_completed",s.neighbour_talk_completed},
      {"completed_visits",s.completed_preset_visits},{"transition",s.transition_pending},{"tv_pending",s.morning_tv_pending},{"tv_complete",s.morning_tv_complete},
      {"didnt_check_signs",s.didnt_check_signs_days},{"pending_talks",s.pending_neighbour_talks},{"committed_talks",s.committed_neighbour_talks},
      {"completed_dialogue",s.completed_dialogue_snapshot},{"presentation",pres}};
  }
  void import_saved(const Json& j) {
    auto require=[&](const char* k){if(!j.is_object()||!j.contains(k))throw std::invalid_argument("Save field missing: "+std::string(k));};
    require("magic");require("version");require("content_id");
    if(j.at("magic")!="NINAH-SAVE"||!j.at("version").is_number_integer()||j.at("version")!=1)
      throw std::invalid_argument("Unsupported save format version");
    if(!j.at("content_id").is_string()||j.at("content_id").get<std::string>()!=content_id_text())
      throw std::invalid_argument("Save belongs to different narrative content");
    auto c=std::make_unique<Snapshot>(*this);
    const auto& p=j.at("progression"); const auto& inv=j.at("inventory"); const auto& o=j.at("occupants");
    if(!p.is_object()||!inv.is_object()||!o.is_object())throw std::invalid_argument("Malformed save sections");
    auto integer=[&](const Json& x,int lo,int hi){if(!x.is_number_integer())throw std::invalid_argument("Expected integer save value");auto n=x.get<std::int64_t>();if(n<lo||n>hi)throw std::invalid_argument("Save integer outside valid range");return static_cast<std::int32_t>(n);};
    auto boolean=[&](const Json& x){if(!x.is_boolean())throw std::invalid_argument("Expected boolean save value");return x.get<bool>();};
    auto int_list=[&](const Json& a,int lo,int hi){if(!a.is_array())throw std::invalid_argument("Expected integer list");std::vector<std::int32_t> v;for(const auto& x:a)v.push_back(integer(x,lo,hi));return v;};
    if(!j.at("characters").is_array()||j.at("characters").size()!=c->characters.records().size())throw std::invalid_argument("Malformed character catalog save");
    std::vector<std::int32_t> serialized_character_ids;
    for(const auto& row:j.at("characters")){if(!row.is_object())throw std::invalid_argument("Malformed character row");auto id=integer(row.at("id"),0,10000);if(!c->characters.find(id)||std::find(serialized_character_ids.begin(),serialized_character_ids.end(),id)!=serialized_character_ids.end())throw std::invalid_argument("Unknown or duplicate character catalog reference");serialized_character_ids.push_back(id);c->characters.set_imposter(id,boolean(row.at("imposter")));}
    c->progression.energy.day=integer(p.at("day"),0,1000);c->progression.energy.remaining=integer(p.at("remaining"),0,1000);
    c->progression.energy.extra_slots=integer(p.at("extra"),0,1000);c->progression.time_of_day=static_cast<TimeOfDay>(integer(p.at("time"),0,1));
    c->progression.last_change=p.at("last").get<float>();c->progression.accumulated_time=p.at("accumulated").get<float>();
    if(!std::isfinite(c->progression.last_change)||!std::isfinite(c->progression.accumulated_time))throw std::invalid_argument("Non-finite progression time");
    c->progression.can_leave_rooms=boolean(p.at("leave"));c->progression.imposters_killing_blocked=boolean(p.at("blocked"));
    c->progression.was_somebody_murdered=boolean(p.at("murdered"));c->progression.bodyeater_ready=boolean(p.at("body_ready"));
    c->progression.repair_after_bodyeater=boolean(p.at("repair"));c->progression.last_courier_ordered_day=integer(p.at("courier_day"),-1,1000);
    c->progression.coffee_days=int_list(p.at("coffee_days"),0,1000);
    c->progression.energy.fines_by_day.clear();if(!p.at("fines").is_array())throw std::invalid_argument("Invalid fine table");for(const auto& row:p.at("fines")){if(!row.is_array()||row.size()!=2)throw std::invalid_argument("Malformed fine row");auto day=integer(row[0],0,1000);auto value=integer(row[1],0,100000);if(c->progression.energy.fines_by_day.count(day))throw std::invalid_argument("Duplicate fine day");c->progression.energy.fines_by_day[day]=value;}
    c->inventory.storage.clear();for(const auto& row:inv.at("storage")){if(!row.is_array()||row.size()!=2)throw std::invalid_argument("Malformed inventory row");auto id=integer(row[0],0,100);if(id!=0&&id!=1&&id!=2&&id!=3&&id!=4&&id!=5&&id!=6&&id!=7&&id!=8&&id!=9&&id!=100)throw std::invalid_argument("Unknown inventory item");if(c->inventory.storage.count(static_cast<Consumable>(id)))throw std::invalid_argument("Duplicate inventory item");c->inventory.storage[static_cast<Consumable>(id)]=integer(row[1],0,100000);}
    auto item_vector=[&](const Json& values){if(!values.is_array())throw std::invalid_argument("Invalid inventory usage list");std::vector<Consumable> result;for(const auto& x:values){auto id=integer(x,0,100);if(id!=0&&id!=1&&id!=2&&id!=3&&id!=4&&id!=5&&id!=6&&id!=7&&id!=8&&id!=9&&id!=100)throw std::invalid_argument("Unknown used inventory item");result.push_back(static_cast<Consumable>(id));}return result;};
    c->inventory.ever_used=item_vector(inv.at("ever"));c->inventory.today_used=item_vector(inv.at("today"));c->inventory.povistkas_used=integer(inv.at("povistkas_used"),0,100000);
    auto vec=[&](const char* key){const auto& values=o.at(key);if(!values.is_array())throw std::invalid_argument("Invalid character reference list");std::vector<std::int32_t> v;for(const auto& raw:values){auto id=integer(raw,0,10000);if(!c->characters.find(id))throw std::invalid_argument("Unknown character reference in save");v.push_back(id);}return v;};
    c->occupants.characters.inside=vec("inside");c->occupants.characters.with_povistka=vec("with_povistka");c->occupants.killed=vec("killed");c->occupants.exiled=vec("exiled");c->occupants.refused=vec("refused");c->occupants.self_kill_next_day=vec("self_kill");c->occupants.innocents_killed_by_player=vec("innocents_killed");c->occupants.killed_by_imposters=vec("killed_by_imposters");c->occupants.killed_today=vec("killed_today");
    c->occupants.fema_rating.clear();for(const auto& row:o.at("fema")){if(!row.is_array()||row.size()!=2||!row[1].is_number())throw std::invalid_argument("Malformed FEMA row");auto id=integer(row[0],0,10000);float v=row[1].get<float>();if(!std::isfinite(v)||std::abs(v)>10000||!c->characters.find(id)||c->occupants.fema_rating.count(id))throw std::invalid_argument("Invalid FEMA reference");c->occupants.fema_rating[id]=v;}
    c->occupants.are_imposters.clear();for(const auto& row:o.at("imposters")){if(!row.is_array()||row.size()!=2)throw std::invalid_argument("Malformed imposter row");auto id=integer(row[0],0,10000);if(!c->characters.find(id)||c->occupants.are_imposters.count(id))throw std::invalid_argument("Invalid imposter reference");bool value=boolean(row[1]);c->occupants.are_imposters[id]=value;c->characters.set_imposter(id,value);}
    c->occupants.exiles_on_days.clear();for(const auto& row:o.at("exiles_days")){if(!row.is_array()||row.size()!=2)throw std::invalid_argument("Malformed exile day row");auto day=integer(row[0],0,1000);auto ids=row[1];if(!ids.is_array())throw std::invalid_argument("Malformed exile references");std::vector<std::int32_t> types;for(const auto& raw:ids){auto id=integer(raw,0,10000);if(!c->characters.find(id))throw std::invalid_argument("Invalid exile reference");types.push_back(id);}if(c->occupants.exiles_on_days.count(day))throw std::invalid_argument("Duplicate exile day");c->occupants.exiles_on_days[day]=std::move(types);}
    c->occupants.came_in_days.clear();for(const auto& row:o.at("came_in")){auto id=integer(row[0],0,10000),day=integer(row[1],0,1000);if(!c->characters.find(id))throw std::invalid_argument("Invalid arrival reference");c->occupants.came_in_days.emplace_back(id,day);}
    const auto& pose=j.at("world_pose");auto pos=pose.at("position");if(!pos.is_array()||pos.size()!=3)throw std::invalid_argument("Invalid world position");for(int i=0;i<3;++i){if(!pos[i].is_number())throw std::invalid_argument("World position must be numeric");double v=pos[i].get<double>();if(!std::isfinite(v)||std::abs(v)>1000)throw std::invalid_argument("World position outside bounds");c->world_pose.position[i]=v;}if(!pose.at("yaw").is_number()||!pose.at("pitch").is_number())throw std::invalid_argument("World orientation must be numeric");c->world_pose.yaw=pose.at("yaw").get<double>();c->world_pose.pitch=pose.at("pitch").get<double>();c->world_pose.revision=integer(pose.at("revision"),0,INT32_MAX);if(!std::isfinite(c->world_pose.yaw)||std::abs(c->world_pose.yaw)>3600||!std::isfinite(c->world_pose.pitch)||c->world_pose.pitch < -80||c->world_pose.pitch>80)throw std::invalid_argument("Invalid world orientation");
    c->rng.seed(0);std::istringstream random(j.at("rng").get<std::string>());if(!(random>>c->rng))throw std::invalid_argument("Invalid random engine state");random>>std::ws;if(!random.eof())throw std::invalid_argument("Invalid random engine trailing data");
    c->phase=j.at("phase").get<std::string>();if(c->phase!="menu"&&c->phase!="intro"&&c->phase!="playing"&&c->phase!="boundary"&&c->phase!="tools")throw std::invalid_argument("Invalid save phase");
    c->view_mode=j.at("view_mode").get<std::string>();if(c->view_mode!="world"&&c->view_mode!="room")throw std::invalid_argument("Invalid view mode");
    c->character=j.at("character").get<std::string>();if(!c->character.empty()&&c->character!="TV"&&c->characters.parse_name(c->character,true)<0)throw std::invalid_argument("Unknown save character");
    c->dialogue=j.at("dialogue").get<std::string>();c->has_session=boolean(j.at("has_session"));c->active_node=j.at("active_node").get<std::string>();
    if(c->has_session&&c->active_node.empty())throw std::invalid_argument("Session save has no active node");
    c->room=integer(j.at("room"),0,6);c->boundary_return_phase=j.at("boundary_return").get<std::string>();c->boundary_reason=j.at("boundary_reason").get<std::string>();
    c->intro_elapsed_ms=integer(j.at("intro_elapsed"),0,72000);c->campaign_elapsed_ms=integer(j.at("campaign_elapsed"),0,INT32_MAX);
    c->door_waiting=boolean(j.at("door_waiting"));c->door_opened=boolean(j.at("door_opened"));c->fridge_active=boolean(j.at("fridge"));c->neighbour_talk_completed=boolean(j.at("neighbour_talk_completed"));
    c->completed_preset_visits=integer(j.at("completed_visits"),0,1000);c->transition_pending=boolean(j.at("transition"));c->morning_tv_pending=boolean(j.at("tv_pending"));c->morning_tv_complete=boolean(j.at("tv_complete"));c->didnt_check_signs_days=integer(j.at("didnt_check_signs"),0,1000);c->pending_neighbour_talks=integer(j.at("pending_talks"),0,100000);c->committed_neighbour_talks=integer(j.at("committed_talks"),0,100000);c->completed_dialogue_snapshot=j.at("completed_dialogue").get<std::string>();
    c->deficit_day=integer(j.at("deficit_day"),0,1000);
    const auto& fl=j.at("flags");c->flags={boolean(fl.at("begun")),boolean(fl.at("saved")),boolean(fl.at("rude")),boolean(fl.at("death")),boolean(fl.at("mushroom")),boolean(fl.at("vigilante"))};
    c->phones_initialized=boolean(j.at("phones_initialized"));c->phone_numbers.entries.clear();for(const auto& row:j.at("phone_numbers")){int id=integer(row[0],1,15);auto number=row[1].get<std::string>();if(number.size()!=6||!std::all_of(number.begin(),number.end(),[](unsigned char ch){return std::isdigit(ch);}))throw std::invalid_argument("Invalid phone number in save");c->phone_numbers.add(static_cast<PhoneSubscriber>(id),std::move(number));}
    if(c->phones_initialized&&c->phone_numbers.entries.size()!=15)throw std::invalid_argument("Initialized phone table is incomplete");
    c->unlocked_phone_subscribers=int_list(j.at("unlocked"),1,15);
    const auto& ps=j.at("presentation");PresentationState presentation(catalog_);PresentationState::Snapshot pv=presentation.snapshot();pv.dialog_companion=ps.at("dialog_companion").get<std::string>();
    if(ps.at("emotion").is_null())pv.emotion.reset();else{const auto id=integer(ps.at("emotion"),INT32_MIN,INT32_MAX);const auto names=presentation_data::emotion_names();if(std::none_of(names.begin(),names.end(),[&](const auto& entry){return entry.second==id;}))throw std::invalid_argument("Unknown presentation emotion");pv.emotion=id;}
    pv.gun_shown=ps.at("gun_shown").is_null()?std::nullopt:std::optional<bool>(boolean(ps.at("gun_shown")));
    auto valid_pose=[&](const std::string& name,int state){const auto* record=catalog_.find(name);if(!record)return false;return std::any_of(record->poses.begin(),record->poses.end(),[&](const PresentationPose& pose){return pose.state==state;});};
    auto readposes=[&](const Json& a){std::vector<PoseChange> v;if(!a.is_array())throw std::invalid_argument("Invalid pose schedule");for(const auto& row:a){if(!row.is_array()||row.size()!=2||!row[0].is_string())throw std::invalid_argument("Malformed pose change");auto name=row[0].get<std::string>();int state=integer(row[1],0,100000);if(!valid_pose(name,state))throw std::invalid_argument("Unknown pose state");v.push_back({name,state});}return v;};pv.immediate_poses=readposes(ps.at("immediate"));pv.tomorrow_poses=readposes(ps.at("tomorrow"));pv.live_poses.clear();if(!ps.at("live").is_object())throw std::invalid_argument("Invalid live pose map");for(auto it=ps.at("live").begin();it!=ps.at("live").end();++it){int state=integer(it.value(),0,100000);if(!valid_pose(it.key(),state))throw std::invalid_argument("Unknown live pose state");pv.live_poses[it.key()]=state;}presentation.restore(pv);
    if(!pv.dialog_companion.empty()&&!catalog_.find(pv.dialog_companion))throw std::invalid_argument("Unknown presentation companion");
    if(!ps.at("sign").is_null()){
      const auto& sg=ps.at("sign");auto who=sg.at("character").get<std::string>();if(!catalog_.find(who))throw std::invalid_argument("Unknown sign character");
      auto sign_id=integer(sg.at("sign"),0,5);bool imposter=boolean(sg.at("imposter"));
      const char* sign_names[]={"Eye","Hands","Teeth","AuraPhoto","Armpit","Ear"};
      if(presentation.show_sign(who,sign_names[sign_id],imposter)!=PresentationResult::Applied)throw std::invalid_argument("Invalid presentation sign");
      pv=presentation.snapshot();
    }
    c->presentation.restore(presentation.snapshot());c->presentation_snapshot=presentation.snapshot();
    // Construct the VM against the candidate's restored services before committing the slot.
    auto validate_vm=[&](const std::string& snapshot){auto vm=std::make_unique<DialogueSession>(program_,metadata_,functions_,commands_,c->characters,option_callbacks(),[this](const std::string& text){return immediate_command(text);});vm->restore_snapshot(snapshot);};
    if(!c->completed_dialogue_snapshot.empty())validate_vm(c->completed_dialogue_snapshot);
    if(c->has_session)validate_vm(c->dialogue);
    saved_=std::move(c);log("Save versionado importado; use Continuar para restaurar");
  }
  static bool contains(const std::vector<std::int32_t>& v,std::int32_t id){return std::find(v.begin(),v.end(),id)!=v.end();}
  bool night_events_complete()const{
    return phase_=="playing" && static_cast<std::size_t>(completed_preset_visits_)>=
      preset_visits_for_day(characters_,energy_.day).size();
  }
  bool can_sleep()const{
    return phase_=="playing"&&view_mode_=="room"&&room_==6&&!session_&&!transition_pending_
      &&energy_.day==0&&progression_.time_of_day==TimeOfDay::Night&&night_events_complete();
  }
  bool can_watch_morning_tv()const{
    return phase_=="playing"&&view_mode_=="room"&&room_==6&&!session_&&!transition_pending_
      &&energy_.day==1&&progression_.time_of_day==TimeOfDay::Day&&morning_tv_pending_;
  }
  void sleep(){
    if(!can_sleep())throw std::logic_error("Só é possível dormir no quarto após concluir as visitas desta noite");
    // Keep this adapter bounded to the first morning, with explicit pending
    // state checks before any transition or manager mutation can occur.
    if(!occupants_.self_kill_next_day.empty()||occupants_.exiles_on_days.count(1)
       ||!progression_.coffee_days.empty())
      throw std::logic_error("Há efeitos agendados que esta passagem de dia ainda não apresenta");
    ProgressionHost host;
    host.all_night_ding_dongs_complete=[this](std::int32_t day){return day==0&&night_events_complete();};
    host.update_talks_count=[this]{committed_neighbour_talks_+=pending_neighbour_talks_;pending_neighbour_talks_=0;};
    host.start_visual_transition=[this](TimeOfDay target){
      if(target!=TimeOfDay::Day)throw std::logic_error("A próxima noite ainda não está integrada");
      transition_pending_=true;
    };
    host.current_time=[this]{return static_cast<float>(campaign_elapsed_ms_)/1000.0f;};
    if(request_daynight_change(progression_,host)!=TransitionResult::started)
      throw std::logic_error("O objetivo da noite ainda não foi concluído");
    log("Noite concluída; transição para a primeira manhã iniciada");
  }
  void complete_day_transition(){
    if(!transition_pending_||phase_!="playing"||energy_.day!=0||progression_.time_of_day!=TimeOfDay::Day)
      throw std::logic_error("Não há uma virada de dia aguardando conclusão");
    if(didnt_check_signs_days_+1>=production::morning::prophet_no_signs_days)
      throw std::logic_error("A consequência de inspeções pendentes ainda não está integrada");
    ProgressionHost host;
    host.run_morning_of_suicides=[this]{
      if(!occupants_.self_kill_next_day.empty())throw std::logic_error("Suicídios agendados não estão integrados");
      occupants_.self_kill_next_day.clear();
    };
    host.poses_changed=[this]{presentation_->apply_tomorrow_poses();};
    // The presentation event above consumes its pending pose schedule.
    host.clear_change_poses_tomorrow=[]{};
    host.character_counts=[this]()->std::optional<CharacterCountsSnapshot>{
      std::int32_t imposters=0,innocents=0;
      for(const auto type:occupants_.characters.inside){if(characters_.at(type).is_imposter)++imposters;else ++innocents;}
      return CharacterCountsSnapshot{imposters,static_cast<std::int32_t>(people_.possible_characters_to_kill(energy_.day).size()),innocents};
    };
    host.day_changed=[this](std::int32_t day){log("Dia "+std::to_string(day)+" iniciado pelas regras recuperadas");};
    // GameEventsManager.BeginNewDay is literally Return in the source dump.
    host.events_begin_new_day=[]{};
    host.characters_begin_new_day=[this](std::int32_t day){people_.begin_new_day(day,production::morning::every_day_fema_increment);};
    // No sign inspection is reachable in the bounded night-0 gameplay path.
    host.refresh_dialog_sign_checks=[this]{++didnt_check_signs_days_;};
    // Source BeginNewDay resets this counter; inventory and TodayUsed survive.
    host.consumables_begin_new_day=[this]{inventory_state_.povistkas_used=0;};
    initialize_new_day(progression_,ProgressionConfig{production::day_config(),production::morning::coffee_boost_days,production::last_day},host);
    transition_pending_=false;morning_tv_pending_=true;morning_tv_complete_=false;
    door_waiting_=door_opened_=false;room_=6;view_mode_="room";
    log("Primeira manhã disponível; a TV original pode ser assistida no quarto");
  }
  void watch_morning_tv(){
    if(!can_watch_morning_tv())throw std::logic_error("O noticiário desta manhã não está disponível neste cômodo");
    set_dialog_character("TV");start_session("tv_1_necessary");
    morning_tv_pending_=false;log("Noticiário original iniciado: tv_1_necessary");
  }
  void start_session(const std::string& node){
    auto next=std::make_unique<DialogueSession>(program_,metadata_,functions_,commands_,characters_,option_callbacks(),
      [this](const std::string& text){return immediate_command(text);});
    // Yarn variables and visited nodes belong to the game, not one conversation.
    if(!completed_dialogue_snapshot_.empty())next->restore_snapshot(completed_dialogue_snapshot_);
    active_node_=node;session_=std::move(next);session_->start(node);
  }
  void set_world_pose(const Json& pose){
    const auto& p=pose.at("position");
    if(!p.is_array()||p.size()!=3)throw std::invalid_argument("world_pose.position must have three components");
    WorldPose candidate=world_pose_;
    for(std::size_t i=0;i<3;++i){
      if(!p.at(i).is_number())throw std::invalid_argument("world_pose.position must be numeric");
      const double value=p.at(i).get<double>();
      if(!std::isfinite(value)||std::abs(value)>1000.0)throw std::invalid_argument("world_pose.position is outside the source world bounds");
      candidate.position[i]=value;
    }
    if(!pose.at("yaw").is_number()||!pose.at("pitch").is_number())throw std::invalid_argument("world_pose yaw and pitch must be numeric");
    candidate.yaw=pose.at("yaw").get<double>();candidate.pitch=pose.at("pitch").get<double>();
    if(!std::isfinite(candidate.yaw)||std::abs(candidate.yaw)>3600.0||!std::isfinite(candidate.pitch)||candidate.pitch<-80.0||candidate.pitch>80.0)
      throw std::invalid_argument("world_pose yaw or pitch is outside source camera limits");
    candidate.revision=++world_revision_;world_pose_=candidate;
  }
  static bool is_stopped(const DialogueSession* s){return s&&Json::parse(s->current_event()).value("type","")=="stopped";}
  static const char* intro_node(std::int64_t t){
    if(t>=59000&&t<72000) return "Intro_5";
    if(t>=43000&&t<52000) return "Intro_4";
    if(t>=28000&&t<34000) return "Intro_3";
    if(t>=20000&&t<23000) return "Intro_2";
    if(t>=10000&&t<18000) return "Intro_1";
    return "";
  }
  static Json intro_line_ids(std::int64_t t){
    const auto n=intro_node(t);
    if(std::string(n)=="Intro_1")return Json::array({"line:Intro_1_0cdc98a","line:Intro_1_0a7cf30"});
    if(std::string(n)=="Intro_2")return Json::array({"line:Intro_2_084b500"});
    if(std::string(n)=="Intro_3")return Json::array({"line:Intro_3_085ae9a","line:Intro_3_07d5c28"});
    if(std::string(n)=="Intro_4")return Json::array({"line:Intro_4_0e3fe2e","line:Intro_4_04248a3"});
    if(std::string(n)=="Intro_5")return Json::array({"line:Intro_5_0047cb3","line:Intro_5_05f8fce"});
    return Json::array();
  }
  std::int32_t random_range(std::int32_t lo,std::int32_t hi){
    if(hi<=lo) return lo;
    std::uniform_int_distribution<std::int32_t> d(lo,hi-1);
    return d(rng_);
  }
  LetInInputs let_in_inputs(std::int32_t type)const{
    if(type!=3)throw std::logic_error("LetIn inputs currently wired only for Neighbour");
    // _isHuman=0.2 and Neighbour's FEMA bonus=0. Status percentages are unused
    // for this fixed-status visitor; zero is an explicit sentinel.
    return LetInInputs{0.2f,0.0f,0.0f,0.0f};
  }
  OccupantsHooks occupant_hooks(){
    OccupantsHooks hooks;
    hooks.room_add_character=[this](std::int32_t room,std::int32_t type,bool){
      const auto* source=characters_.find(type); if(!source)return false;
      const auto* view=catalog_.find(source->name);
      if(!view||view->room_enum!=room||source->room!=room)return false;
      const auto packet=presentation_->room_packet(source->name);
      return packet&&packet->room_enum==room;
    };
    hooks.unity_random_value=[this]{std::uniform_real_distribution<float>d(0.0f,1.0f);return d(rng_);};
    hooks.unity_random_range=[this](std::int32_t lo,std::int32_t hi){return random_range(lo,hi);};
    return hooks;
  }
  DialogueServiceHooks dialogue_service_hooks(){
    DialogueServiceHooks hooks;
    hooks.is_ever_completed_game=[] {return std::optional<bool>(false);};
    hooks.is_need_to_get_deficit_item=[this]{return std::optional<bool>(deficit_service_.is_need_to_get_item());};
    hooks.peek_deficit_item=[this]{return std::optional<std::string>(consumable_enum_name(deficit_service_.get_deficit_item()));};
    return hooks;
  }
  StoryStateQueries story_queries(){
    StoryStateQueries q;
    q.required_achievement=[this](std::string_view raw,bool){log("Conquista local de teste: "+std::string(raw));};
    return q;
  }
  OptionCallbacks option_callbacks(){
    OptionCallbacks callbacks;
    callbacks.energy_consumed=[this]{energy_.act();log("Energia consumida pela escolha original");};
    callbacks.were_bad_boy=[this]{if(!character_.empty())story_.on_were_bad_boy(characters_.parse_name(character_,true));};
    return callbacks;
  }
  bool immediate_command(const std::string& text){
    if(text=="SetFridgeActiveState true"){fridge_active_=true;return true;}
    if(text=="SetFridgeActiveState false"){fridge_active_=false;return true;}
    if(text=="UnlockPhoneNumber Neighbour"){
      if(!phones_initialized_||!phone_numbers_.contains(PhoneSubscriber::Neighbour))
        throw std::logic_error("Neighbour phone number is not initialized");
      const auto id=static_cast<std::int32_t>(PhoneSubscriber::Neighbour);
      if(std::find(unlocked_phone_subscribers_.begin(),unlocked_phone_subscribers_.end(),id)==unlocked_phone_subscribers_.end())
        unlocked_phone_subscribers_.push_back(id);
      return true;
    }
    return router_->dispatch(text);
  }
  void rebuild_router(){
    SceneCommandHooks h;h.gun_state_selected=[this](bool selected){
      const auto type=characters_.parse_name(character_,true);
      occupants_.fema_rating.at(type)+=selected?-0.699999988079071f:0.5f;
    };
    router_=std::make_unique<SceneCommandRouter>(characters_,presentation_.get(),&story_,std::move(h));
  }
  void focus(const std::string& raw){
    const auto& c=characters_.at(characters_.parse_name(raw,true));
    if(!catalog_.find(c.name))throw std::invalid_argument("Personagem sem dados de cena neste teste");
    session_.reset();character_=c.name;room_=catalog_.find(c.name)->room_enum;
    occupants_.fema_rating.try_emplace(c.type,0.0f);
    presentation_->set_dialog_companion(c.name);presentation_->set_emotion("Base");presentation_->stop_showing_sign();
  }
  void set_dialog_character(const std::string& raw){
    const auto& c=characters_.at(characters_.parse_name(raw,true));character_=c.name;
    presentation_->set_dialog_companion(c.name);presentation_->set_emotion("Base");presentation_->stop_showing_sign();
  }
  void scenario(const std::string& name){
    const std::string who=name=="fatman"?"Fatman":name=="firefighter"?"Firefighter":name=="alkonost"?"Alkonost":"";
    const std::string node=name=="fatman"?"Fatman_Asking_1_1_1":name=="firefighter"?"Firefighter_Entrance_GoAway":name=="alkonost"?"Alkonost_Asking_6":"";
    if(who.empty())throw std::invalid_argument("Sequência de teste desconhecida");
    session_.reset();active_node_.clear();completed_dialogue_snapshot_.clear();phase_="tools";progression_=ProgressionState{};energy_.day=13;energy_.refill(production::day_config());
    inventory_state_=InventoryState::initial(false);occupants_=OccupantsState{};flags_=Flags{};deficit_item_day_=0;
    rng_.seed(0x4e494e41u);presentation_=std::make_unique<PresentationState>(catalog_);rebuild_router();focus(who);
    session_=std::make_unique<DialogueSession>(program_,metadata_,functions_,commands_,characters_,option_callbacks(),
      [this](const std::string& text){return immediate_command(text);});
    active_node_=node;session_->start(node);log("Sequência original de teste: "+node);
  }
  void new_game(){
    session_.reset();active_node_.clear();completed_dialogue_snapshot_.clear();progression_=ProgressionState{};
    progression_.time_of_day=TimeOfDay::Night;energy_.day=0;energy_.remaining=1;
    inventory_state_=InventoryState::initial(false);occupants_=OccupantsState{};characters_=production::character_catalog();
    flags_=Flags{};phone_numbers_=PhoneNumbers{};unlocked_phone_subscribers_.clear();phones_initialized_=false;
    rng_.seed(0x4e494e41u);deficit_item_day_=0;room_=5;character_.clear();phase_="intro";
    intro_elapsed_ms_=campaign_elapsed_ms_=0;door_waiting_=door_opened_=fridge_active_=false;
    neighbour_talk_completed_=false;completed_preset_visits_=0;
    transition_pending_=morning_tv_pending_=morning_tv_complete_=false;
    didnt_check_signs_days_=pending_neighbour_talks_=committed_neighbour_talks_=0;
    world_pose_=WorldPose{};world_pose_.revision=++world_revision_;view_mode_="world";
    boundary_reason_.clear();boundary_return_phase_.clear();presentation_=std::make_unique<PresentationState>(catalog_);rebuild_router();
    log("Novo jogo; estado original de dia 0 preparado e introdução aberta");
  }
  void finish_intro_video(){
    if(phase_!="intro")return;
    if(intro_elapsed_ms_<72000)throw std::logic_error("O vídeo de introdução ainda não chegou ao fim");
    if(!phones_initialized_){phone_service_.generate_numbers(phone_numbers_);phones_initialized_=true;}
    phase_="playing";room_=5;campaign_elapsed_ms_=0;door_waiting_=door_opened_=false;
    log("Vídeo concluído; sessão limitada iniciou na Entrada");
  }
  void open_door(){
    if(phase_!="playing"||!door_waiting_||door_opened_||night_events_complete())
      throw std::logic_error("Nenhum visitante pendente está aguardando na porta");
    door_waiting_=false;door_opened_=true;room_=5;view_mode_="room";set_dialog_character("Neighbour");
    start_session("entrance_neighbour_0");log("Diálogo de entrada iniciado: entrance_neighbour_0");
  }
  void actor_talk(const std::string& raw){
    if(phase_!="playing"||session_||view_mode_!="room")throw std::logic_error("Não há espaço para iniciar uma conversa");
    const auto type=characters_.parse_name(raw,true);
    if(type!=3||!contains(occupants_.characters.inside,type))
      throw std::logic_error("Esse personagem ainda não está dentro da casa");
    if(neighbour_talk_completed_)
      throw std::logic_error("Não há outro diálogo de Neighbour verificado depois de talk_neighbour_1");
    const auto* source=characters_.find(type);
    const auto* view=catalog_.find(source->name);
    const auto packet=presentation_->room_packet(source->name);
    if(!view||!packet||view->room_enum!=source->room||packet->room_enum!=source->room)
      throw std::logic_error("O cômodo de Neighbour não possui apresentação integrada");
    room_=source->room;view_mode_="room";set_dialog_character(source->name);active_node_="talk_neighbour_1";
    start_session("talk_neighbour_1");log("Primeiro diálogo dentro da casa iniciado: talk_neighbour_1");
  }
  void finish_current_dialogue(){
    completed_dialogue_snapshot_=session_->dump_snapshot();
    if(active_node_=="entrance_neighbour_0"){
      if(completed_preset_visits_<1)++completed_preset_visits_;
      session_.reset();active_node_.clear();character_.clear();view_mode_="world";
      door_opened_=false;
      log(contains(occupants_.characters.inside,3)?"Visita da Neighbour concluída; a casa permanece explorável":"Visita da Neighbour concluída sem admissão; a casa permanece explorável");return;
    }
    if(active_node_=="talk_neighbour_1"){neighbour_talk_completed_=true;++pending_neighbour_talks_;}
    if(active_node_=="tv_1_necessary")morning_tv_complete_=true;
    session_.reset();active_node_.clear();character_.clear();view_mode_="world";
    log("Conversa encerrada; exploração da casa retomada");
  }
  void enter_boundary(const std::string& text){phase_="boundary";boundary_return_phase_="playing";boundary_reason_=text;
    log("Limite da sequência inicial alcançado");}
  void save(){saved_=std::make_unique<Snapshot>(*this);log("Estado salvo na memória desta execução");}
  void load(){
    if(!saved_)throw std::logic_error("Nenhum estado salvo nesta execução");
    std::unique_ptr<DialogueSession> restored;
    if(saved_->has_session){restored=std::make_unique<DialogueSession>(program_,metadata_,functions_,commands_,characters_,option_callbacks(),
      [this](const std::string& text){return immediate_command(text);});restored->restore_snapshot(saved_->dialogue);}
    auto presentation=std::make_unique<PresentationState>(saved_->presentation);presentation->restore(saved_->presentation_snapshot);session_.reset();
    progression_=saved_->progression;inventory_state_=saved_->inventory;occupants_=saved_->occupants;characters_=saved_->characters;
    phone_numbers_=saved_->phone_numbers;unlocked_phone_subscribers_=saved_->unlocked_phone_subscribers;
    phones_initialized_=saved_->phones_initialized;
    neighbour_talk_completed_=saved_->neighbour_talk_completed;
    completed_preset_visits_=saved_->completed_preset_visits;
    transition_pending_=saved_->transition_pending;morning_tv_pending_=saved_->morning_tv_pending;
    morning_tv_complete_=saved_->morning_tv_complete;didnt_check_signs_days_=saved_->didnt_check_signs_days;
    pending_neighbour_talks_=saved_->pending_neighbour_talks;committed_neighbour_talks_=saved_->committed_neighbour_talks;
    completed_dialogue_snapshot_=saved_->completed_dialogue_snapshot;
    world_pose_=saved_->world_pose;view_mode_=saved_->view_mode;world_pose_.revision=++world_revision_;
    flags_=saved_->flags;rng_=saved_->rng;deficit_item_day_=saved_->deficit_day;character_=saved_->character;room_=saved_->room;
    phase_=saved_->phase;active_node_=saved_->active_node;boundary_return_phase_=saved_->boundary_return_phase;boundary_reason_=saved_->boundary_reason;
    intro_elapsed_ms_=saved_->intro_elapsed_ms;campaign_elapsed_ms_=saved_->campaign_elapsed_ms;
    door_waiting_=saved_->door_waiting;door_opened_=saved_->door_opened;fridge_active_=saved_->fridge_active;
    presentation_.swap(presentation);rebuild_router();session_=std::move(restored);log("Estado retomado sem repetir comandos já emitidos");
  }
  void log(std::string s){logs_.push_back(std::move(s));if(logs_.size()>16)logs_.erase(logs_.begin());}

  std::string program_,metadata_; ProgressionState progression_; EnergyState& energy_=progression_.energy;
  CharacterCatalog characters_; OccupantsState occupants_;
  InventoryState inventory_state_; Inventory inventory_; PresentationCatalog catalog_;
  std::unique_ptr<PresentationState> presentation_; std::mt19937 rng_{0x4e494e41u};
  PhoneNumbers phone_numbers_; PhoneNumberService phone_service_; std::vector<std::int32_t> unlocked_phone_subscribers_;
  bool phones_initialized_=false;
  bool neighbour_talk_completed_=false;
  std::int32_t completed_preset_visits_=0;
  bool transition_pending_=false,morning_tv_pending_=false,morning_tv_complete_=false;
  std::int32_t didnt_check_signs_days_=0,pending_neighbour_talks_=0,committed_neighbour_talks_=0;
  std::string completed_dialogue_snapshot_;
  DeficitConsumableTargets deficit_targets_; std::int32_t deficit_item_day_=0;
  ConsumablesDeficitService deficit_service_; OccupantsRuntime people_;
  DialogueCommandDispatcher commands_; DialogueServices functions_; Flags flags_; StoryState story_;
  std::unique_ptr<SceneCommandRouter> router_; std::unique_ptr<DialogueSession> session_;
  std::unique_ptr<Snapshot> saved_; std::string character_,error_,phase_="menu",active_node_;
  std::string boundary_reason_,boundary_return_phase_;std::int64_t intro_elapsed_ms_=0,campaign_elapsed_ms_=0;
  int room_=5;bool door_waiting_=false,door_opened_=false,fridge_active_=false;std::vector<std::string> logs_;
  WorldPose world_pose_{};std::string view_mode_="world";std::int64_t world_revision_=0;
};

std::unique_ptr<Context> context;
std::string create(const std::string& program,const std::string& metadata){
  try{auto fresh=std::make_unique<Context>(program,metadata);context.swap(fresh);return context->state().dump(-1,' ',true);}
  catch(const std::exception& e){return Json({{"type","error"},{"error",e.what()}}).dump(-1,' ',true);}
}
std::string action(const std::string& raw){
  try{if(!context)throw std::logic_error("Núcleo não iniciado");return context->action(Json::parse(raw)).dump(-1,' ',true);}
  catch(const std::exception& e){return Json({{"type","error"},{"error",e.what()}}).dump(-1,' ',true);}
}
} // namespace ninah::current

#ifdef __ANDROID__
namespace {
std::string input(JNIEnv* env,jstring value){
  if(!value)throw std::invalid_argument("null JNI input");const char* chars=env->GetStringUTFChars(value,nullptr);
  if(!chars)throw std::runtime_error("JNI string allocation failed");std::string result(chars);env->ReleaseStringUTFChars(value,chars);return result;
}
}
extern "C" JNIEXPORT jstring JNICALL Java_org_reconstruction_current_MainActivity_nativeCreate(JNIEnv* env,jclass,jstring program,jstring metadata){
  try{const auto result=ninah::current::create(input(env,program),input(env,metadata));return env->NewStringUTF(result.c_str());}
  catch(const std::exception& e){const auto result=nlohmann::json({{"type","error"},{"error",e.what()}}).dump(-1,' ',true);return env->NewStringUTF(result.c_str());}
}
extern "C" JNIEXPORT jstring JNICALL Java_org_reconstruction_current_MainActivity_nativeAction(JNIEnv* env,jclass,jstring action){
  try{const auto result=ninah::current::action(input(env,action));return env->NewStringUTF(result.c_str());}
  catch(const std::exception& e){const auto result=nlohmann::json({{"type","error"},{"error",e.what()}}).dump(-1,' ',true);return env->NewStringUTF(result.c_str());}
}
#endif
