# Project instructions

Continue the experimental Android port of No, I'm not a Human v1.3.18.
The user authorized saving progress in this repository and using multiple Luna
agents for this project. Keep ownership of Java, native host, extraction and
build files separate while agents work; do not compile mixed versions of C++
headers and objects.

Never execute or load the original game EXE, DLL, installer or Steam crack.
Static extraction of the supplied Unity files is permitted. New C++/Rust/Java
code and trusted build/extraction tools can run.

Publish source and documentation in frequent commits. Verify each GitHub ref
update and do not end a work session with important source changes only in the
temporary workspace. Do not commit SDKs, caches, signing keys, raw archives or
large extracted game media. Preserve existing remote changes; no force push.

Keep unknown original behavior explicit. Do not replace missing game functions
with fake success or invent campaign progression. Distinguish compiled APKs,
host rule tests, graphics tests and actual Android execution.

The current architecture uses C++ rules/JNI, Rust Yarn VM, Android Java HUD and
libGDX rendering. Application ID is org.reconstruction.port.preview and the JNI
activity remains org.reconstruction.current.MainActivity. Reuse the existing
private test signing key for updates.

Prioritize fidelity to the PC original. Use authored transforms, serialized sibling order, UI layers and recovered state transitions. Avoid substitute layouts and invented campaign behavior. Label debug previews and mobile adaptations explicitly. Validate converters against raw source data, not only their own generated manifests. Keep signing configuration private and out of source/logs.

Current user priority: finish reconstructing the original house before adding campaign continuity. Audit and restore default fixtures, room interactions, window close-ups, original lighting, door/collision behavior and authored animation. Do not represent house completeness or official-port parity as achieved until those gaps are verified.
