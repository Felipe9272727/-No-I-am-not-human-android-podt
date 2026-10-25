package org.reconstruction.current;

import com.badlogic.gdx.ApplicationAdapter;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.graphics.GL20;
import com.badlogic.gdx.graphics.PerspectiveCamera;
import com.badlogic.gdx.graphics.Texture;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.badlogic.gdx.math.Matrix4;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.io.PrintWriter;
import java.io.StringWriter;

/** Draws recovered room backgrounds and flat character cards on LibGDX's GL thread. */
public final class RoomEngine extends ApplicationAdapter {
    private static final float SOURCE_WIDTH = 1920f;
    private static final float SOURCE_HEIGHT = 1080f;
    private static final float SOURCE_ASPECT = SOURCE_WIDTH / SOURCE_HEIGHT;
    private static final float MAIN_FOV = 60f;
    private static final float ENTRANCE_FOV = 32.9f;
    private static final long TEXTURE_BUDGET_BYTES = 64L * 1024L * 1024L;
    private static final float[] ROOM_DISTANCE = {1.25f, 1.4f, 1.5f, 1f, 1f, 1f, 2f};

    private volatile String pendingAssetsJson = "{}";
    private volatile String pendingStateJson = "{}";
    private String appliedAssetsJson;
    private String appliedStateJson;

    private SpriteBatch batch;
    private PerspectiveCamera camera;
    private volatile WorldRenderer worldRenderer;
    private final Matrix4 spriteTransform = new Matrix4();
    private int viewportX, viewportY, viewportWidth, viewportHeight;
    private int room = -1;
    private boolean scenePhase;
    private String viewMode = "world";
    private boolean inBatch;
    private JSONArray roomObjects = new JSONArray();
    private volatile String rendererStatus = "loading: waiting for GL surface";
    private volatile String rendererStage = "create room renderer";
    private volatile String rendererDiagnostic = "";
    private volatile boolean rendererFailed;

    private final Map<String, String> imagePaths = new HashMap<>();
    private final Map<Integer, String> roomBackgrounds = new HashMap<>();
    private final Map<String, JSONObject> roomLayouts = new HashMap<>();
    private final Map<Integer, Map<String, JSONObject>> roomLayoutsByRoom = new HashMap<>();
    private final Set<String> missingAssets = new HashSet<>();
    private final LinkedHashMap<String, TextureEntry> textures = new LinkedHashMap<>(16, 0.75f, true);
    private final List<Texture> transientTextures = new ArrayList<>();
    private long textureBytes;

    public RoomEngine() { }

    public RoomEngine(JSONObject assets) { setAssets(assets); }

    /** May be called from any thread. Assets are parsed and textures are touched on the GL thread. */
    public void setAssets(JSONObject assets) {
        pendingAssetsJson = assets == null ? "{}" : assets.toString();
    }

    /** Copies the root state for a thread-safe handoff; never calls native gameplay code. */
    public void setState(JSONObject state) {
        pendingStateJson = state == null ? "{}" : state.toString();
    }

    @Override public void create() {
        try {
            rendererStage = "create SpriteBatch shader";
            batch = new SpriteBatch();
            rendererStage = "create room camera";
            camera = new PerspectiveCamera(MAIN_FOV, SOURCE_WIDTH, SOURCE_HEIGHT);
            worldRenderer = new WorldRenderer("");
            rendererStage = "create 3D renderer";
            worldRenderer.create();
            camera.near = 0.1f;
            camera.far = 10000f;
            rendererStage = "parse presentation assets";
            applyPendingAssets();
            applyPendingState();
            updateViewport(Gdx.graphics.getWidth(), Gdx.graphics.getHeight());
            updateCamera();
            rendererStatus = worldRenderer.getStatus();
        } catch (RuntimeException error) { failRenderer(error); }
    }

    @Override public void resize(int width, int height) {
        updateViewport(width, height);
        updateCamera();
        if (worldRenderer != null) worldRenderer.resize(viewportWidth, viewportHeight);
    }

    @Override public void render() {
        if (rendererFailed) return;
        try {
            rendererStage = "apply renderer state";
            applyPendingAssets();
            applyPendingState();
            if (batch == null || camera == null) return;
            rendererStage = "clear frame";
            Gdx.gl.glViewport(viewportX, viewportY, viewportWidth, viewportHeight);
            Gdx.gl.glClearColor(0f, 0f, 0f, 1f);
            Gdx.gl.glClear(GL20.GL_COLOR_BUFFER_BIT | GL20.GL_DEPTH_BUFFER_BIT);
            if (!scenePhase) return;
            if ("world".equals(viewMode)) {
                rendererStage = "render GLES world scene";
                if (worldRenderer != null) worldRenderer.render(Gdx.graphics.getDeltaTime());
                if (worldRenderer != null) rendererStatus = worldRenderer.getStatus();
                return;
            }
            if (room < 0) return;
            rendererStage = "draw room sprites";
            updateCamera();
            camera.update();
            batch.setProjectionMatrix(camera.combined);
            batch.begin();
            inBatch = true;
            drawBackground();
            drawActors();
            batch.end();
            inBatch = false;
            disposeTransientTextures();
            rendererStatus = "ready";
        } catch (RuntimeException error) {
            if (inBatch) { try { batch.end(); } catch (RuntimeException ignored) { } inBatch = false; }
            if (worldRenderer != null && "render GLES world scene".equals(rendererStage)) worldRenderer.failRender(error);
            failRenderer(error);
        }
    }

    private void updateViewport(int width, int height) {
        if (width <= 0 || height <= 0) return;
        float aspect = width / (float) height;
        if (aspect > SOURCE_ASPECT) {
            viewportHeight = height;
            viewportWidth = Math.round(height * SOURCE_ASPECT);
        } else {
            viewportWidth = width;
            viewportHeight = Math.round(width / SOURCE_ASPECT);
        }
        viewportX = (width - viewportWidth) / 2;
        viewportY = (height - viewportHeight) / 2;
        if (camera != null) {
            camera.viewportWidth = SOURCE_WIDTH;
            camera.viewportHeight = SOURCE_HEIGHT;
            camera.update();
        }
        if (worldRenderer != null) worldRenderer.resize(viewportWidth, viewportHeight);
    }

    private void updateCamera() {
        if (camera == null) return;
        float fov = room == 5 ? ENTRANCE_FOV : MAIN_FOV;
        float multiplier = room >= 0 && room < ROOM_DISTANCE.length ? ROOM_DISTANCE[room] : 1f;
        camera.fieldOfView = fov;
        float baseDistance = (float) (SOURCE_HEIGHT / (2.0 * Math.tan(Math.toRadians(fov * 0.5))));
        float cameraDistance = baseDistance * multiplier;
        camera.position.set(SOURCE_WIDTH * multiplier * 0.5f,
                SOURCE_HEIGHT * multiplier * 0.5f, cameraDistance);
        camera.direction.set(0f, 0f, -1f);
        camera.up.set(0f, 1f, 0f);
    }

    private void applyPendingAssets() {
        String serialized = pendingAssetsJson;
        if (serialized.equals(appliedAssetsJson)) return;
        appliedAssetsJson = serialized;
        disposeTextures();
        imagePaths.clear();
        roomBackgrounds.clear();
        roomLayouts.clear();
        roomLayoutsByRoom.clear();
        missingAssets.clear();
        try {
            JSONObject root = new JSONObject(serialized);
            if (worldRenderer != null) worldRenderer.setManifestPath(root.optString("world_manifest", ""));
            JSONObject images = root.optJSONObject("images");
            if (images != null) {
                Iterator<String> keys = images.keys();
                while (keys.hasNext()) {
                    String key = keys.next();
                    String path = images.optString(key, "");
                    if (!path.isEmpty()) imagePaths.put(key, path);
                }
            }
            JSONArray backgrounds = root.optJSONArray("backgrounds");
            if (backgrounds != null) for (int i = 0; i < backgrounds.length(); i++) {
                JSONObject item = backgrounds.optJSONObject(i);
                if (item == null) continue;
                int roomId = item.optInt("room", -1);
                String asset = item.optString("asset", "");
                if (roomId >= 0 && !asset.isEmpty()) roomBackgrounds.put(roomId, asset);
            }
            JSONObject layouts = root.optJSONObject("room_layout");
            if (layouts != null) {
                Iterator<String> keys = layouts.keys();
                while (keys.hasNext()) {
                    String key = keys.next();
                    JSONObject layout = layouts.optJSONObject(key);
                    if (layout != null) roomLayouts.put(key, layout);
                }
            }
            JSONObject layoutsByRoom = root.optJSONObject("room_layout_by_room");
            if (layoutsByRoom != null) {
                Iterator<String> roomKeys = layoutsByRoom.keys();
                while (roomKeys.hasNext()) {
                    String roomKey = roomKeys.next();
                    JSONObject roomEntry = layoutsByRoom.optJSONObject(roomKey);
                    JSONObject characters = roomEntry == null ? null : roomEntry.optJSONObject("characters");
                    if (characters == null) continue;
                    try {
                        int roomId = Integer.parseInt(roomKey);
                        Map<String, JSONObject> characterLayouts = new HashMap<>();
                        Iterator<String> characterKeys = characters.keys();
                        while (characterKeys.hasNext()) {
                            String name = characterKeys.next();
                            JSONObject layout = characters.optJSONObject(name);
                            if (layout != null) characterLayouts.put(name, layout);
                        }
                        roomLayoutsByRoom.put(roomId, characterLayouts);
                    } catch (NumberFormatException ignored) { }
                }
            }
        } catch (JSONException ignored) {
            // A bad presentation manifest leaves the scene black without interrupting the app.
        }
    }

    private void applyPendingState() {
        String serialized = pendingStateJson;
        if (serialized.equals(appliedStateJson)) return;
        appliedStateJson = serialized;
        scenePhase = false;
        room = -1;
        viewMode = "world";
        roomObjects = new JSONArray();
        try {
            JSONObject state = new JSONObject(serialized);
            String phase = state.optString("phase", "");
            scenePhase = "playing".equals(phase) || "tools".equals(phase);
            room = state.optInt("room", -1);
            viewMode = state.optString("view_mode", "world");
            if (!"world".equals(viewMode) && !"room".equals(viewMode)) viewMode = "world";
            if (worldRenderer != null) worldRenderer.applyState(state);
            JSONArray objects = state.optJSONArray("room_objects");
            if (objects != null) roomObjects = objects;
        } catch (JSONException ignored) {
            // Invalid state clears the room until the next safe update arrives.
        }
    }

    private void drawBackground() {
        Texture texture = texture(roomBackgrounds.get(room));
        if (texture != null) {
            float scale = roomScale();
            drawContain(texture, 0f, 0f, SOURCE_WIDTH * scale, SOURCE_HEIGHT * scale, -2f * scale);
        }
    }

    private void drawActors() {
        List<RoomActor> actors = new ArrayList<>();
        for (int i = 0; i < roomObjects.length(); i++) {
            JSONObject object = roomObjects.optJSONObject(i);
            if (object == null || object.optInt("room", -1) != room || !object.optBoolean("active", false)) continue;
            String name = object.optString("name", "");
            Map<String, JSONObject> roomLayout = roomLayoutsByRoom.get(room);
            JSONObject layout = roomLayout == null ? null : roomLayout.get(name);
            if (layout == null) layout = roomLayouts.get(name);
            actors.add(new RoomActor(object, layout, layout == null ? i : layout.optInt("order", i), i));
        }
        Collections.sort(actors, new Comparator<RoomActor>() {
            @Override public int compare(RoomActor a, RoomActor b) {
                int order = Integer.compare(a.order, b.order);
                return order != 0 ? order : Integer.compare(a.originalIndex, b.originalIndex);
            }
        });
        for (RoomActor actor : actors) drawActor(actor);
    }

    private void drawActor(RoomActor actor) {
        JSONObject object = actor.object;
        Texture sprite = texture(object.optString("asset", ""));
        if (sprite == null) return;
        float[] size = vector2(actor.layout == null ? null : actor.layout.optJSONArray("size"), 50f, 130f);
        float[] pivot = vector2(actor.layout == null ? null : actor.layout.optJSONArray("pivot"), 0.5f, 0.5f);
        float[] position = vector3(object.optJSONArray("position"), 0f, 0f, 0f);
        float[] poseScale = vector3(object.optJSONArray("scale"), 1f, 1f, 1f);
        float canvasScale = roomScale();
        float width = Math.max(1f, size[0] * Math.abs(poseScale[0]) * canvasScale);
        float height = Math.max(1f, size[1] * Math.abs(poseScale[1]) * canvasScale);
        float centerX = (SOURCE_WIDTH * 0.5f + position[0]) * canvasScale;
        float centerY = (SOURCE_HEIGHT * 0.5f + position[1]) * canvasScale;
        float left = centerX - width * clamp01(pivot[0]);
        float bottom = centerY - height * clamp01(pivot[1]);
        drawContain(sprite, left, bottom, width, height, finiteOr(position[2], 0f) * canvasScale);
    }

    private Texture texture(String assetKey) {
        if (assetKey == null || assetKey.isEmpty()) return null;
        String path = imagePaths.containsKey(assetKey) ? imagePaths.get(assetKey) : assetKey;
        if (path.startsWith("/") || path.contains("..")) return null;
        TextureEntry cached = textures.get(path);
        if (cached != null) return cached.texture;
        if (missingAssets.contains(path) || Gdx.files == null) return null;
        try {
            if (inBatch) batch.flush();
            Texture texture = new Texture(Gdx.files.internal(path));
            texture.setFilter(Texture.TextureFilter.Linear, Texture.TextureFilter.Linear);
            texture.setWrap(Texture.TextureWrap.ClampToEdge, Texture.TextureWrap.ClampToEdge);
            long bytes = Math.max(1L, (long) texture.getWidth() * texture.getHeight() * 4L);
            if (bytes > TEXTURE_BUDGET_BYTES) {
                transientTextures.add(texture);
                return texture;
            }
            textures.put(path, new TextureEntry(texture, bytes));
            textureBytes += bytes;
            trimTextureCache();
            return textures.containsKey(path) ? texture : null;
        } catch (Exception ignored) {
            missingAssets.add(path);
            return null;
        }
    }

    private void trimTextureCache() {
        if (inBatch && textureBytes > TEXTURE_BUDGET_BYTES) batch.flush();
        Iterator<Map.Entry<String, TextureEntry>> iterator = textures.entrySet().iterator();
        while (textureBytes > TEXTURE_BUDGET_BYTES && iterator.hasNext()) {
            TextureEntry eldest = iterator.next().getValue();
            textureBytes -= eldest.bytes;
            eldest.texture.dispose();
            iterator.remove();
        }
    }

    private void drawContain(Texture texture, float x, float y, float width, float height, float depth) {
        float contentScale = Math.min(width / texture.getWidth(), height / texture.getHeight());
        float drawWidth = texture.getWidth() * contentScale;
        float drawHeight = texture.getHeight() * contentScale;
        float drawX = x + (width - drawWidth) * 0.5f;
        float drawY = y + (height - drawHeight) * 0.5f;
        spriteTransform.idt().setToTranslation(0f, 0f, depth);
        batch.setTransformMatrix(spriteTransform);
        batch.draw(texture, drawX, drawY, drawWidth, drawHeight);
        spriteTransform.idt();
        batch.setTransformMatrix(spriteTransform);
    }

    private float roomScale() {
        return room >= 0 && room < ROOM_DISTANCE.length ? ROOM_DISTANCE[room] : 1f;
    }

    private static float[] vector2(JSONArray values, float x, float y) {
        return new float[] {
                (float) (values == null ? x : values.optDouble(0, x)),
                (float) (values == null ? y : values.optDouble(1, y))
        };
    }

    private static float[] vector3(JSONArray values, float x, float y, float z) {
        return new float[] {
                (float) (values == null ? x : values.optDouble(0, x)),
                (float) (values == null ? y : values.optDouble(1, y)),
                (float) (values == null ? z : values.optDouble(2, z))
        };
    }

    private static float clamp01(float value) {
        if (Float.isNaN(value)) return 0.5f;
        return Math.max(0f, Math.min(1f, value));
    }

    private static float finiteOr(float value, float fallback) {
        return Float.isNaN(value) || Float.isInfinite(value) ? fallback : value;
    }

    private void disposeTransientTextures() {
        for (Texture texture : transientTextures) texture.dispose();
        transientTextures.clear();
    }

    /** Thread-safe input feed from the Android joystick and look surface. */
    public void setMoveVector(float x, float forward) { if (worldRenderer != null) worldRenderer.setMoveVector(x, forward); }
    public void addLookDelta(float dx, float dy) { if (worldRenderer != null) worldRenderer.addLookDelta(dx, dy); }
    public void setInputEnabled(boolean enabled) { if (worldRenderer != null) worldRenderer.setInputEnabled(enabled); }
    public JSONObject getInteraction() { return worldRenderer == null ? null : worldRenderer.getInteraction(); }
    public JSONObject getPose() { return worldRenderer == null ? new JSONObject() : worldRenderer.getPose(); }
    public String getRendererStatus() {
        WorldRenderer world = worldRenderer;
        String worldStatus = world == null ? "" : world.getStatus();
        if (rendererStatus.startsWith("error:")) return rendererStatus;
        if (worldStatus.startsWith("error:") || worldStatus.startsWith("loading:")) return worldStatus;
        return rendererStatus;
    }
    public int getFrameRate() { WorldRenderer world=worldRenderer; return world==null?0:world.getFrameRate(); }

    public String getRendererDiagnostic() {
        if (rendererStatus.startsWith("error:") && !rendererDiagnostic.isEmpty()) return rendererDiagnostic;
        WorldRenderer world = worldRenderer;
        if (world != null) {
            String detail = world.getDiagnostic();
            if (detail != null && !detail.isEmpty() && !"ready".equals(detail)) return detail;
        }
        return rendererDiagnostic.isEmpty() ? getRendererStatus() : rendererDiagnostic;
    }

    private void failRenderer(RuntimeException error) {
        rendererStatus = errorStatus(rendererStage, error);
        StringWriter trace = new StringWriter(); error.printStackTrace(new PrintWriter(trace));
        String gl = "GL information unavailable";
        try { gl = "GL vendor=" + Gdx.gl.glGetString(GL20.GL_VENDOR) + ", renderer=" + Gdx.gl.glGetString(GL20.GL_RENDERER) + ", version=" + Gdx.gl.glGetString(GL20.GL_VERSION); }
        catch (RuntimeException ignored) { }
        rendererDiagnostic = "Renderer failure at " + rendererStage + "\n" + gl + "\n\n" + trace;
        rendererFailed = true;
    }

    private static String errorStatus(String stage, Throwable error) {
        String detail = error.getClass().getSimpleName() + ": " + String.valueOf(error.getMessage());
        detail = detail.replace('\n', ' ').replace('\r', ' ').trim();
        if (detail.length() > 160) detail = detail.substring(0, 157) + "...";
        return "error: " + stage + ": " + detail;
    }

    private void disposeTextures() {
        for (TextureEntry entry : textures.values()) entry.texture.dispose();
        textures.clear();
        textureBytes = 0L;
        disposeTransientTextures();
    }

    @Override public void dispose() {
        if (worldRenderer != null) worldRenderer.dispose();
        worldRenderer = null;
        disposeTextures();
        if (batch != null) batch.dispose();
        batch = null;
        camera = null;
    }

    private static final class TextureEntry {
        final Texture texture;
        final long bytes;
        TextureEntry(Texture texture, long bytes) { this.texture = texture; this.bytes = bytes; }
    }

    private static final class RoomActor {
        final JSONObject object;
        final JSONObject layout;
        final int order;
        final int originalIndex;
        RoomActor(JSONObject object, JSONObject layout, int order, int originalIndex) {
            this.object = object;
            this.layout = layout;
            this.order = order;
            this.originalIndex = originalIndex;
        }
    }
}
