# Android campaign slot

Version 0.11 writes an explicit **Salvar jogo** checkpoint to the application's
private `files/saves` directory. Reopening starts at the menu; **Continuar** loads
the accepted slot. Starting a new game preserves the previous slot until the
user saves again. There is no automatic save on process death or uninstall.

The C++ host owns a versioned `NINAH-SAVE` object. It includes progression,
inventory and usage history, occupants and mutable character flags, ordered
phone numbers, PRNG state, camera pose, presentation state and deferred poses,
the active Rust Yarn VM snapshot and the last completed dialogue snapshot.
Content identity is a hexadecimal string, avoiding Android JSON's loss of
precision for unsigned 64-bit numbers. JNI JSON input uses ASCII Unicode escapes
so surrogate pairs survive modified UTF-8 transport.

`export_save` returns the normal state plus `save`. `import_save` accepts that
object, or its serialized JSON string. It validates a temporary snapshot and VM
before replacing the saved slot; it does not load or advance the current game.
Rejected imports preserve the current game and the existing slot. Continue/Load
restores the saved cursor without replaying side effects.

Java `SaveFileStore` wraps the native payload with a format/version and SHA-256
checksum. Writes flush and sync a temporary file before renaming. The previous
committed file is retained as a backup. Startup tries the main file, then the
backup, requiring both transport integrity and native schema validation. An
orphan temporary file is ignored. The UI reports a recovered backup or an
unreadable slot; failed writes do not report success. A backup accepted after
native validation is protected from replacement by a rejected primary file.

The checksum detects incomplete or accidentally changed data; it is not an
authentication mechanism. The two files are bounded to 4 MiB each, with a 2 MiB
native payload limit. Saving runs on the same single worker as native actions,
not on the render/UI thread. The existing source scene and media are not copied
into the checkpoint. Debug graphics preferences, including the cat preview,
remain separate from campaign state.

Host tests cover fresh Context restoration, active dialogue and inventory,
pending sleep transitions, nonempty fines, and rejected versions, malformed
values, references and VM snapshots. Java filesystem tests cover UTF-8,
checksums, backup selection and interrupted rename scenarios. Actual Android
process restart and storage failure behavior still require a device test.
