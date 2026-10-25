//! Small, data-driven model of verified IL2CPP state rules.
//!
//! This crate deliberately contains no production character catalogue, energy
//! configuration, inventory implementation, or progression defaults. Callers
//! must supply recovered game data and callback services.

use std::collections::BTreeMap;

/// Remaining daytime actions. `max_day_actions` is supplied by the caller;
/// this crate does not derive it from configuration, fines, or upgrades.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct EnergyState {
    pub day: i32,
    pub remaining: i32,
    pub extra_slots: i32,
    /// Fine counts keyed by day, matching the save-data dictionary.
    pub fines_by_day: BTreeMap<i32, i32>,
}

impl EnergyState {
    /// Native `Act` decrements unconditionally; availability is checked by callers.
    pub fn act(&mut self) {
        self.remaining = self.remaining.wrapping_sub(1);
    }

    /// Native `ActAll` sets remaining actions to zero.
    pub fn act_all(&mut self) {
        self.remaining = 0;
    }

    /// Adds one action only when the current value is below the explicit maximum.
    pub fn add_energy(&mut self, max_day_actions: i32) {
        if self.remaining < max_day_actions {
            self.remaining = self.remaining.wrapping_add(1);
        }
    }

    /// Replaces the remaining count with the explicit maximum.
    pub fn refill_energy(&mut self, max_day_actions: i32) {
        self.remaining = max_day_actions;
    }

    /// Adds a fine to the entry for `day + 1`, creating that entry if needed.
    pub fn add_fine_for_tomorrow(&mut self, energy_count: i32) {
        let next_day = self.day.wrapping_add(1);
        let entry = self.fines_by_day.entry(next_day).or_insert(0);
        *entry = entry.wrapping_add(energy_count);
    }

    /// Records the native `ExtraEnergySlots` increment. Its use in the
    /// configured maximum is intentionally left to the caller.
    pub fn add_extra_slot(&mut self) {
        self.extra_slots = self.extra_slots.wrapping_add(1);
    }

    /// Computes the native maximum from this day's serialized configuration,
    /// current fine, and extra slots. The native IL uses Int32 `sub`/`add`
    /// (unchecked), so arithmetic wraps as a 32-bit signed integer.
    pub fn configured_max_day_actions(
        &self,
        config: &ProductionDayConfig,
    ) -> Result<i32, ProductionConfigError> {
        let configured = *config
            .max_day_actions_by_days
            .get(usize::try_from(self.day).map_err(|_| ProductionConfigError::DayOutOfRange {
                day: self.day,
                entries: config.max_day_actions_by_days.len(),
            })?)
            .ok_or(ProductionConfigError::DayOutOfRange {
                day: self.day,
                entries: config.max_day_actions_by_days.len(),
            })?;
        let fine = self.fines_by_day.get(&self.day).copied().unwrap_or(0);
        Ok(configured
            .wrapping_sub(fine)
            .wrapping_add(self.extra_slots))
    }
}

/// Fully decoded `DayNightControllerSOData` fields needed by the native
/// `get_MaxDayActions` calculation.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProductionDayConfig {
    pub max_day_actions_by_days: Vec<i32>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ProductionConfigError {
    MalformedJson(String),
    MissingFullyParsedDayNightRecord,
    DayOutOfRange { day: i32, entries: usize },
}

impl std::fmt::Display for ProductionConfigError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::MalformedJson(message) => write!(f, "invalid production config JSON: {message}"),
            Self::MissingFullyParsedDayNightRecord => {
                write!(f, "no fully parsed DayNightControllerSOData record")
            }
            Self::DayOutOfRange { day, entries } => {
                write!(f, "day index {day} outside {entries} configured entries")
            }
        }
    }
}

impl std::error::Error for ProductionConfigError {}

impl ProductionDayConfig {
    /// Reads only record zero when it is explicitly marked complete in the
    /// asset extraction (`parsed_bytes_end == raw_bytes`, zero unparsed tail).
    /// Other asset records and partially decoded values are never substituted.
    pub fn from_production_configs_json(json: &str) -> Result<Self, ProductionConfigError> {
        let root: serde_json::Value = serde_json::from_str(json)
            .map_err(|error| ProductionConfigError::MalformedJson(error.to_string()))?;
        let record = root
            .get("day_night_controller_records")
            .and_then(serde_json::Value::as_array)
            .and_then(|records| records.first())
            .filter(|record| {
                record.get("class").and_then(serde_json::Value::as_str)
                    == Some("_Code.Infrastructure.DayNightControllerSOData")
                    && record.get("parsed_bytes_end").and_then(serde_json::Value::as_u64)
                        == record.get("raw_bytes").and_then(serde_json::Value::as_u64)
                    && record.get("unparsed_tail_bytes").and_then(serde_json::Value::as_u64)
                        == Some(0)
            })
            .ok_or(ProductionConfigError::MissingFullyParsedDayNightRecord)?;
        let values = record
            .get("max_day_actions_by_days")
            .and_then(serde_json::Value::as_array)
            .ok_or(ProductionConfigError::MissingFullyParsedDayNightRecord)?;
        let max_day_actions_by_days = values
            .iter()
            .map(|value| {
                value
                    .as_i64()
                    .and_then(|value| i32::try_from(value).ok())
                    .ok_or(ProductionConfigError::MissingFullyParsedDayNightRecord)
            })
            .collect::<Result<Vec<_>, _>>()?;
        Ok(Self { max_day_actions_by_days })
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CharacterRecord {
    /// Native enum spelling, such as `CharacterType.ToString()`.
    pub name: String,
    pub place: String,
    pub is_imposter: bool,
}

/// Explicit snapshot of recovered character records and current occupants.
/// No records are bundled with the crate.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct CharacterSnapshot {
    pub records: Vec<CharacterRecord>,
    pub inside: Vec<String>,
}

impl CharacterSnapshot {
    /// Mirrors the command lookup: exact name match, false when no data matches.
    pub fn is_imposter(&self, name: &str) -> bool {
        self.records
            .iter()
            .find(|record| record.name == name)
            .map(|record| record.is_imposter)
            .unwrap_or(false)
    }

    /// Counts current occupants classified as non-imposters.
    pub fn innocents_count(&self) -> usize {
        self.inside
            .iter()
            .filter(|name| !self.is_imposter(name))
            .count()
    }

    /// True when no current occupant resolves to the target character's place.
    /// An unknown target has no resolved place and is reported as an error.
    pub fn is_place_empty(&self, character_name: &str) -> Result<bool, StateError> {
        let place = self
            .records
            .iter()
            .find(|record| record.name == character_name)
            .map(|record| record.place.as_str())
            .ok_or(StateError::UnknownCharacter(character_name.to_owned()))?;
        let occupied = self.inside.iter().any(|inside_name| {
            self.records
                .iter()
                .find(|record| record.name == *inside_name)
                .map(|record| record.place == place)
                .unwrap_or(false)
        });
        Ok(!occupied)
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum StateError {
    UnavailableService(&'static str),
    UnknownCharacter(String),
}

impl std::fmt::Display for StateError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::UnavailableService(name) => write!(f, "service callback unavailable: {name}"),
            Self::UnknownCharacter(name) => write!(f, "character data unavailable: {name}"),
        }
    }
}

impl std::error::Error for StateError {}

/// Calls a recovered injected callback without silently substituting test data.
pub fn call_service<T>(
    service_name: &'static str,
    callback: Option<impl FnOnce() -> T>,
) -> Result<T, StateError> {
    callback
        .map(|call| call())
        .ok_or(StateError::UnavailableService(service_name))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn energy_mutations_match_native_assignments_and_guard() {
        let mut state = EnergyState { remaining: 1, ..EnergyState::default() };
        state.act();
        assert_eq!(state.remaining, 0);
        state.act(); // The native method itself does not clamp at zero.
        assert_eq!(state.remaining, -1);
        state.add_energy(2);
        assert_eq!(state.remaining, 0);
        state.add_energy(0);
        assert_eq!(state.remaining, 0);
        state.refill_energy(4);
        assert_eq!(state.remaining, 4);
        state.act_all();
        assert_eq!(state.remaining, 0);
    }

    #[test]
    fn fine_accumulates_on_next_day_and_preserves_existing_value() {
        let mut state = EnergyState { day: 3, ..EnergyState::default() };
        state.add_fine_for_tomorrow(2);
        state.add_fine_for_tomorrow(3);
        assert_eq!(state.fines_by_day.get(&4), Some(&5));
        assert_eq!(state.fines_by_day.len(), 1);
    }

    #[test]
    fn character_checks_use_explicit_records_and_current_occupancy() {
        let snapshot = CharacterSnapshot {
            records: vec![
                CharacterRecord { name: "A".into(), place: "Kitchen".into(), is_imposter: false },
                CharacterRecord { name: "B".into(), place: "Kitchen".into(), is_imposter: true },
                CharacterRecord { name: "C".into(), place: "Hall".into(), is_imposter: false },
            ],
            inside: vec!["B".into()],
        };
        assert!(snapshot.is_imposter("B"));
        assert!(!snapshot.is_imposter("missing"));
        assert_eq!(snapshot.innocents_count(), 0);
        assert_eq!(snapshot.is_place_empty("A"), Ok(false));
        assert_eq!(snapshot.is_place_empty("C"), Ok(true));
        assert_eq!(snapshot.is_place_empty("missing"), Err(StateError::UnknownCharacter("missing".into())));
    }

    #[test]
    fn missing_service_is_an_explicit_error() {
        let result: Result<i32, _> = call_service("GotEnergy", None::<fn() -> i32>);
        assert_eq!(result, Err(StateError::UnavailableService("GotEnergy")));
        assert_eq!(call_service("GotEnergy", Some(|| 7)), Ok(7));
    }

    #[test]
    fn production_config_maximum_uses_real_day_values_fine_and_extra_slots() {
        let path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../assets/gameplay_data/production_configs.json"
        );
        let json = std::fs::read_to_string(path).expect("checked-in recovered production config");
        let config = ProductionDayConfig::from_production_configs_json(&json).unwrap();
        assert_eq!(config.max_day_actions_by_days.len(), 19);
        assert_eq!(config.max_day_actions_by_days[0], 1);
        assert_eq!(config.max_day_actions_by_days[13], 4);
        assert_eq!(config.max_day_actions_by_days[14], 5);
        assert_eq!(config.max_day_actions_by_days[15], 0);

        let mut state = EnergyState { day: 4, ..EnergyState::default() };
        assert_eq!(state.configured_max_day_actions(&config), Ok(3));
        state.fines_by_day.insert(4, 2);
        state.extra_slots = 1;
        assert_eq!(state.configured_max_day_actions(&config), Ok(2));
    }

    #[test]
    fn production_config_rejects_malformed_partial_and_out_of_range_data() {
        assert!(matches!(
            ProductionDayConfig::from_production_configs_json("{"),
            Err(ProductionConfigError::MalformedJson(_))
        ));
        let partial = r#"{"day_night_controller_records":[{"class":"_Code.Infrastructure.DayNightControllerSOData","raw_bytes":10,"parsed_bytes_end":9,"unparsed_tail_bytes":1,"max_day_actions_by_days":[3]}]}"#;
        assert_eq!(
            ProductionDayConfig::from_production_configs_json(partial),
            Err(ProductionConfigError::MissingFullyParsedDayNightRecord)
        );
        let config = ProductionDayConfig { max_day_actions_by_days: vec![2] };
        let state = EnergyState { day: 1, ..EnergyState::default() };
        assert_eq!(
            state.configured_max_day_actions(&config),
            Err(ProductionConfigError::DayOutOfRange { day: 1, entries: 1 })
        );
    }
}
