# Android scene renderer

`RoomEngine` is the LibGDX `ApplicationAdapter` hosted below the transparent Android HUD. It
accepts assets and native state through `setAssets(JSONObject)` and `setState(JSONObject)`; both
methods copy JSON for a thread-safe handoff, and all scene/GL work stays on LibGDX's render thread.
The activity feeds `setMoveVector(x,forward)`, `addLookDelta(dx,dy)`, and `setInputEnabled(boolean)`.
`getPose()` and `getInteraction()` return copied snapshots for the UI; the GL thread never calls
native gameplay code.

`phase=playing` with `view_mode=world` draws the exported level-1 Unity environment. When
`view_mode=room`, it draws the authored 2D room close-up. A missing `view_mode` defaults to world.
Menu, intro, and other phases clear the 3D/2D scene while Android presents their UI or video.
World geometry, source transforms, materials, colliders, lights, and named door targets come from
`reconstruction/reverse-world/world_manifest.json`. The app uses the source Unity left-handed,
Y-up coordinates and converts to LibGDX's right-handed system by reflecting Z for vertices,
normals, and transforms and reversing triangle winding once. Mesh data is split at triangle
boundaries into chunks that fit LibGDX's 16-bit indices. Material texture UV tiling and offsets
follow the static export, with V inverted once because UnityPy exports Unity's bottom-origin
texture pixels to top-origin PNGs while LibGDX uploads Pixmap rows directly to OpenGL. Texture
wrap/filter mode, tint, transparency, and culling follow the static export. Active source lights
and ambient color are used as a static approximation; dynamic shadowing and runtime light changes
are not recovered.

The serialized active Main Camera transform is the provisional initial view pose; it does not
claim to be the game's final spawn point. Save/load state uses `world_pose:{position:[x,y,z],
yaw:deg,pitch:deg,revision:int}` in source Unity coordinates. A new revision applies the pose;
ordinary campaign ticks preserve the renderer's locally moved pose. Source eye height is 1.65 m,
and pitch clamps to the recovered ±80°. The ECM2 movement speed was not recovered, so 2.5 m/s is a
playable adapter default. Movement uses the exported floor triangles and active solid collider
geometry: oriented box colliders are tested as boxes, and mesh colliders use their actual source
triangles rather than a solid bounding box. The player capsule is approximated by three spheres;
this does not reproduce Unity's full rigidbody simulation.

The source camera ray tests the serialized door `RaycastTarget` boxes to 1 m. Interior door targets
use native `world_navigation.room_doors` collider-to-room mappings. The entrance action uses the
actual Peephole ray collider (path ID 2432), not the separate floor proximity trigger (2412); it
opens the door when the native campaign state says a visitor is waiting and otherwise enters room
5. The returned descriptor includes the source collider ID so the UI can dispatch only supported
actions.

World renderers are frustum culled and limited to 160 m to exclude distant cut-scene set pieces.
Textures load only for visible materials, preferring Android-safe assets downsampled to 1024 px.
A 64 MiB decoded-RGBA LRU pins textures for the active frame and disposes evictions on the GL
thread after the batch completes. The room close-up preserves its 1920×1080 Screen Space Camera
composition, per-room FOV/distance factors, RectTransform size/pivot/order, native pose scale, and
serialized `Image.preserveAspect=true` behavior verified for all seven backgrounds and 61 character
images.

`tools/android-current/libgdx/WorldMathTest.java` checks joystick axes, yaw, and pitch limits
without GL. `WorldGeometryTest.java` parses the staged manifest and mesh colliders on the CPU,
checks all seven source ray colliders and action mappings, then walks from the Main Camera pose
until the entrance collider stops movement. `WorldPreview.java [output.png] [walkSeconds] [forward]`
is the desktop GL screenshot harness when an X11/EGL Mesa display is available.
