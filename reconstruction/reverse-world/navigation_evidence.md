# World navigation evidence

This is a static reconstruction from retained Unity scene data, C# stubs, and ISIL. The original game PE/DLL was not executed. Machine-readable source values and hashes are in [navigation_evidence.json](navigation_evidence.json).

The public camera pose is the Unity eye transform. `PlayerInstance` is at `(-3.985, -0.066, -6.998)` with identity rotation. The `Main Camera` child adds a local eye offset of `(0, 1.65, 0)`, yielding eye position `(-3.985, 1.584, -6.998)` at yaw/pitch 0. Source camera FOV is 60 degrees, with 0.1/1000 near/far planes. PlayerController's constructor defaults pitch to −80..+80 degrees and mouse sensitivity to `(1.5, 1.25)`. Movement transforms the input vector by the player transform, normalizes only above unit length, then forwards it to ECM2 Character. Serialized speed and gravity were not recovered.

PlayerInputActions binds Move to WASD/left stick, Look to mouse delta (scaled 0.1)/right stick, Interact to left mouse/E/Space/gamepad south, Run to Shift/right trigger, Crouch to left Ctrl/right-stick press, and Pause to Escape/gamepad start. RaycastSource projects from the camera through the Default layer mask and toggles the hit ARaycastTarget. Its constructor initializes max ray distance to 1.0; the serialized override is unknown.

The room IDs are Kitchen=0, Office=1, BigRoom=2, Bathroom=3, Pantry=4, Entrance=5, Bedroom=6. Room navigation uses each named door's child RaycastTarget collider center. The visible door pivots can be far from those actionable colliders:

| Door | Room | Collider | World center (metres) |
| --- | ---: | ---: | --- |
| Door1 Kitchen | 0 | 2425 | (-2.109, 1.391, -11.845) |
| Door2 Office | 1 | 2449 | (-0.269, 1.329, -11.820) |
| Door3 BigRoom | 2 | 2452 | (0.985, 1.329, -8.829) |
| Door4 Bathroom | 3 | 2453 | (-2.987, 1.272, -7.755) |
| Door5 Pantry | 4 | 2460 | (-5.079, 1.286, -9.425) |
| Door6 Bedroom | 6 | 2439 | (3.142, 1.318, -10.525) |

The outside visitor action targets PeepholeTrigger (MonoBehaviour 3929) on GO81. Its actual raycast target is BoxCollider 2432 on GO142 `RaycastTrigger`, a non-trigger collider on the Default layer at `(-4.121358, 1.466308, -4.229544)`. GO81 collider 2412 at `(-4.117006, 0.098784, -4.535772)` is a separate proximity trigger. Raw serialized MonoBehaviour fields identify `_linkedRoom=5` (Entrance), peephole camera GO43, volume component 4032, and distortion scale 0.5. Its authored actions animate the peephole camera and lens distortion. The camera transform itself is not the interaction point.

DoorTrigger resolves its linked room through IRoomsManager and runs authored door entry/exit actions; RoomsManager handles the room transition. For the known first visitor flow, the renderer maps an interaction with the peephole target to `open_door`, which enters Entrance close-up and starts `entrance_neighbour_0`. Active Yarn dialogue blocks `enter_room` and `enter_world` so the dialogue stays visible. After admission, `enter_room(0)` enables the mapped Kitchen close-up and Neighbour conversation. The first known in-house dialogue ends at a boundary; no day advance is fabricated.

Fresh-start StartPoint selection is unresolved. The initial pose uses the authored Main Camera scene transform. Exact ECM2 speed/gravity, serialized ray-distance override, and joystick viewport geometry remain unresolved; the presentation layer owns mobile controls.
