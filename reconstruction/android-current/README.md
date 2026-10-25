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

The intended output is `deliverables/NINAH-Port-Desempenho.apk`. The build report
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

The v0.4 test build has a visible `DEBUG: pular intro` button. This explicit
mobile debug adaptation releases the movie and follows the existing serialized
`intro_tick(72000)` then `intro_video_finished` transition. It does not add a
fake campaign phase or alter the native rules. The normal movie completion
path remains available. Diagnostics stay private until the user copies or
shares them from Options. A native Android exit/tombstone summary is available
on supported system versions; the missing-shader cause is now confirmed. The user confirmed v0.4 opens the house on the Xiaomi, while reporting missing/white/flickering surfaces. v0.5 device playback and rendering are not yet verified.

The manual packager preserves the GDX Java resources at APK root, where
Classpath FileHandle expects them. D8 alone does not carry GLSL resources from
its input jars into classes.dex. `qa/check_apk_shaders.py` reproduces the v0.3
missing-file failure and verifies v0.4 with a classes-only GDX jar, checking
that the shader URL resolves inside the delivered APK.

## v0.5 rendering and music

The original menu AudioSource selects main_menu; the recovered level-1 night and
ambient AudioSources select night1 and ambience_house. The host uses two independent
lifecycle-gated MediaPlayers for the bounded opening. The intro keeps its embedded
soundtrack and does not overlap these OGG tracks. Options includes a persistent
music mute setting. All OGG assets must be ZIP_STORED for AssetManager.openFd;
the manual packager enforces this and validates hashes in the delivered APK.
Fourteen original music AudioClips are bundled, but later-day routing and campaign
progression are not enabled by their presence. See reverse-music for extraction.

Two damaged PNGs in the recovered v0.4 APK are restored from the hash-locked
3D/UI source bundle. Validation now verifies PNG CRCs and fully decodes every
PNG, checks each world texture hash, and rejects staging temporary files.
Renderer changes honor source blend/depth settings, reverse culling for mirrored
instances and request 24-bit depth with source camera clipping planes. Stock
libGDX lighting/shaders still approximate the source; uncovered areas, bright
source Window materials and incomplete effects remain under investigation.

Historical Android exits are labeled separately from the current renderer status.
Only a previously unseen exit from the currently installed version triggers an
automatic notice; older records remain available through manual diagnostics.

## v0.6 performance preview

The renderer fixes full-size/half-extents frustum rejection and Unity/GL cull enum
translation, reuses per-item material/renderable objects and retains indexed GPU
vertices from the offline C++ mesh optimizer. Shader and triangle counts remain
source-based. Source geometry and all indexed corner attributes remain lossless.
The GPU surface has balanced/light/native resolution options; native Canvas UI
and touch mapping keep the same layout. FPS and graphics diagnostics are private
until the user copies/shares them. Surface resizing and performance changes have
not been executed on Android here. The user's v0.5 report is approximately10 FPS.

Assembly is not a substitute for measuring the relevant CPU/GPU workload. The
Android NDK supports NEON by default on arm64, and no measured native CPU hotspot
has yet justified hand-written assembly. Research and validation links are in
release_v06_summary.json.
