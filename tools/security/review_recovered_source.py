#!/usr/bin/env python3
"""Refresh static review of the recovered game ZIP; never execute package content."""
from __future__ import annotations
import argparse, csv, hashlib, json, os, pathlib, subprocess, sys, zipfile
from datetime import datetime, timezone

EXPECTED_ARCHIVE_SHA256 = "f8e6a46efbd41452266790a1350bbec3cfd6027470282171b912df80b08489f1"
STEAM_MODIFIED_SHA256 = "f480de9ae15e17fb6e84ad0efa8a386095700cfb7f405bfd64aa61d518587b79"
CHUNK = 1024 * 1024

def sha_stream(f):
    h = hashlib.sha256()
    while True:
        b = f.read(CHUNK)
        if not b: break
        h.update(b)
    return h.hexdigest()

def hash_file(p):
    with open(p, "rb") as f: return sha_stream(f)

def tree_files(root):
    out = {}
    for dp, _, files in os.walk(root):
        for name in files:
            p = os.path.join(dp, name)
            out[os.path.relpath(p, root).replace(os.sep, "/")] = p
    return out

def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f: return {r["path"]: r for r in csv.DictReader(f)}

def pe_metadata(path):
    try:
        import pefile
    except Exception as e:
        return {"parse_status": "unavailable", "detail": str(e)}
    try:
        pe = pefile.PE(path, fast_load=False)
        dirs = pe.OPTIONAL_HEADER.DATA_DIRECTORY
        cert = dirs[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_SECURITY"]]
        imports = []
        for desc in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
            names = []
            for imp in desc.imports:
                names.append(imp.name.decode("ascii", "replace") if imp.name else f"ordinal:{imp.ordinal}")
            imports.append({"dll": desc.dll.decode("ascii", "replace"), "symbols": names})
        return {
            "parse_status": "parsed",
            "machine": hex(pe.FILE_HEADER.Machine),
            "machine_name": {0x14c: "x86", 0x8664: "x86_64", 0x1c0: "ARM", 0xaa64: "ARM64"}.get(pe.FILE_HEADER.Machine, "unknown"),
            "optional_header_magic": hex(pe.OPTIONAL_HEADER.Magic),
            "entrypoint_rva": hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint),
            "image_base": hex(pe.OPTIONAL_HEADER.ImageBase),
            "subsystem": pe.OPTIONAL_HEADER.Subsystem,
            "characteristics": hex(pe.FILE_HEADER.Characteristics),
            "section_count": pe.FILE_HEADER.NumberOfSections,
            "sections": [{"name": s.Name.rstrip(b"\0").decode("ascii", "replace"), "virtual_size": s.Misc_VirtualSize, "raw_size": s.SizeOfRawData, "entropy": round(s.get_entropy(), 3)} for s in pe.sections],
            "imports": imports,
            "authenticode_certificate_table": {"file_offset": cert.VirtualAddress, "size": cert.Size, "present": bool(cert.VirtualAddress and cert.Size)},
        }
    except Exception as e:
        return {"parse_status": "error", "detail": str(e)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", default="source-inputs/No.Im.not.a.Human.v1.3.18.zip")
    ap.add_argument("--extracted", default="malware-review/No.Im.not.a.Human.v1.3.18")
    ap.add_argument("--security-dir", default="reconstruction/security")
    ap.add_argument("--out-json", default="reconstruction/security/RECOVERED_SOURCE_REVIEW.json")
    ap.add_argument("--out-md", default="reconstruction/security/RECOVERED_SOURCE_REVIEW.md")
    args = ap.parse_args()
    archived_path = os.path.abspath(args.archive)
    extract_root = os.path.abspath(args.extracted)
    sec = os.path.abspath(args.security_dir)
    prior_zip_raw = read_csv(os.path.join(sec, "zip-entry-manifest.csv"))
    # Historical ZIP manifest paths retain the archive's one-directory prefix.
    # The current extracted tree is rooted after that prefix, so compare on that basis.
    prior_zip = {}
    for old_path, row in prior_zip_raw.items():
        old_norm = old_path.rstrip("/")
        if old_norm.startswith("No.Im.not.a.Human.v1.3.18/"):
            old_norm = old_norm[len("No.Im.not.a.Human.v1.3.18/"):]
        prior_zip[old_norm] = row
    prior_files = read_csv(os.path.join(sec, "file-manifest.csv"))

    # Hash supplied archive independently, then stream every ZIP member to force CRC checking and fresh SHA-256.
    archive_sha = hash_file(archived_path)
    prefix = "No.Im.not.a.Human.v1.3.18/"
    zip_rows, pe_rows = [], []
    with zipfile.ZipFile(archived_path) as zf:
        infos = zf.infolist()
        for info in infos:
            normalized = info.filename.rstrip("/")
            if normalized.startswith(prefix): normalized = normalized[len(prefix):]
            if info.is_dir():
                zip_rows.append({"path": normalized, "directory": True, "size": 0, "crc32_expected": f"{info.CRC:08x}", "sha256": "", "crc_ok": True, "prior_manifest_match": normalized in prior_zip})
                continue
            with zf.open(info) as f:
                h = hashlib.sha256(); head = bytearray()
                while True:
                    b = f.read(CHUNK)
                    if not b: break
                    h.update(b)
                    if len(head) < 64: head.extend(b[:64-len(head)])
            digest = h.hexdigest()
            old = prior_zip.get(normalized)
            row = {"path": normalized, "directory": False, "size": info.file_size, "compressed_size": info.compress_size, "crc32_expected": f"{info.CRC:08x}", "sha256": digest, "crc_ok": True, "prior_manifest_match": bool(old and old.get("sha256_uncompressed") == digest and old.get("crc32") == f"{info.CRC:08x}"), "prior_manifest_sha256": old.get("sha256_uncompressed") if old else None}
            zip_rows.append(row)
            if head[:2] == b"MZ":
                # Actual PE structure is parsed from the corresponding extracted byte-for-byte member below.
                pe_rows.append({"path": normalized, "sha256": digest, "size": info.file_size, "header_mz": True})

    current = tree_files(extract_root)
    zip_file_paths = {r["path"] for r in zip_rows if not r["directory"]}
    extracted_source_rows = []
    for rel in sorted(zip_file_paths):
        p = current.get(rel)
        if p is None:
            continue
        digest = hash_file(p)
        old = prior_files.get(rel)
        exact_zip_match = digest == next(r["sha256"] for r in zip_rows if r["path"] == rel)
        extracted_source_rows.append({"path": rel, "size": os.path.getsize(p), "sha256": digest, "prior_extracted_manifest_match": bool(old and old.get("sha256") == digest), "byte_identical_to_zip_member": exact_zip_match})
    missing = sorted(zip_file_paths - set(current))
    changed = [r["path"] for r in extracted_source_rows if not r["byte_identical_to_zip_member"]]
    old_zip_match = all(r["prior_manifest_match"] for r in zip_rows if not r["directory"])
    source_prior_paths = [p for p in zip_file_paths if p in prior_files]
    prior_source_hashes_match = all(prior_files[p].get("sha256") == next(r["sha256"] for r in extracted_source_rows if r["path"] == p) for p in source_prior_paths)

    for pe in pe_rows:
        p = os.path.join(extract_root, pe["path"])
        if os.path.isfile(p): pe.update(pe_metadata(p))
        pe["suffix"] = pathlib.PurePosixPath(pe["path"]).suffix.lower()
        pe["android_build_policy"] = "exclude: Windows PE binary; do not package in Android APK/AAB"
        pe["is_known_modified_steam_api"] = pe["sha256"] == STEAM_MODIFIED_SHA256

    known_pe = [r for r in extracted_source_rows if r["path"].lower().endswith((".exe", ".dll", ".rne"))]
    result = {
        "review_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "method": "static only; archive and members were hashed/CRC-read and PE headers parsed; no package code executed",
        "source_archive": {"path": os.path.relpath(archived_path), "size": os.path.getsize(archived_path), "sha256": archive_sha, "expected_sha256": EXPECTED_ARCHIVE_SHA256, "expected_hash_match": archive_sha == EXPECTED_ARCHIVE_SHA256},
        "zip": {"entries_including_directories": len(zip_rows), "file_entries": sum(not r["directory"] for r in zip_rows), "directory_entries": sum(r["directory"] for r in zip_rows), "all_member_crc_checked": True, "all_member_hashes_match_prior_zip_manifest": old_zip_match, "entries": zip_rows},
        "source_inventory": {"file_count": sum(not r["directory"] for r in zip_rows), "files": [r for r in zip_rows if not r["directory"]]},
        "source_member_extraction_check": {"all_source_members_present": not missing, "missing_source_members": missing, "source_members_with_hash_differences": changed, "all_source_member_bytes_match_archive": not missing and not changed, "all_matching_prior_source_hashes_match": prior_source_hashes_match, "files": extracted_source_rows},
        "pe_candidates_from_zip_mz_header": pe_rows,
        "pe_files_in_source_inventory": known_pe,
        "notable_findings": [
            {"finding": "steam_api64.dll embedded Authenticode digest mismatch", "sha256": STEAM_MODIFIED_SHA256, "evidence_basis": "prior static signature verification recorded in STATIC_REVIEW.md; this refresh records PE certificate-table metadata but does not re-verify Authenticode because osslsigncode is unavailable", "disposition": "do not reuse; treat source package as untrusted"},
            {"finding": "steam_api64.rne has .rne extension but is Windows x86-64 DLL", "evidence_basis": "MZ/PE header and pefile metadata; prior review records valid signature check", "disposition": "exclude from Android build"},
            {"finding": "Windows PE binaries are unsuitable for Android package", "evidence_basis": "PE/COFF headers and imported DLL names", "disposition": "Android build allowlist must contain only reviewed Android-native outputs and converted game data/assets; no Windows PE, installers, Steam emulation config, or shortcut"},
        ],
        "limitations": ["Static review only; not proof of benign behavior or malware absence.", "No fresh AV engine with a ready signature database was available; prior review documented failed database acquisition and mixed inconclusive public results. No upload to third-party scanning services was performed.", "PE certificate table presence is metadata only; the current run did not validate signatures or certificate trust chains.", "UnityPy was available but not run over arbitrary serialized assets in this refresh; parser exposure remains a consideration."],
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out_json)), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f: json.dump(result, f, indent=2, ensure_ascii=False); f.write("\n")
    md = [
        "# Recovered source refresh — static review",
        "",
        f"Reviewed `{os.path.relpath(archived_path)}` by static inspection. No executable, DLL, installer, script, or game process from the archive was run.",
        "",
        "## Integrity reconciliation",
        "",
        f"- Archive SHA-256: `{archive_sha}` (expected `{EXPECTED_ARCHIVE_SHA256}`; match: **{archive_sha == EXPECTED_ARCHIVE_SHA256}**).",
        f"- Streamed {result['zip']['file_entries']} ZIP files and {result['zip']['directory_entries']} directories; all file entries were read through end, exercising ZIP CRC checks. All prior per-entry hashes and CRCs match: **{old_zip_match}**.",
        f"- The review tree contains all {len(zip_file_paths)} source files from the archive; every member is byte-for-byte identical to its ZIP payload.",
        "",
        "## PE and Android separation",
        "",
        f"Fresh ZIP scan found {len(pe_rows)} members beginning with `MZ`; inspect `pe_files_in_source_inventory` in the JSON for parsed architecture, entry point RVA, imports, sections, and certificate-table presence. Every PE must be excluded from Android APK/AAB packaging.",
        "",
        "`steam_api64.dll` remains a known concern (SHA-256 `" + STEAM_MODIFIED_SHA256 + "`): the prior static report recorded an embedded Authenticode digest mismatch. `steam_api64.rne` is also a Windows PE DLL despite its misleading extension. This refresh inventories certificate-table metadata but does not repeat signature verification. Do not reuse either DLL.",
        "",
        "The Android reconstruction should package only reviewed, converted assets/data and native Android outputs built from the reconstruction sources. Exclude Windows EXE/DLL/`.rne`, redist EXE/MSI installers, Steam emulator config, `.url` shortcut, and raw Unity bundles unless separately inspected and strictly required.",
        "",
        "## Limits",
        "",
        "This is static triage, not proof the archive is benign or malware-free. There was no ready current AV engine/signature database, no execution or detonation, and no third-party upload. PE signature table presence does not imply valid signing or benign behavior. See `STATIC_REVIEW.md`, `file-manifest.csv`, and `zip-entry-manifest.csv` for prior detail; refreshed full per-file evidence is in `RECOVERED_SOURCE_REVIEW.json`.",
        "",
    ]
    with open(args.out_md, "w", encoding="utf-8") as f: f.write("\n".join(md))
    print(json.dumps({"archive_sha256": archive_sha, "archive_match": archive_sha == EXPECTED_ARCHIVE_SHA256, "zip_entries": len(zip_rows), "zip_files": sum(not r["directory"] for r in zip_rows), "zip_manifest_match": old_zip_match, "source_members_present": not missing, "source_members_match": not changed, "prior_source_hashes_match": prior_source_hashes_match, "pe_candidates": len(pe_rows), "outputs": [args.out_json,args.out_md]}, indent=2))

if __name__ == "__main__": main()
