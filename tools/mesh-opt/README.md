# Offline mesh reindexing

`optimize_world.py` stages exact, lossless vertex deduplication and vertex-fetch reindexing for the Android world meshes. It preserves the original `models/` blobs and writes optimized copies under `world/models_android/`; it writes a separate `world_manifest.optimized.json` candidate and never replaces the active manifest.

The native helper uses only `meshopt_generateVertexRemap`, `meshopt_remapIndexBuffer`, `meshopt_remapVertexBuffer`, and `meshopt_optimizeVertexFetchRemap` from meshoptimizer v1.3, pinned to official commit `9e1f07b159d3cb777f1c67ed31fc11fd117986f4`. The official source archive SHA-256 is `ca4f47d451201593904b9e3067fa54b65db94bc34ab5173864950862b748a145`. The small subset of upstream source and its MIT license are included under `third_party/meshoptimizer-v1.3/`.

The input layout is 32-byte interleaved vertex records followed by little-endian uint32 indices. Remapping compares the complete 32-byte record. Vertex-fetch remapping walks the existing index stream, so it does not reorder triangles or submeshes. The tool does not simplify, strip, quantize, split, or generate LODs. Every indexed vertex record is compared byte-for-byte against the corresponding source corner before output is accepted.

From the repository root, run:

```sh
python3 tools/mesh-opt/optimize_world.py
```

The script verifies each source SHA-256 from `world_manifest.json` before optimization. It stages into `reconstruction/android-current/app/src/main/assets/world/models_android/`, writes `tools/mesh-opt/world_manifest.optimized.json`, and records counts and byte savings in `tools/mesh-opt/optimization_report.json`. `--assets-root` selects another Android assets tree, such as a staging directory from `prepare_assets.py`; `--apply` atomically replaces that tree's active world manifest only after all meshes pass validation. The default writes a candidate manifest and leaves the active manifest intact.
