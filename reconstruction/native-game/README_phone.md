# Recovered phone-number model

`ninah::PhoneNumberService` models the recovered subscriber-number behavior. The host supplies Unity-compatible RNG callbacks explicitly; the model owns no PRNG or invented seed. Integer bounds are exclusive as in `Random.Range(int,int)`. Fixed subscriber numbers are generated into a C++ factory by `tools/reverse-phone/generate_phone_data.py` from fully parsed `other_game_data.json` and are never typed into that generator by hand.

The number builder selects one of five recovered patterns, emits six digit characters, applies the observed repeated-digit / neighboring-digit branches, and retries on duplicate numbers or equal three-digit halves. `PhoneNumbers` preserves insertion order to match dictionary enumeration. `PhoneNumbers::add` throws on duplicate subscriber keys, mirroring `Dictionary.Add`. A missing lookup returns the literal `000000`; phone matching uses exact string equality and returns the first insertion-order match, or false with `None` when absent.

The current provider generator is `tools/reverse-phone/generate_phone_provider.py`.
It reads `reconstruction/reverse-phone/other_game_data.json`, validates the
decoded source fields and emits `generated/production_phone.hpp`. Both the JSON
and generated provider are present. The older `generate_phone_data.py` path
describes a previous recovery stage.

The original view initializes phone numbers, asks the controller for numbers while creating/restoring pins, and adds a subscriber to the unlocked list before pin creation. The model leaves pin/UI actions to the caller.

Build the standalone regression test:

```sh
g++ -std=c++17 -Wall -Wextra -Werror -pedantic \
  -Ireconstruction/native-game/include \
  reconstruction/native-game/src/phone.cpp \
  reconstruction/native-game/tests/phone_tests.cpp \
  -o /tmp/ninah-phone-tests
/tmp/ninah-phone-tests
```

Evidence and the current checkpoint limitation are listed in `reconstruction/reverse-phone/phone_evidence.md`. No original executable code was run.
