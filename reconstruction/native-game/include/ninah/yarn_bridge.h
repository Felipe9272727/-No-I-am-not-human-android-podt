#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct NinahYarnHandle NinahYarnHandle;
typedef struct NinahYarnArg { int32_t tag; double number; const char* text; } NinahYarnArg;
// Args are borrowed for this call. Return borrowed JSON primitive, copied
// immediately. nullptr reports unavailable service. No concurrent or reentrant handle calls.
typedef const char* (*NinahGameFunction)(void*,const char*,const NinahYarnArg*,size_t);
NinahYarnHandle* ninah_yarn_create(const char*,void*,NinahGameFunction,char**);
// Atomically attaches the recovered line_metadata.json export. 1=success;
// 0=error (JSON string in error output). Missing metadata is explicitly null
// in line/option events, never an inferred empty tag set. Same call-lifetime rules.
int32_t ninah_yarn_load_line_metadata(NinahYarnHandle*,const char*,char**);
char* ninah_yarn_start(NinahYarnHandle*,const char*);
char* ninah_yarn_advance(NinahYarnHandle*);
char* ninah_yarn_choose(NinahYarnHandle*,size_t);
// JSON snapshot of VM state, allocated with the bridge string allocator. Restore
// validates program identity and state atomically; 1=success, 0=error JSON.
char* ninah_yarn_dump_snapshot(NinahYarnHandle*,char**);
int32_t ninah_yarn_restore_snapshot(NinahYarnHandle*,const char*,char**);
void ninah_yarn_free_string(char*);
void ninah_yarn_destroy(NinahYarnHandle*);
#ifdef __cplusplus
}
#endif
