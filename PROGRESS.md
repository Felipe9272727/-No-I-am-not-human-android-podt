# Current scope

The previous signed opening APK passed host rule tests and package checks. It
contains the original menu/intro, first Neighbour entrance and in-house dialogue,
phone number state and in-memory snapshots. No Android execution test is claimed
by the build environment.

The current work reconstructs the original 3D house, touch joystick/look controls
and original UI. Static analysis found 153 mesh renderers, 100 meshes, 57 materials,
42 textures, 104 collider components, and the original UI sprites/fonts. These
exports are being regenerated after workspace maintenance. Integration tests and
graphics checks for the new version must complete before a new APK is delivered.

Known limits: the campaign ends after the first in-house Neighbour conversation;
save state is not persistent after closing the app; phone close-up/pin UI and
later days remain unfinished. Movement speed and some original rendering effects
remain explicit mobile approximations until independently recovered.
