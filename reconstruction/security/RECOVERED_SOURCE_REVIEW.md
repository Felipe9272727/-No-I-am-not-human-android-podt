# Recovered source refresh — static review

Reviewed `source-inputs/No.Im.not.a.Human.v1.3.18.zip` by static inspection. No executable, DLL, installer, script, or game process from the archive was run.

## Integrity reconciliation

- Archive SHA-256: `f8e6a46efbd41452266790a1350bbec3cfd6027470282171b912df80b08489f1` (expected `f8e6a46efbd41452266790a1350bbec3cfd6027470282171b912df80b08489f1`; match: **True**).
- Streamed 93 ZIP files and 15 directories; all file entries were read through end, exercising ZIP CRC checks. All prior per-entry hashes and CRCs match: **True**.
- The review tree contains all 93 source files from the archive; every member is byte-for-byte identical to its ZIP payload.

## PE and Android separation

Fresh ZIP scan found 16 members beginning with `MZ`; inspect `pe_files_in_source_inventory` in the JSON for parsed architecture, entry point RVA, imports, sections, and certificate-table presence. Every PE must be excluded from Android APK/AAB packaging.

`steam_api64.dll` remains a known concern (SHA-256 `f480de9ae15e17fb6e84ad0efa8a386095700cfb7f405bfd64aa61d518587b79`): the prior static report recorded an embedded Authenticode digest mismatch. `steam_api64.rne` is also a Windows PE DLL despite its misleading extension. This refresh inventories certificate-table metadata but does not repeat signature verification. Do not reuse either DLL.

The Android reconstruction should package only reviewed, converted assets/data and native Android outputs built from the reconstruction sources. Exclude Windows EXE/DLL/`.rne`, redist EXE/MSI installers, Steam emulator config, `.url` shortcut, and raw Unity bundles unless separately inspected and strictly required.

## Limits

This is static triage, not proof the archive is benign or malware-free. There was no ready current AV engine/signature database, no execution or detonation, and no third-party upload. PE signature table presence does not imply valid signing or benign behavior. See `STATIC_REVIEW.md`, `file-manifest.csv`, and `zip-entry-manifest.csv` for prior detail; refreshed full per-file evidence is in `RECOVERED_SOURCE_REVIEW.json`.
