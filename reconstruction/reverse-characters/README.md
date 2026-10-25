# Recovered character production data

`character_configs.json` is the normalized full `CharacterSOData` parse for all 73 production records. It includes character type and pose transforms, emotion reference IDs and overrides, room and localization references, human/imposter sprites and eye/animation assets, sound references, impostor/exile/preset/status fields, placement and visit schedules, allowed days, minimum games, quote localization, gacha biases, FEMA rating bonus, extra transforms, and dialog transforms.

Each raw field boundary uses the local Cpp2IL layout declarations. The ordinary-field cursor must match the serialized managed-reference registry offset exactly. Every registry has version 2; all 275 managed-reference IDs map to declared concrete payload classes and declared `EDialogEmotionState` values, match the host `_emotions` vectors, and finish at the exact raw object end. The parser has zero errors across 73 rows. It also checks known Alkonost values and byte offsets (`isImposter` 636, place 656 / `LivingRoomSofaRight`, allowed days 1–6, registry start 880).

`emotion_registry.json` presents all 275 emotion-to-sprite/animation records in source array order. The source Unity data files have been statically read and the referenced media exported. `exported_character_assets/manifest.json` records all 1,256 unique PPtrs found recursively in the 73 character configs and 275 emotion records: 1,151 sprites, 49 textures, and 56 AudioClips, with no unresolved refs. This includes the white and iris eye sprite refs. `exported_audio/manifest.json` records all 56 referenced clips, the exact original FSB5 resource bytes with SHA-256, and decoded WAV files independently checked against Unity duration, channel count, and sample rate. The image manifest includes dimensions and output sizes for every PNG.

The exporter loads only the two asset files that own referenced objects, one at a time. The audio decoder uses the same sequential load policy. The PNGs are UnityPy-decoded sprite/texture pixels, not a mesh re-render. No original executable or DLL is run.

Run the raw data parsers:

```sh
python tools/reverse-characters/decode_character_config.py
python tools/reverse-characters/decode_emotion_registry.py
```

To regenerate exports when the original `NoImNotAHuman_Data` files are present, run `export_character_assets.py` followed by `decode_character_audio.py`.
