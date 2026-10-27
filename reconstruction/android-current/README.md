# Current Android preview

`0.13-house-fidelity` restores the original house before adding more campaign content.
The current artifact is `deliverables/NINAH-Port-Casa-v013.apk`; see the root
README, PROGRESS.md, RECOVERY.md and LATEST_BUILD.json for exact build identity.

C++/JNI contains recovered game rules, Rust runs the Yarn VM, Java/Android draws
the HUD and libGDX renders the scene. Source Unity data supplies the house meshes,
room layers, character poses, music and UI art. Original Windows code is neither
loaded nor executed. The package is `org.reconstruction.port.preview`, JNI
activity `org.reconstruction.current.MainActivity`, API 23+/target35, arm64-v8a
and x86_64. Restore the same private signing key to install updates.

The current route reaches the first morning. Manual save and Continue persist
on the device since v0.11. v0.13 fixes the default Kitchen fridge, Bedroom TV
fixture, source parent offsets, TV dialogue panel placement and draw order, and
adds the active basement miner's serialized skinned pose. Direct taps work on
the bed and available morning TV; pause/save are accessible in rooms.

The house is unfinished: window close-ups, furniture narrative interactions,
dynamic object states, original lighting/material effects, full Animator
playback and front-door swing remain incomplete. Cat preview remains debug-only
and static; it does not unlock story events. Native campaign rules were not
changed for v0.13. This is an experimental reconstruction, not an official port.

Build using `python3 tools/android-current/build_apk.py`; current-version
reference-APK instructions and source-data requirements are in RECOVERY.md.
The APK report verifies signing, ZIP CRC, 16 KiB native alignment, original
media hashes and both ABI libraries. Host GLES2 tests and source-data audits
are separate from Android execution; the current release has not been run on
a physical phone or emulator here.
