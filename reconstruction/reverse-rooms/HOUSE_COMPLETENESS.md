# House composition audit (v1.3.18 source)

This audit prioritizes the seven 2D house rooms before campaign/story progression. It compares the tracked Unity scene extraction with the current staged room-layer audit and recovered room-object initialization. It covers the 2D `level1` room views only; it makes no claims about 3D locations or later campaign states.

## Coverage

The tracked [room manifest](room_manifest.json) accounts for all seven room views, 104 descendant GameObjects, 95 room Image components, 35 resolved Sprite references (33 unique sprites), 61 ordered `CharacterRoomObjectView` references, 10 `ObjectRoomObjectView` references, 79 room-array buttons, and nine narrative hotspots. The staged room-layer audit now reports 19 always-visible layers, one separately gated bed layer, and 75 exclusions. The 19 always-visible layers contain every room's authored background and Kitchen's default Fridge state; the Bedroom TV is a separate room actor.

| Room | Source Images | Static layers now | Source-active/stateful objects requiring runtime initialization | Authored conditional or inactive props |
|---|---:|---|---|---|
| Kitchen | 17 | BG, Fridge, Cupboards | Fridge is activeSelf, starts at `Fridge` state (enum 2), and is staged as an always-visible layer from sprite `Kitchen_obj1`. `fridge_active` controls its button interaction, not the closed-fridge sprite. | Beer1 and Beer2 have null state-0 slots and sprite-bearing state-1 slots in the StateObjectsViewProvider. Do not show either without state 1. Twelve character views remain distinct actors. |
| Office | 24 | RoomTest background, Pictures, Magazine | None among the ObjectRoomObjectViews is activeSelf. | Baby and CultistsSheets GameObjects are inactiveSelf with `None` (-1) as their sole serialized start state. Nineteen character views remain distinct actors. |
| BigRoom | 19 | RoomTest background, Cross, Toy | None among the ObjectRoomObjectViews is activeSelf. | Apple is inactiveSelf with `None` (-1) start state. Fifteen character views remain distinct actors. |
| Bathroom | 12 | RoomTest background, Sink, Window | None among the ObjectRoomObjectViews is activeSelf. | Baby and Husband are inactiveSelf with `None` (-1) start states. Seven character views remain distinct actors. |
| Pantry | 8 | RoomTest background, Box | No ObjectRoomObjectView is serialized for this room. | Six character views remain distinct actors. |
| Entrance | 3 | Sky, Background | No ObjectRoomObjectView or character view is serialized for this room. | `Black` has an Image with an unresolved/null source Sprite and is not promoted to a layer. |
| Bedroom | 12 | BG, Nightstand, Window | **Bed** is activeSelf and starts at `Bed` state (enum 0), sprite `Livingroom2_obj1`; the current runtime layer is separately gated by the audited `bed_visible` condition. | TV is an activeSelf room character (see below). TVMask and Screen are inactiveSelf. Curtain, Clock, Mushroomlist and Sexy are inactiveSelf; their object/character state must come from runtime state. |

The Kitchen Fridge is the key default house object recovered in this pass: source component 4813 on active GameObject 999 selects state 2 (`Fridge`), and its sole state record points to Sprite `sharedassets1.assets:612` (`Kitchen_obj1`) with position `(690, -65)` and scale `(2, 2)`. The exporter now retains this full table and `stage_room_layers.py` stages its transformed image as an always-visible layer. The recovered `KitchenView.SetFridgeActivity` calls only `UIButton.set_IsActive` on `_fridgeButton`; it does not hide the closed-fridge image. This separates source-visible house composition from conditional interaction.

The Bedroom bed is the other active object view. Component 4801 on GameObject 398 starts at state 0 (`Bed`) and points to `sharedassets1.assets:640` (`Livingroom2_obj1`); the runtime audit records its bounded `bed_visible` gate and source object hash. Other object-view GameObjects listed above are serialized inactive and remain conditional. Their one-record arrays generally use `None` (-1); an array's presence does not authorize activating its GameObject.

## Bedroom TV and masks

BedroomView's serialized character order contains TV component 5161 on GameObject 1337. That GameObject is activeSelf, its Image 4593 references `Livingroom2_obj2`, and its `CharacterRoomObjectView` initial state is 0 (`ERoomPeopleState.FullSize`) at raw serialized offset 68. The corresponding character data resolves the FullSize pose to the authored TV sprite. The room manifest and scene-render extraction both retain this as a room actor, even though the TV is not an occupant in the host's occupant list.

The value at offset 68 and the `4`/`9` checks below are `ERoomPeopleState` pose values, not `ECharacterType` values. A renderer that gates every actor on occupant membership drops this authored Bedroom fixture.

Recovered `CharacterRoomObjectView.Awake` skips the generic initial-state path only for pose values 9 (`Bags`) and 4 (`Corpse`); TV pose 0 follows it. The generic `ARoomObjectView<T>.Awake` selects `StartState`, and `SelectState` applies the matching state's sprite and transform. `BedroomView.Init` wires the TV callbacks. `BedroomView.SetTVActive(bool)` toggles the TV button's `IsActive`, which controls interaction. The source therefore supports rendering the TV as an always-present house actor while keeping clickability and playback state conditional.

TVMask (GameObject 1091, Image 5079) and Screen (GameObject 533, RawImage 4560) are serialized inactiveSelf. Keep both hidden until a recovered runtime TV state activates them. Likewise, Sexy (character component 4507) and Bedroom Curtain, Clock, and Mushroomlist are inactiveSelf and should not be forced into the base room view.

## Hotspots and remaining behavior

Nine source narrative hotspots are represented by the room manifest and their native narrative records: Bedroom `bedroom_window` and `bedroom_nightstand`; Bathroom `bathroom_window`; BigRoom `bigroom_cross` and `bigroom_toy`; Kitchen `kitchen_cupboards`; Office `office_pictures` and `office_magazine`; Pantry `pantry_box`. The manifest retains each component, referenced UIButton, source GameObject and local position. These are room click targets; this audit does not substitute a close-up image or invent a close-up transition where recovered code/data has not established one.

The 19 static layers and their room-by-room breakdown come from `room_layers_audit.json`; image and hierarchy counts, button links, Sprite PPtrs, activeSelf values and actor/object order come from `room_manifest.json`. The source object-state evidence is the recovered `RoomObjectState<T>` / `ObjectRoomObjectView` layout, `ERoomPeopleState`, `EObjectsRoomObject`, `BedroomView`, `CharacterRoomObjectView`, and `ARoomObjectView<T>` declarations and recovered ISIL, plus the raw `level1` component bytes. Beer1/Beer2 state slots are in `state_objects.json`. Those recovered declarations/ISIL and the Unity checkpoint are under `recovery/checkpoint/reconstruction/logic`; the original game executable and libraries were not run.

Validation against the supplied raw Unity data: `tools/reverse-rooms/export_room_manifest.py` reproduces the tracked manifest; `tools/reverse-rooms/validate_room_manifest.py` passes all seven rooms, fully consumed object-state records, 80 UIButton components (79 room-array refs), nine narrative components and 35 resolved Image/Sprite links; `tools/android-current/stage_room_layers.py --check` passes its seven-room audit with 19 always-visible layers, one conditionally gated bed, and 75 exclusions. These checks establish extraction and staging consistency, not actual Android rendering.
