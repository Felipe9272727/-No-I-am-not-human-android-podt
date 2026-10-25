# Original Unity level 1 world export

Static extraction from Unity `level1` using UnityPy 1.25.4; original EXE/DLL/installer is never executed. Reproduce with `python tools/reverse-world/export_world.py`. The exporter reads source `MeshHandler` vertices, normals, UV0, and triangle indices directly. It deliberately does not use UnityPy OBJ output, which changes X and reverses winding.

`world_manifest.json` carries source file/path IDs, all GameObject transforms, renderers, materials, texture sampler settings, lights, render settings, colliders, cameras, start candidates, player, and six door targets. Mesh binary records are interleaved little-endian float32 position3/normal3/UV0_2 (32 bytes) followed by little-endian uint32 indices. Source LH, Y-up, metre units and winding are retained; world matrices are row-major Unity TRS parent-compositions. A right-handed renderer must reflect positions/normals and triangle winding together.
