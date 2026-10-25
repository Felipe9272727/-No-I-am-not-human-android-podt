# Day/night progression recovery

The rules in `daynight_rules.json` and the C++ adapter describe the static reconstruction recovered from earlier analysis notes. They require host callbacks for Unity managers and events whose implementation lives outside this state module. DayConfig is supplied from extracted production data; there are no invented threshold values. Signed 32-bit updates use explicit wrapping to match managed integer behavior.

No original game executable, DLL, or installer was executed. This recovery did not reverify source binary hashes.
