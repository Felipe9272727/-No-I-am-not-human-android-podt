# 3D cat preview evidence

The recovered level-1 scene contains the actual cat model on `SkinnedMeshRenderer` path 2557, GameObject 439 (`Body`). Its parent is GameObject 477 (`Naperdysh_idle`), whose serialized `active_self` value is false. `CatInstance` path 5254 and `CatInteractable` path 4881 are attached to that object. The skinned renderer points to `sharedassets1.assets` mesh 304 (`Body`, 1,112 vertices, 1,519 triangles, 48 bones), material 30 (`Cat_alpha_mat`), and albedo texture 92 (`koshka`). The material uses URP/Lit, `_BaseColor=(0.821,0.821,0.821,1)`, alpha clipping at 0.264, back-face culling and Z write. The texture's streamed bytes are in `sharedassets1.assets.resS`.

The checkpoint's recovered `CatController` IL shows that `ActivateCat()` sets `CatSaveData.IsActive=true`, enables the cat GameObject, and then calls `ChangePosition(1)`. The fresh `CatSaveData` constructor zero-initializes its fields, so the original scene does not activate the cat by default. `ActivateCatOnLoad` waits for the data model to load before restoring the saved cat state. Yarn `GetCat` is present only in the later `Ballerina_Entrance_YesLet_1`, `_2`, and `_Occupied` branches. The port therefore exposes this asset only through an explicit debug preview flag; this does not change campaign state or save data.

`CatViewProvider` is serialized on GameObject 15 (`ViewProviders`). Its MonoBehaviour raw data encodes the `CatInstance` reference at byte 32, then three 20-byte DayPosition rows beginning at byte 48 and three NightPosition rows beginning at byte 112. Each row is `(Vector3 position, float yaw, int animation)`. `ETimeOfDay` is Day=0/Night=1; `ECatAnimation` is Sit=0, Lay=1, Stand=2, Walk=3, Play=4. The first Day position is `(-5.27, 0.32, -4.76)` at yaw `-255.84°` with Sit; the first Night position is `(-5.21, 0.32, -4.86)` at yaw `-70.2°` with Lay. The debug preview uses the fixed DayPosition[0] source position regardless of the opening campaign time; it does not claim to follow the Day/Night controller.

The exporter evaluates the actual source bone transforms with the mesh bind poses and decoded per-vertex bone indices/weights, then converts the result into the cat root's local frame. It preserves source UVs, normals, triangle indices, the source base color, and alpha cutout texture. This produces a static source skeleton/rest pose. It does not evaluate the authored Sit or Lay animation clips; the manifest records that limitation rather than claiming a live animation.

Recreate the small runtime assets from the restored static Unity files with:

```sh
PYTHONPATH=tools/python-deps python tools/reverse-world/export_cat3d.py \
  --data /workspace/scratch/ad0b61c5ef81/restore-v11/unity-data \
  --original-archive /workspace/scratch/ad0b61c5ef81/restore-v11/original.zip \
  --out reconstruction/reverse-world/cat3d
```

The archive is read only for the `.resS` texture sidecar. The game's EXE and DLL are not run or loaded. `tools/android-current/prepare_assets.py` stages the separate cat manifest, mesh and texture beside the static world assets without changing the 100-mesh static-world manifest. `RoomEngine.setCatPreviewEnabled(boolean)` controls visibility for the `DEBUG: gato 3D` option; it remains false by default and carries across GL renderer creation.
