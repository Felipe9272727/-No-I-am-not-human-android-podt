# Evidence notes

The compact evidence files alongside this note are excerpts copied from the recovered selected native disassembly of `GameAssembly.dll` and Cpp2IL-generated managed IL. No game code was executed. The native listing has no original-entrypoint-to-method RVA mapping, so no such mapping is claimed.

- `IsEndingDay`: compares current day to configured last day.
- Day transition goal checks current energy exhaustion; night transition asks the event manager whether all ding-dongs for this night are complete.
- Both successful transition branches join before vibration and `WentToBed`, then time-of-day update, talk-count update, visual transition start, and `LastChange` normalization.
- `InitNewNight` runs the BodyEater kill path only when not loading save data and readiness is true.
- `InitNewDay` performs suicides and pose/count services before coffee expiry and energy maximum calculation. The latter reads current fines and extra slots after host callback effects.
- Coffee expiry decrements extra slots for every matured schedule, while native list removal removes one last remembered matured value.
- Save restore calls day/night initialization in restore mode and may emit the same-day courier visit.

The source hashes were not reverified after filesystem recovery. Managed IL headings contain generated managed assembly RVAs, not original native RVAs.
