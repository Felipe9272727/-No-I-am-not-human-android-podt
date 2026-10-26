# Reverse graphics evidence

This directory records static source findings that guide the libGDX reconstruction. It does not claim a full recreation of Unity's renderer.

`unity-render-settings-evidence.json` is extracted from `restore-v08/unity-data` with UnityPy 1.25.4. The Unity data identifies version 6000.3.10f1 and URP Universal Runtime components. The project uses Linear color space, the selected quality tier is High Fidelity URP, room cameras permit HDR, and the level1 scene has fog disabled.

The project default `DefaultVolumeProfile` has Tonemapping mode `None` and neutral ColorAdjustments (`postExposure=0.0 EV`). The active `level1` scene starts with a global `[POSTPROCESS] Volume` at weight 1 referencing the `Night` profile. Night's Tonemapping component is active and mode `Neutral` (enum value 1). The scene view provider also references a `Day` profile, and recovered game code switches the Volume profile according to time of day.

The Day profile has Tonemapping and ColorAdjustments components, but both are inactive. Its disabled ColorAdjustments payload stores `postExposure=+3.48 EV`; that value is not applied while the component is inactive. The Night profile has no ColorAdjustments component. Thus neither effective profile indicates a positive exposure lift, although Night uses Neutral tone mapping and both profiles have other color effects such as ColorCurves. The JSON distinguishes stored values from active overrides.

The serialized MonoBehaviour objects lack UnityPy type trees. Values were decoded from raw payloads using the component field order and typed override/value pairs, then cross-checked against the profile references in scene and data assets and recovered Assembly-CSharp fields. Unity's URP `NeutralTonemap` implementation is linked in the JSON for its actual source constants. For the bright ceiling, check the port's intermediate LDR clipping, point-light range and attenuation, and active scene ColorCurves/ChannelMixer data before adding output transforms.
