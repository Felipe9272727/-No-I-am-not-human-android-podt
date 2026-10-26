// Current C++ gameplay host. Original Windows programs are never loaded.
#include "ninah/dialogue_session.hpp"
#include "ninah/arrivals.hpp"
#include "ninah/scene_commands.hpp"
#include "presentation_provider.hpp"
#include "production_characters.hpp"
#include "production_data.hpp"
#include "production_phone.hpp"
#include "../../native-game/third_party/nlohmann/json.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <memory>
#include <random>
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
        if(phase_=="playing"&&!door_opened_&&!night_events_complete()) {
          const auto t=a.at("elapsed_ms").get<std::int64_t>();
          if(t<0) throw std::invalid_argument("Tempo de campanha inválido");
          campaign_elapsed_ms_=std::max(campaign_elapsed_ms_,t);
          if(campaign_elapsed_ms_>=1000) door_waiting_=true;
        }
      } else if(name=="open_door") open_door();
      else if(name=="enter_world") {
        if(session_&&!is_stopped(session_.get()))throw std::logic_error("A conversa atual ainda está ativa");
        view_mode_="world";
      } else if(name=="enter_room") {
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
      {"save_scope","memória desta execução; não persiste ao fechar o aplicativo"}};
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
      Json c={{"day",energy_.day},{"time","night"},{"time_of_day","night"},{"energy",energy_.remaining},
        {"night_events_complete",night_events_complete()},
        {"door_waiting",door_waiting_},{"visitor",door_waiting_?"Neighbour":""},
        {"visitor_type",door_waiting_?3:0},{"fridge_active",fridge_active_},
        {"neighbour_inside",neighbour_inside},
        {"neighbour_can_talk",phase_=="playing"&&view_mode_=="room"&&neighbour_inside&&neighbour_data&&room_==neighbour_data->room&&!session_&&!neighbour_talk_completed_},
        {"neighbour_talk_count",neighbour_talk_completed_?1:0},
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
    EnergyState energy; InventoryState inventory; OccupantsState occupants; Flags flags;
    PhoneNumbers phone_numbers; std::vector<std::int32_t> unlocked_phone_subscribers; bool phones_initialized;
    WorldPose world_pose; std::string view_mode;
    CharacterCatalog characters; PresentationState presentation; std::mt19937 rng;
    std::int32_t deficit_day; std::string character,dialogue,phase,boundary_return_phase,boundary_reason,active_node;
    std::int64_t intro_elapsed_ms,campaign_elapsed_ms; int room;
    bool has_session,door_waiting,door_opened,fridge_active,neighbour_talk_completed;
    std::int32_t completed_preset_visits;
    explicit Snapshot(const Context& c):energy(c.energy_),inventory(c.inventory_state_),occupants(c.occupants_),
      flags(c.flags_),phone_numbers(c.phone_numbers_),unlocked_phone_subscribers(c.unlocked_phone_subscribers_),
      phones_initialized(c.phones_initialized_),world_pose(c.world_pose_),view_mode(c.view_mode_),characters(c.characters_),presentation(*c.presentation_),rng(c.rng_),deficit_day(c.deficit_item_day_),
      character(c.character_),dialogue(c.session_?c.session_->dump_snapshot():std::string{}),phase(c.phase_),
      boundary_return_phase(c.boundary_return_phase_),boundary_reason(c.boundary_reason_),active_node(c.active_node_),
      intro_elapsed_ms(c.intro_elapsed_ms_),campaign_elapsed_ms(c.campaign_elapsed_ms_),room(c.room_),
      has_session(static_cast<bool>(c.session_)),door_waiting(c.door_waiting_),door_opened(c.door_opened_),
      fridge_active(c.fridge_active_),neighbour_talk_completed(c.neighbour_talk_completed_),
      completed_preset_visits(c.completed_preset_visits_){}
  };
  static bool contains(const std::vector<std::int32_t>& v,std::int32_t id){return std::find(v.begin(),v.end(),id)!=v.end();}
  bool night_events_complete()const{
    return phase_=="playing" && static_cast<std::size_t>(completed_preset_visits_)>=
      preset_visits_for_day(characters_,energy_.day).size();
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
    session_.reset();active_node_.clear();phase_="tools";energy_=EnergyState{};energy_.day=13;energy_.refill(production::day_config());
    inventory_state_=InventoryState::initial(false);occupants_=OccupantsState{};flags_=Flags{};deficit_item_day_=0;
    rng_.seed(0x4e494e41u);presentation_=std::make_unique<PresentationState>(catalog_);rebuild_router();focus(who);
    session_=std::make_unique<DialogueSession>(program_,metadata_,functions_,commands_,characters_,option_callbacks(),
      [this](const std::string& text){return immediate_command(text);});
    active_node_=node;session_->start(node);log("Sequência original de teste: "+node);
  }
  void new_game(){
    session_.reset();saved_.reset();active_node_.clear();energy_=EnergyState{};energy_.day=0;energy_.remaining=1;
    inventory_state_=InventoryState::initial(false);occupants_=OccupantsState{};characters_=production::character_catalog();
    flags_=Flags{};phone_numbers_=PhoneNumbers{};unlocked_phone_subscribers_.clear();phones_initialized_=false;
    rng_.seed(0x4e494e41u);deficit_item_day_=0;room_=5;character_.clear();phase_="intro";
    intro_elapsed_ms_=campaign_elapsed_ms_=0;door_waiting_=door_opened_=fridge_active_=false;
    neighbour_talk_completed_=false;completed_preset_visits_=0;
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
    session_=std::make_unique<DialogueSession>(program_,metadata_,functions_,commands_,characters_,option_callbacks(),
      [this](const std::string& text){return immediate_command(text);});
    active_node_="entrance_neighbour_0";session_->start(active_node_);log("Diálogo de entrada iniciado: entrance_neighbour_0");
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
    session_=std::make_unique<DialogueSession>(program_,metadata_,functions_,commands_,characters_,option_callbacks(),
      [this](const std::string& text){return immediate_command(text);});
    session_->start(active_node_);log("Primeiro diálogo dentro da casa iniciado: talk_neighbour_1");
  }
  void finish_current_dialogue(){
    if(active_node_=="entrance_neighbour_0"){
      if(completed_preset_visits_<1)++completed_preset_visits_;
      session_.reset();active_node_.clear();character_.clear();view_mode_="world";
      door_opened_=false;
      log(contains(occupants_.characters.inside,3)?"Visita da Neighbour concluída; a casa permanece explorável":"Visita da Neighbour concluída sem admissão; a casa permanece explorável");return;
    }
    if(active_node_=="talk_neighbour_1")neighbour_talk_completed_=true;
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
    auto presentation=std::make_unique<PresentationState>(saved_->presentation);session_.reset();
    energy_=saved_->energy;inventory_state_=saved_->inventory;occupants_=saved_->occupants;characters_=saved_->characters;
    phone_numbers_=saved_->phone_numbers;unlocked_phone_subscribers_=saved_->unlocked_phone_subscribers;
    phones_initialized_=saved_->phones_initialized;
    neighbour_talk_completed_=saved_->neighbour_talk_completed;
    completed_preset_visits_=saved_->completed_preset_visits;
    world_pose_=saved_->world_pose;view_mode_=saved_->view_mode;world_pose_.revision=++world_revision_;
    flags_=saved_->flags;rng_=saved_->rng;deficit_item_day_=saved_->deficit_day;character_=saved_->character;room_=saved_->room;
    phase_=saved_->phase;active_node_=saved_->active_node;boundary_return_phase_=saved_->boundary_return_phase;boundary_reason_=saved_->boundary_reason;
    intro_elapsed_ms_=saved_->intro_elapsed_ms;campaign_elapsed_ms_=saved_->campaign_elapsed_ms;
    door_waiting_=saved_->door_waiting;door_opened_=saved_->door_opened;fridge_active_=saved_->fridge_active;
    presentation_.swap(presentation);rebuild_router();session_=std::move(restored);log("Estado retomado sem repetir comandos já emitidos");
  }
  void log(std::string s){logs_.push_back(std::move(s));if(logs_.size()>16)logs_.erase(logs_.begin());}

  std::string program_,metadata_; EnergyState energy_; CharacterCatalog characters_; OccupantsState occupants_;
  InventoryState inventory_state_; Inventory inventory_; PresentationCatalog catalog_;
  std::unique_ptr<PresentationState> presentation_; std::mt19937 rng_{0x4e494e41u};
  PhoneNumbers phone_numbers_; PhoneNumberService phone_service_; std::vector<std::int32_t> unlocked_phone_subscribers_;
  bool phones_initialized_=false;
  bool neighbour_talk_completed_=false;
  std::int32_t completed_preset_visits_=0;
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
