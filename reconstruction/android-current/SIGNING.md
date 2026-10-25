# Test signing continuity

The preview uses package `org.reconstruction.port.preview` and a stable local
debug key at `tools/android-current/signing/port-debug.keystore`. Its alias is
`port-preview`; both passwords are `android`. This is a test key, not a
production release credential.

The key is deliberately excluded from the APK and source ZIP. A separate
recovery artifact, `NINAH-Port-Chave-Teste.zip`, preserves it for later preview
updates. Restore the file to the path above before building future versions;
generating a different key would prevent updating the installed application.
