# Estado atual

O código atual acrescenta a casa 3D original, movimento com joystick, câmera por toque e interação com portas. Os diálogos e a pausa usam imagens/fontes e coordenadas recuperadas da UI. O pacote anterior já possuía a abertura original e a primeira sequência do vizinho; essa sequência continua preservada.

Os extratores recuperaram 153 MeshRenderers, 100 malhas, 57 materiais, 42 texturas, 104 componentes de colisão, duas câmeras e 34 luzes. A extração de UI resolveu 119 sprites e cinco fontes TTF. Geometria, texturas e fontes são preservadas no pacote de dados separado; o APK usa variantes de textura limitadas a 1024 pixels para reduzir memória.

## Verificado nesta etapa

- Teste C++/Rust com ASan/UBSan: menu, introdução, duas rotas de entrada, duas rotas da primeira conversa, telefone, guardas de navegação e restauração de câmera/estado.
- WorldMathTest: direção do joystick, rotação, diagonal, limites de pitch e conversão UV.
- WorldGeometryTest: sete colliders originais de interação; movimento de 2,379 m desde a câmera inicial até parar na porta.
- Renderização real em Mesa EGL/OpenGL 4.5 por software; captura corrigida para a origem das linhas do framebuffer.
- Compilação Java contra Android 35/libGDX e preparação dos recursos.

Os relatórios em `reconstruction/android-current/` distinguem o teste de regras, a renderização no computador e a inspeção do APK. Nenhuma execução em Android é reivindicada.

## Limites

A campanha para após a primeira conversa interna do vizinho; o save é temporário. Close-up/pinos do telefone, novos dias, efeitos e animações restantes ainda não estão integrados. O movimento de 2,5 m/s é uma adaptação móvel, pois a velocidade original serializada não foi confirmada. Shader, iluminação e colisão aproximam a implementação original; a geometria/texturas extraídas são reais.

O Git é o registro do código atual. A cópia privada de versão 8 serve como base anterior e fonte de dados; não deve sobrescrever código novo do repositório.

## Crash investigation (2026-10-25)

The user reports v0.2 exits after the intro, before the house appears. The
original renderer passed a 120-frame Mesa OpenGL ES 2 check during investigation;
that does not reproduce the Redmi/Android failure. A new test APK, version 0.3-crash-fix, was built and verified with private on-device Java/native-exit diagnostics, an explicit debug
intro skip, guarded MediaPlayer callbacks and a conditional shader fallback.
Current Java passes 120 GLES2 frames normally and another 120 frames after a
simulated shader compile exception. Native tombstone parsing and geometry tests
pass. The APK is signed with the same certificate as v0.2 and contains no new
permissions. The unaccelerated API35 emulator exposed ADB and eventually completed first
boot, but its package/activity services were unusable: installation returned
Broken pipe (32), and no app launched. This is an environment blocker, not an
Android gameplay pass. Physical Redmi validation remains outstanding.
The precise device crash cause is still unconfirmed.

## v0.4: confirmed shader packaging regression

The device report identifies a missing libGDX classpath resource,
`com/badlogic/gdx/graphics/g3d/shaders/default.vertex.glsl`, on the first
3D draw. v0.3 contains no GLSL resources. D8 kept library classes while the
manual APK builder dropped the accompanying Java resources. Earlier host
rendering accidentally supplied these files from the development GDX jar.

The builder now preserves 12 namespaced GDX resources at the APK root and
verifies their exact bytes against the pinned library. A separate probe runs
with a classes-only GDX jar and the APK as its only shader source. It reproduces
the exact v0.3 FileNotFound failure. The final v0.4 APK passes this probe;
its resource URL points inside the delivered APK. With the same isolated
classpath it also renders 120 GLES2 frames without GL errors or fallback.
UI work replaces generic buttons/cards with recovered menu/HUD/dialogue art,
uses recovered fonts, and wraps long Portuguese choices without truncating them.
Menu font selection and some mobile sizing remain explicitly inferred.
The physical-device fix is not yet verified.


## v0.5: source music and rendering corrections

The user confirmed v0.4 enters the 3D house, then supplied screenshots of white
objects, open/black surfaces and a persistent renderer warning. Two world PNGs
in that APK differed from their staged-manifest hashes and failed full PNG
verification. The source media bundle reproduces their expected Android bytes;
all 1,387 staged PNGs now verify and fully decode.

The renderer reverses culling for 33 mirrored instances among 109 active source
renderers, respects blend/depth-write/alpha-clip settings, avoids using normal
maps as diffuse maps, and uses source camera near/far planes. It requests a
24-bit depth buffer. Java geometry/material regression tests, normal and
injected-fallback Mesa GLES2 renders pass. Other camera angles still expose
incomplete scene coverage, so this is not a claim of finished visual parity.

The original menu, night1 and house-ambient AudioSources identify the three
tracks used by this opening. Fourteen original music clips are recovered with
static Unity extraction and trusted ffmpeg conversion. Later-day music routing
is explicitly unresolved, and the campaign still ends at its existing boundary.
The Android player pauses with the activity, preserves track position on resume,
releases previous players on switches and provides a persistent mute option.
The original intro movie retains its own soundtrack.

Crash-history policy regression checks suppress the user's old timestamp after
an APK update, avoid repeated notices and keep unrelated Java/native reports
separate. v0.5 has not been executed on a physical Android device.

The final v0.5 APK is 322,331,722 bytes, SHA-256
`3159894270ae6be78993478c142ff56baa3659b6441f90809e27f554732e4117`.
Its closed-file signature verifies with the stable certificate, and all
1,404 PNGs in the APK fully decode (1,387 staged game PNGs plus Android/library
resources). Fourteen OGG assets match the fully decoded export and are stored
uncompressed. A new isolated check loads all shader resources from this exact
APK and renders 120 GLES2 frames. The first packaging attempt was rejected by
independent integrity checks and was not delivered.


## v0.6: visibility and measured work reduction

The user reports about 10 FPS on the Xiaomi with v0.5. This has not been profiled
on the device, so no CPU/GPU bottleneck or phone FPS gain is claimed.

Two confirmed rendering defects were fixed: Unity Cull 0/1/2 was passed as GL
enumerants, and half extents were passed to a Frustum overload that halves full
dimensions again. Source triangle rays prove the near walls/ceiling exist and
face the camera. Regressions reproduce both old failures; the corrected bounds
pass twelve source structure/camera cases. Four-angle renders now show the
original near surfaces instead of terrain/void through missing walls.

A new offline C++ helper uses pinned meshoptimizer v1.3 for exact 32-byte vertex
remap and vertex-fetch ordering. All 372,897 indexed corners remain byte exact
and triangles/submesh order are preserved. Across 100 meshes, vertices fall
from 372,897 to 98,536 and raw blobs from 13,424,292 to 4,644,740 bytes. The Java
uploader retains shared indices instead of expanding every triangle again.
Five GLES2 captures (four directions plus injected fallback) are pixel-identical
to the unoptimized meshes with the same corrected visibility.

Materials/renderables/lists are reused; pure no-contribution alpha-zero passes
are skipped. The default 3D surface is capped at 1600x720, with a 1200x540 light
mode and native option. UI/touch layout keeps display coordinates. Native
surface behavior and FPS improvements require the user's phone test. An FPS
counter and private render-submit/draw/texture counters help that test.

The intro preserves explicit subtitle line breaks. Music and the existing
campaign boundary remain unchanged. New code does not run original binaries.


## v0.7: Android HUD software rasterization

The user reports v0.6 remains very stuttery. A source audit identified an explicit
LAYER_TYPE_SOFTWARE on the full-screen transparent GameCanvas and unconditional
HUD invalidation for every look pointer movement. These common Canvas operations
are supported by the target hardware UI pipeline; there was no required software
operation. The application/window now request hardware acceleration and the view
uses the default layer. Look-only input updates GLES without repainting the HUD;
hint down/up, changed joystick, state/interaction and FPS changes still invalidate
when their visible content changes. Diagnostics record Canvas acceleration and
HUD draw rate/CPU recording time on the actual device.

Source geometry math did not explain a 100ms frame in the isolated JDK benchmark.
The interaction hit path nevertheless allocated about3.7–4.0KiB/call. Primitive
ray math and immutable cached target JSON reduce that to about3B/call after warmup
(the miss path measured0B). 14,000 source OBB ray cases match the old float result
bit for bit. Tests cover unchanged snapshot reuse, defensive copies, changed
entrance actions and target disappearance. These microbenchmarks are not ART or
phone FPS measurements.

The GL loop is non-continuous under menu, intro and boundary, with explicit state
wakeups. Playing/tools scenes remain continuous. Loop transition tests pass.
All four source views plus the injected shader fallback render120 GLES2 frames
without GL errors and match v0.6 pixels. The final APK loads shaders solely from
its own resources and requests hardware UI in its binary manifest. No host test
validates Android Canvas/SurfaceFlinger composition or physical FPS here. The
full campaign remains bounded; new interactions were paused for the FPS work.
