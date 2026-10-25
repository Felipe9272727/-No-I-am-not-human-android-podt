# Android opening preview

This project combines the reconstructed C++ game state, Rust Yarn interpreter,
Java Android host and libGDX room renderer. Python scripts extract data and
build the application. It is a bounded reconstruction, not the complete port.

The intended preview sequence is the recovered main menu, original 72-second
intro movie with its audio and Portuguese subtitle IDs, the house, and the
original first Neighbour entrance conversation. Admission updates the occupant
state. The first in-house `talk_neighbour_1` route is also recovered. Later
visitors, day transitions and the complete campaign remain unfinished.

The host initializes the 15 ordered phone numbers using the recovered number
service and fixed-number provider with explicit host RNG callbacks. It exposes
the Neighbour number and unlocked subscriber state for the dialogue, and saves
these alongside RNG and game state. Phone close-up and pin UI are unfinished.
The bounded opening uses separate dialogue sessions; preserving all global Yarn
variables and talk counters across the later campaign still needs integration.

The original room scene uses layered UI images and perspective cameras. The
mobile renderer uses the recovered 1920×1080 RectTransform coordinates, room
backgrounds and character poses. Screen Space Camera canvas scaling must cancel
camera plane distance; plane distance alone must not shrink the entire room.
The Android host draws touch controls and dialogue over the GL scene. This
adaptation does not recreate every original UI effect, animation or interaction.

The preview package is `org.reconstruction.port.preview`, separate from the
previous `org.reconstruction.current` test application. The Java/JNI class is
still `org.reconstruction.current.MainActivity`. The build targets API 23+
for arm64-v8a and x86_64 with SDK 35, NDK r27c and Java 17.

Build from the source root:

```sh
python3 tools/android-current/build_apk.py
```

The intended output is `deliverables/NINAH-Port-3D-Correcao.apk`. The build report
records the actual output, signatures, native libraries, assets and validation
limits. No original EXE, DLL or installer is executed or included. The preserved
source reports are static reverse engineering evidence, not a certification
that the downloaded Windows distribution is malware-free.

Save/Continue currently snapshots only the running process. Closing the app
loses that save. Debug test signing is distinct from a production release key.
Device execution must not be claimed unless a real Android test is recorded.

Generated staging assets under `app/src/main/assets` duplicate the recovered
source data and are excluded from source checkpoints. The large intro MP4 is
also excluded from that ZIP; it is reproducibly extracted from the original
archive preserved in three parts. See `reverse-bootstrap/intro_evidence.json`,
the extraction script, and `security/ORIGINAL_ARCHIVE_RECOVERY.json`.

The v0.3 test build has a visible `DEBUG: pular intro` button. This explicit
mobile debug adaptation releases the movie and follows the existing serialized
`intro_tick(72000)` then `intro_video_finished` transition. It does not add a
fake campaign phase or alter the native rules. The normal movie completion
path remains available. Diagnostics stay private until the user copies or
shares them from Options. A native Android exit/tombstone summary is available
on supported system versions; the previous device crash is still unconfirmed.
