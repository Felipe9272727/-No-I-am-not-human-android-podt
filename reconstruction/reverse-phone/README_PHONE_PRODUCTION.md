# Fixed phone-number provider

`phone_fixed_numbers.json` records three values decoded directly from `OtherGameSOData._phoneNumbers`: FEMA (`000451`), Psychics (`777460`), and PhoneRoulette (`891533`). The object is `sharedassets0.assets` path ID 2715. Its raw size is 356 bytes and its SHA-256 is `f6c54b961c02a810320592e3ceb28c329e62a0134193ae26f47f0cd994d73a2f`. The selected source asset has SHA-256 `99a6ae7df177512a9fb2c27bb7c89e6fb8e1c14227fdd7b12e9fa42e564fb1d9`.

`decode_other_game_data.py` extracts only path IDs 2715 (`OtherGameData`) and 2713 (`EndingsData`) from `sharedassets0.assets`. It verifies both raw-object hashes before writing the preserved bytes. It decodes every declared `OtherGameSOData` field using the retained Cpp2IL declarations and checks that the field layout consumes the full 356-byte object, including aligned `DreamData` and serialized dictionary entries. The 64-byte `EndingsData` object is also parsed and fully consumed. No PE or DLL is executed.

Re-run the static extraction and regenerate the C++ provider with:

```sh
python3 tools/reverse-phone/decode_other_game_data.py
python3 tools/reverse-phone/generate_phone_provider.py
```

The generated header is `reconstruction/native-game/generated/production_phone.hpp`. Its values can be checked separately from the core phone behavior tests:

```sh
python3 tools/reverse-phone/decode_other_game_data.py
python3 tools/reverse-phone/generate_phone_provider.py
g++ -std=c++17 -Wall -Wextra -Werror -pedantic \
  -Ireconstruction/native-game/include \
  -Ireconstruction/native-game/generated \
  reconstruction/native-game/src/phone.cpp \
  reconstruction/native-game/tests/phone_production_tests.cpp \
  -o /tmp/ninah-phone-production-tests
/tmp/ninah-phone-production-tests
```
