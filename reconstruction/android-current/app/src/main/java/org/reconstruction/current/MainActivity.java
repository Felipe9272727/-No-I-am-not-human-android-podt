package org.reconstruction.current;

import com.badlogic.gdx.backends.android.AndroidApplication;
import com.badlogic.gdx.backends.android.AndroidApplicationConfiguration;

import android.app.AlertDialog;
import android.content.res.AssetFileDescriptor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffColorFilter;
import android.graphics.RectF;
import android.graphics.SurfaceTexture;
import android.graphics.Typeface;
import android.media.MediaPlayer;
import android.opengl.GLSurfaceView;
import android.os.Bundle;
import android.os.Handler;
import android.os.SystemClock;
import android.util.LruCache;
import android.view.MotionEvent;
import android.view.Surface;
import android.view.TextureView;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.ArrayAdapter;
import android.widget.FrameLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Landscape host for the recovered menu, intro movie, native state, and LibGDX room scene. */
public final class MainActivity extends AndroidApplication {
    static { System.loadLibrary("ninah_current"); }

    private static native String nativeCreate(String program, String metadata);
    private static native String nativeAction(String action);

    private final Map<String, String> imagePaths = new HashMap<>();
    private final Map<String, String> menuAssets = new HashMap<>();
    private final Map<Integer, String> roomBackgrounds = new HashMap<>();
    private final Map<String, JSONObject> roomLayouts = new HashMap<>();
    private final Map<Integer, Map<String, JSONObject>> roomLayoutsByRoom = new HashMap<>();
    private final Map<String, String> translatedLines = new HashMap<>();
    private final Map<String, Typeface> uiFonts = new HashMap<>();
    private JSONObject uiManifest = new JSONObject();
    private final LruCache<String, Bitmap> bitmaps = new LruCache<String, Bitmap>(32 * 1024 * 1024) {
        @Override protected int sizeOf(String key, Bitmap value) { return Math.max(1, value.getAllocationByteCount()); }
    };
    private final Set<String> missingBitmaps = new HashSet<>();
    private final ExecutorService nativeWorker = Executors.newSingleThreadExecutor();
    private final Handler ui = new Handler();

    private FrameLayout host;
    private View roomEngineView;
    private RoomEngine roomEngine;
    private TextureView introView;
    private Surface introSurface;
    private MediaPlayer introPlayer;
    private boolean introPrepared;
    private boolean activityResumed;
    private String activeIntroAsset = "";
    private GameCanvas canvas;
    private JSONObject state = new JSONObject();
    private volatile boolean initialized;
    private volatile boolean nativeBusy;
    private String loadError;
    private float uiScale = 1f;
    private boolean muteIntro;
    private boolean toolsMode;
    private String lastPhase = "";
    private long campaignClockOrigin;
    private boolean resetCampaignClock;
    private long lastIntroTick = -1;
    private boolean introFinishedPending;
    private int introCompletionTickAttempts;
    private volatile JSONObject nearbyInteraction;
    private String nearbyInteractionSignature = "";
    private int joystickPointer = -1, lookPointer = -1;
    private float joystickX, joystickY, lookLastX, lookLastY;
    private final Map<Integer,Integer> pointerRoles = new HashMap<>();
    private final Map<Integer,Hit> pointerHits = new HashMap<>();

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Window window = getWindow();
        window.getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_LAYOUT_STABLE |
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        host = new FrameLayout(this);
        AndroidApplicationConfiguration cfg = new AndroidApplicationConfiguration();
        cfg.useAccelerometer = false; cfg.useCompass = false; cfg.useGyroscope = false;
        roomEngine = new RoomEngine();
        roomEngineView = initializeForView(roomEngine, cfg);
        if (roomEngineView instanceof GLSurfaceView) ((GLSurfaceView) roomEngineView).setZOrderMediaOverlay(true);
        roomEngineView.setVisibility(View.VISIBLE);
        introView = new TextureView(this);
        introView.setVisibility(View.GONE);
        introView.setSurfaceTextureListener(new TextureView.SurfaceTextureListener() {
            @Override public void onSurfaceTextureAvailable(SurfaceTexture texture, int width, int height) {
                introSurface = new Surface(texture); fitIntroVideo(width, height); prepareIntro();
            }
            @Override public void onSurfaceTextureSizeChanged(SurfaceTexture texture, int width, int height) { fitIntroVideo(width, height); }
            @Override public boolean onSurfaceTextureDestroyed(SurfaceTexture texture) {
                releaseIntro(); if (introSurface != null) { introSurface.release(); introSurface = null; }
                return true;
            }
            @Override public void onSurfaceTextureUpdated(SurfaceTexture texture) { }
        });
        canvas = new GameCanvas();
        canvas.setBackgroundColor(Color.TRANSPARENT);
        host.addView(roomEngineView, new FrameLayout.LayoutParams(-1, -1));
        host.addView(introView, new FrameLayout.LayoutParams(-1, -1));
        host.addView(canvas, new FrameLayout.LayoutParams(-1, -1));
        setContentView(host);

        nativeBusy = true;
        nativeWorker.execute(() -> {
            JSONObject initial;
            try {
                JSONObject assets = new JSONObject(readAssetText("presentation/assets.json"));
                loadPresentationAssets(assets);
                JSONObject gameUi = assets.optJSONObject("game_ui");
                String uiPath = gameUi == null ? "presentation/ui/ui_manifest.json" : gameUi.optString("manifest", "presentation/ui/ui_manifest.json");
                try { uiManifest = new JSONObject(readAssetText(uiPath)); } catch (Exception ignored) { }
                roomEngine.setAssets(assets);
                loadTranslations();
                initial = parseState(nativeCreate(readAssetText("narrative/program.json"), readAssetText("narrative/line_metadata.json")));
            } catch (Exception e) {
                loadError = "Não foi possível iniciar o núcleo: " + e.getMessage();
                initial = parseState("{}");
                try { initial.put("error", loadError); } catch (JSONException ignored) { }
            }
            final JSONObject result = initial;
            runOnUiThread(() -> applyState(result));
        });
    }

    private String readAssetText(String path) throws Exception {
        try (InputStream input = getAssets().open(path); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192]; int count;
            while ((count = input.read(buffer)) >= 0) output.write(buffer, 0, count);
            return new String(output.toByteArray(), StandardCharsets.UTF_8);
        }
    }

    private void loadPresentationAssets(JSONObject root) {
        JSONObject images = root.optJSONObject("images");
        copyMap(images, imagePaths);
        JSONArray backgrounds = root.optJSONArray("backgrounds");
        if (backgrounds != null) for (int i = 0; i < backgrounds.length(); i++) {
            JSONObject b = backgrounds.optJSONObject(i);
            if (b != null && b.optInt("room", -1) >= 0) roomBackgrounds.put(b.optInt("room"), b.optString("asset", ""));
        }
        JSONObject layout = root.optJSONObject("room_layout");
        if (layout != null) { Iterator<String> it = layout.keys(); while (it.hasNext()) { String name = it.next(); roomLayouts.put(name, layout.optJSONObject(name)); } }
        JSONObject byRoom = root.optJSONObject("room_layout_by_room");
        if (byRoom != null) {
            Iterator<String> rooms = byRoom.keys();
            while (rooms.hasNext()) {
                String roomKey = rooms.next(); JSONObject entry = byRoom.optJSONObject(roomKey);
                JSONObject characters = entry == null ? null : entry.optJSONObject("characters");
                if (characters == null) continue;
                try {
                    int room = Integer.parseInt(roomKey); Map<String, JSONObject> layouts = new HashMap<>();
                    Iterator<String> names = characters.keys(); while (names.hasNext()) { String name=names.next(); JSONObject value=characters.optJSONObject(name); if(value!=null)layouts.put(name,value); }
                    roomLayoutsByRoom.put(room,layouts);
                } catch (NumberFormatException ignored) { }
            }
        }
        JSONObject menu = root.optJSONObject("menu");
        if (menu != null) {
            copyMap(menu.optJSONObject("images"), menuAssets);
            for (String key : new String[]{"background_asset","house_asset","logo_asset","eyes_asset","teeth_asset","button_asset","peephole_asset"}) {
                String path = menu.optString(key, ""); if (!path.isEmpty()) menuAssets.put(key.replace("_asset", ""), path);
            }
        }
        for (String key : new String[]{"background_asset","house_asset","logo_asset","eyes_asset","teeth_asset","button_asset","peephole_asset"}) {
            String path = root.optString(key, ""); if (!path.isEmpty()) menuAssets.put(key.replace("_asset", ""), path);
        }
    }

    private void copyMap(JSONObject source, Map<String, String> target) {
        if (source == null) return;
        Iterator<String> it = source.keys();
        while (it.hasNext()) { String key = it.next(); target.put(key, source.optString(key, "")); }
    }

    private void loadTranslations() throws Exception {
        JSONObject root = new JSONObject(readAssetText("narrative/texts_ptbr.json"));
        JSONObject texts = root.optJSONObject("texts"); if (texts == null) texts = root;
        copyMap(texts, translatedLines);
        copyMap(root.optJSONObject("ids"), translatedLines);
    }

    private JSONObject parseState(String raw) {
        try { return new JSONObject(raw == null ? "{}" : raw); }
        catch (JSONException e) { JSONObject bad = new JSONObject(); try { bad.put("error", "Resposta inválida do núcleo: " + e.getMessage()); } catch (JSONException ignored) { } return bad; }
    }

    private static String stringField(JSONObject object, String key, String fallback) {
        if (object == null || object.isNull(key)) return fallback;
        String value = object.optString(key, fallback);
        return value == null || value.isEmpty() ? fallback : value;
    }

    private void applyState(JSONObject next) {
        state = next;
        initialized = "state".equals(next.optString("type", ""));
        nativeBusy = false;
        updateCampaignClock();
        updateEngine();
        updateIntro();
        if (canvas != null) canvas.invalidate();
        advanceIntroCompletion();
    }

    private void advanceIntroCompletion() {
        if (!introFinishedPending || nativeBusy || !initialized) return;
        if (!"intro".equals(state.optString("phase", ""))) { introFinishedPending = false; introCompletionTickAttempts = 0; return; }
        JSONObject intro = state.optJSONObject("intro");
        long recorded = intro == null ? 0L : intro.optLong("elapsed_ms", 0L);
        JSONObject action = new JSONObject();
        try {
            if (recorded < 72000L) {
                if (introCompletionTickAttempts >= 3) { introFinishedPending = false; return; }
                action.put("action", "intro_tick"); action.put("elapsed_ms", 72000L);
                introCompletionTickAttempts++;
            } else {
                action.put("action", "intro_video_finished");
                introFinishedPending = false; introCompletionTickAttempts = 0;
            }
        } catch (JSONException ignored) { return; }
        dispatch(action);
    }

    private void dispatch(JSONObject action) {
        if (!initialized || nativeBusy) return;
        if ("new_game".equals(action.optString("action"))) resetCampaignClock = true;
        nativeBusy = true;
        boolean clockOnly = "campaign_tick".equals(action.optString("action"));
        if (!clockOnly) {
            if (roomEngine != null) roomEngine.setInputEnabled(false);
            resetWorldInput();
        }
        ui.removeCallbacks(interactionPoll);
        if (canvas != null) canvas.invalidate();
        nativeWorker.execute(() -> {
            JSONObject next;
            try { next = parseState(nativeAction(action.toString())); }
            catch (Exception e) { next = parseState("{}"); try { next.put("error", "Ação não concluída: " + e.getMessage()); } catch (JSONException ignored) { } }
            JSONObject result = next;
            runOnUiThread(() -> applyState(result));
        });
    }

    private void updateEngine() {
        if (roomEngine == null || roomEngineView == null) return;
        roomEngine.setState(state);
        roomEngineView.setVisibility(View.VISIBLE);
        boolean enable = "playing".equals(state.optString("phase", "")) && "world".equals(viewMode()) &&
            !nativeBusy && !toolsMode && state.optJSONObject("dialogue") == null &&
            (canvas == null || (!canvas.isPauseOpen() && !canvas.isSettingsOpen()));
        roomEngine.setInputEnabled(enable);
        if (!enable) resetWorldInput();
        if (enable) { ui.removeCallbacks(interactionPoll); ui.post(interactionPoll); }
        else { ui.removeCallbacks(interactionPoll); nearbyInteraction = null; nearbyInteractionSignature = ""; }
    }

    private String viewMode() {
        String mode = state.optString("view_mode", "world");
        return "room".equals(mode) ? "room" : "world";
    }

    private final Runnable interactionPoll = new Runnable() {
        @Override public void run() {
            if (!"playing".equals(state.optString("phase", "")) || !"world".equals(viewMode()) ||
                state.optJSONObject("dialogue") != null || toolsMode || nativeBusy) return;
            JSONObject target = roomEngine == null ? null : roomEngine.getInteraction();
            String signature = target == null ? "" : target.toString();
            if (!signature.equals(nearbyInteractionSignature)) {
                nearbyInteractionSignature = signature; nearbyInteraction = target;
                if (canvas != null) canvas.invalidate();
            }
            ui.postDelayed(this, 100L);
        }
    };

    private void resetWorldInput() {
        if (roomEngine != null) roomEngine.setMoveVector(0f, 0f);
        joystickPointer = -1; lookPointer = -1; joystickX = joystickY = 0f;
        if (canvas != null) canvas.clearPointersFromHost();
    }

    private void dispatchNearbyInteraction() {
        JSONObject target = nearbyInteraction;
        if (target == null || nativeBusy) return;
        String actionName = target.optString("action", "");
        JSONObject action = new JSONObject();
        try {
            if ("actor_talk".equals(actionName)) {
                String character=target.optString("character","");if(character.isEmpty())return;
                action.put("action", "actor_talk"); action.put("character", character);
            } else if ("open_door".equals(actionName)) action.put("action", "open_door");
            else if ("enter_room".equals(actionName) && target.optInt("room", -1) >= 0) {
                action.put("action", "enter_room"); action.put("room", target.optInt("room", -1));
            } else return;
        } catch (JSONException ignored) { return; }
        dispatch(action);
    }

    private void updateCampaignClock() {
        String phase = state.optString("phase", "");
        if ("playing".equals(phase) && !"playing".equals(lastPhase)) {
            JSONObject campaign = state.optJSONObject("campaign");
            long elapsed = campaign == null ? 0L : Math.max(0L, campaign.optLong("elapsed_ms", 0L));
            if (resetCampaignClock) elapsed = 0L;
            campaignClockOrigin = SystemClock.uptimeMillis() - elapsed;
            resetCampaignClock = false;
            ui.removeCallbacks(campaignTicker); ui.post(campaignTicker);
        } else if (!"playing".equals(phase)) ui.removeCallbacks(campaignTicker);
        lastPhase = phase;
    }

    private final Runnable campaignTicker = new Runnable() {
        @Override public void run() {
            if (!initialized || !"playing".equals(state.optString("phase", ""))) return;
            if (!nativeBusy) {
                JSONObject action = new JSONObject();
                try { action.put("action", "campaign_tick"); action.put("elapsed_ms", Math.max(0L, SystemClock.uptimeMillis() - campaignClockOrigin)); }
                catch (JSONException ignored) { }
                dispatch(action);
            }
            ui.postDelayed(this, 250L);
        }
    };

    private void updateIntro() {
        JSONObject intro = state.optJSONObject("intro");
        String asset = intro == null ? "" : intro.optString("video_asset", "");
        if (!"intro".equals(state.optString("phase", "")) || asset.isEmpty()) {
            introView.setVisibility(View.GONE); releaseIntro(); activeIntroAsset = ""; return;
        }
        introView.setVisibility(View.VISIBLE);
        if (!asset.equals(activeIntroAsset)) {
            releaseIntro(); activeIntroAsset = asset;
            if (introSurface != null) prepareIntro();
        } else if (activityResumed && introPlayer != null && introPrepared && !introPlayer.isPlaying()) introPlayer.start();
    }

    private void fitIntroVideo(int width, int height) {
        if (width <= 0 || height <= 0) return;
        float fit = Math.min(width / 1920f, height / 1080f);
        android.graphics.Matrix matrix = new android.graphics.Matrix();
        matrix.setScale(1920f * fit / width, 1080f * fit / height, width / 2f, height / 2f);
        introView.setTransform(matrix);
    }

    private void prepareIntro() {
        if (activeIntroAsset.isEmpty() || introSurface == null || introPlayer != null) return;
        loadError = null;
        try (AssetFileDescriptor afd = getAssets().openFd(activeIntroAsset)) {
            MediaPlayer player = new MediaPlayer();
            introPlayer = player;
            player.setDataSource(afd.getFileDescriptor(), afd.getStartOffset(), afd.getLength());
            player.setSurface(introSurface); player.setLooping(false);
            player.setVolume(muteIntro ? 0f : 1f, muteIntro ? 0f : 1f);
            player.setOnPreparedListener(mp -> { loadError = null; introPlayer = mp; introPrepared = true; if (activityResumed) { mp.start(); ui.post(introTicker); } });
            player.setOnCompletionListener(mp -> {
                introPlayer = null; introPrepared = false; mp.release();
                introFinishedPending = true; introCompletionTickAttempts = 0; advanceIntroCompletion();
            });
            player.setOnErrorListener((mp, what, extra) -> { introPlayer = null; introPrepared = false; mp.release(); loadError = "Vídeo da introdução indisponível."; if (canvas != null) canvas.invalidate(); return true; });
            introPlayer = player; player.prepareAsync();
        } catch (Exception e) { releaseIntro(); loadError = "Não foi possível abrir a introdução: " + e.getMessage(); if (canvas != null) canvas.invalidate(); }
    }

    private final Runnable introTicker = new Runnable() {
        @Override public void run() {
            if (!"intro".equals(state.optString("phase", "")) || !introPrepared || introPlayer == null) return;
            long elapsed = Math.max(0, introPlayer.getCurrentPosition());
            if (elapsed / 250 != lastIntroTick && !nativeBusy) {
                lastIntroTick = elapsed / 250;
                JSONObject a = new JSONObject(); try { a.put("action", "intro_tick"); a.put("elapsed_ms", elapsed); } catch (JSONException ignored) { }
                dispatch(a);
            }
            ui.postDelayed(this, 250L);
        }
    };

    private void releaseIntro() {
        ui.removeCallbacks(introTicker);
        if (introPlayer != null) { introPlayer.setOnCompletionListener(null); introPlayer.release(); introPlayer = null; }
        introPrepared = false; lastIntroTick = -1;
    }

    private Bitmap bitmap(String key) {
        if (key == null || key.isEmpty()) return null;
        String path = imagePaths.getOrDefault(key, key);
        Bitmap cached = bitmaps.get(path); if (cached != null) return cached;
        if (missingBitmaps.contains(path)) return null;
        try (InputStream input = getAssets().open(path)) {
            Bitmap decoded = BitmapFactory.decodeStream(input);
            if (decoded != null) bitmaps.put(path, decoded); else missingBitmaps.add(path);
            return decoded;
        } catch (Exception e) { missingBitmaps.add(path); return null; }
    }

    @Override protected void onPause() {
        activityResumed = false;
        ui.removeCallbacks(campaignTicker); ui.removeCallbacks(introTicker); ui.removeCallbacks(interactionPoll);
        if (roomEngine != null) roomEngine.setInputEnabled(false); resetWorldInput();
        lastPhase = "";
        if (introPlayer != null && introPlayer.isPlaying()) introPlayer.pause();
        super.onPause();
    }

    @Override protected void onResume() {
        activityResumed = true;
        super.onResume(); updateIntro(); updateCampaignClock(); updateEngine();
        if ("intro".equals(state.optString("phase", "")) && introPrepared) { ui.removeCallbacks(introTicker); ui.post(introTicker); }
    }

    @Override protected void onDestroy() {
        ui.removeCallbacks(campaignTicker); releaseIntro(); nativeWorker.shutdown(); super.onDestroy();
    }

    private String translatedText(JSONObject event) {
        String direct = event.optString("text", "");
        if (!direct.isEmpty()) return substituteTokens(direct, event.optJSONObject("substitutions"));
        String id = event.optString("line_id", event.optString("id", ""));
        String result = translatedLines.get(id);
        if (result != null) return substituteArrayTokens(result, event.optJSONArray("substitutions"));
        return id.isEmpty() ? "" : "Texto em português ainda não integrado (" + id + ")";
    }

    private String substituteTokens(String template, JSONObject substitutions) {
        if (substitutions == null) return template;
        String result = template; Iterator<String> keys = substitutions.keys();
        while (keys.hasNext()) { String key = keys.next(); String value = substitutions.optString(key, ""); result = result.replace("{" + key + "}", value).replace("<" + key + ">", value); }
        return result;
    }

    private String substituteArrayTokens(String template, JSONArray substitutions) {
        if (substitutions == null) return template;
        String result = template;
        for (int i = 0; i < substitutions.length(); i++) { String value = substitutions.optString(i, ""); result = result.replace("{" + i + "}", value).replace("<" + i + ">", value); }
        return result;
    }

    private void showOptionsDialog() {
        String[] items = {"Interface maior", "Interface padrão", muteIntro ? "Ativar som da introdução" : "Silenciar introdução"};
        new AlertDialog.Builder(this).setTitle("Opções").setItems(items, (dialog, which) -> {
            if (which == 0) uiScale = 1.15f;
            else if (which == 1) uiScale = 1f;
            else { muteIntro = !muteIntro; if (introPlayer != null) introPlayer.setVolume(muteIntro ? 0f : 1f, muteIntro ? 0f : 1f); }
            canvas.invalidate();
        }).setNegativeButton("Fechar", null).show();
    }

    private final class GameCanvas extends View {
        private static final float W = 1920f, H = 1080f;
        private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
        private final List<Hit> hits = new ArrayList<>();
        private final String[] roomNames = {"Cozinha", "Escritório", "Sala", "Banheiro", "Despensa", "Entrada", "Quarto"};
        private final String[] roomLabels = {"Novo jogo", "Continuar", "Opções", "Coleção", "Sair"};
        private final Map<String, String> animationSignature = new HashMap<>();
        private final Map<String, Long> animationStart = new HashMap<>();
        private float scale;
        private boolean pauseOpen, settingsOpen;
        private Typeface textFontOverride;
        private static final int ROLE_NONE=0, ROLE_UI=1, ROLE_MOVE=2, ROLE_LOOK=3;

        GameCanvas() { super(MainActivity.this); setLayerType(View.LAYER_TYPE_SOFTWARE, null); setWillNotDraw(false); }
        boolean isToolsMode() { return toolsMode; }
        boolean isPauseOpen() { return pauseOpen; }
        boolean isSettingsOpen() { return settingsOpen; }
        void clearPointersFromHost() { pointerRoles.clear(); pointerHits.clear(); }

        @Override protected void onDraw(Canvas screen) {
            super.onDraw(screen);
            scale = Math.min(getWidth() / W, getHeight() / H);
            float ox = (getWidth() - W * scale) / 2f, oy = (getHeight() - H * scale) / 2f;
            screen.save(); screen.translate(ox, oy); screen.scale(scale, scale); hits.clear();
            String phase = state.optString("phase", "menu");
            if (!initialized) drawLoading(screen);
            else if (toolsMode || "tools".equals(phase)) drawTools(screen);
            else if ("menu".equals(phase)) drawMenu(screen);
            else if ("intro".equals(phase)) drawIntro(screen);
            else if ("boundary".equals(phase)) drawBoundary(screen);
            else drawPlayingHud(screen);
            drawError(screen);
            screen.restore();
        }

        private void drawLoading(Canvas c) { c.drawColor(Color.rgb(13,17,22)); center(c,"Carregando dados recuperados…",960,550,32,Color.WHITE,true); }

        private void drawMenu(Canvas c) {
            JSONObject menu=state.optJSONObject("menu");
            String bg=stringField(menu,"background_asset",menuAssets.get("background"));
            Bitmap background=bitmap(bg); if(background!=null) cover(c,background,0,0,W,H); else gradient(c);
            Bitmap house=bitmap(menuAssets.get("house")); if(house!=null) contain(c,house,0,0,W,H);
            Bitmap circle=bitmap(menuAssets.get("peephole")); if(circle!=null) contain(c,circle,0,0,W,H);
            Bitmap logo=bitmap(stringField(menu,"logo_asset",menuAssets.get("logo")));
            if(logo!=null) contain(c,logo,641, -111,1279,526);
            else { center(c,"NO, I'M NOT A HUMAN",960,180,48,Color.WHITE,true); }
            Bitmap eyes=bitmap(menuAssets.get("eyes")), teeth=bitmap(menuAssets.get("teeth"));
            Bitmap eyeMask=bitmap(menuAssets.get("mask_eyes")),teethMask=bitmap(menuAssets.get("mask_teeth"));
            Bitmap eyeLight=bitmap(menuAssets.get("light_eyes")),teethLight=bitmap(menuAssets.get("light_teeth"));
            if(eyeMask!=null) contain(c,eyeMask,889,429,1031,493);
            if(eyes!=null) contain(c,eyes,889,429,1031,493);
            if(eyeLight!=null) contain(c,eyeLight,889,429,1031,493);
            if(teethMask!=null) contain(c,teethMask,889,508,1031,572);
            if(teeth!=null) contain(c,teeth,889,510,1031,563);
            if(teethLight!=null) contain(c,teethLight,889,510,1031,563);
            Bitmap tri=bitmap(menuAssets.get("trioskaz_banner")); if(tri!=null) contain(c,tri,1292,687,1500,923);
            Bitmap wishlist=bitmap(menuAssets.get("wishlist_banner")); if(wishlist!=null) contain(c,wishlist,1206,847,1279,918);
            String[] labels=roomLabels; float[] centers={520,740,960,1180,1400};
            boolean canContinue=menu!=null&&menu.optBoolean("can_continue",false);
            Bitmap buttonSprite=bitmap(menuAssets.get("button"));
            for(int i=0;i<labels.length;i++) {
                float x=centers[i], top=937.5f, bottom=1012.5f;
                if(buttonSprite!=null) contain(c,buttonSprite,x-100,top,x+100,bottom); else fill(c,x-100,top,x+100,bottom,i==0?0xFF8A4D39:0xFF303840,8);
                String label=labels[i]; center(c,label,x,top+48,22,i==1&&!canContinue?0xFF929292:Color.WHITE,true);
                final int action=i;
                hits.add(new Hit(new RectF(x-100,top,x+100,bottom),()->menuChoice(action,canContinue)));
            }
            button(c,"Ferramentas",1710,25,1880,88,0xCC252E36,12,()->{toolsMode=true;updateEngine();invalidate();});
        }

        private void menuChoice(int choice, boolean canContinue) {
            if(choice==0) act("new_game",null,null);
            else if(choice==1&&canContinue) act("continue_game",null,null);
            else if(choice==2) MainActivity.this.showOptionsDialog();
            else if(choice==3) new AlertDialog.Builder(MainActivity.this).setTitle("Coleção")
                .setMessage("A coleção ainda não está disponível nesta versão.").setPositiveButton("Fechar",null).show();
            else if(choice==4) finish();
        }

        private void drawIntro(Canvas c) {
            JSONObject intro=state.optJSONObject("intro");
            fill(c,60,800,1860,1045,0xD9000000,18);
            String subtitle=introCaption(intro);
            if(!subtitle.isEmpty()) wrap(c,subtitle,115,860,1650,38,4,Color.WHITE,28);
            if(intro!=null&&intro.optBoolean("can_skip",false)) button(c,"Pular introdução",1600,940,1830,1020,0xFF754B3B,14,()->act("skip_intro",null,null));
            button(c,"Menu",80,940,250,1020,0xCC2B343D,14,()->act("menu",null,null));
            if(introPlayer==null&&!activeIntroAsset.isEmpty()) text(c,"Preparando vídeo…",280,990,20,Color.WHITE,false);
        }

        private String introCaption(JSONObject intro) {
            if(intro==null)return "";
            String direct=intro.optString("subtitle_text",""); if(!direct.isEmpty())return direct;
            JSONArray ids=intro.optJSONArray("subtitle_line_ids"); if(ids==null)return "";
            StringBuilder result=new StringBuilder();
            for(int i=0;i<ids.length();i++){String line=translatedLines.get(ids.optString(i,""));if(line!=null&&!line.isEmpty()){if(result.length()>0)result.append('\n');result.append(line);}}
            return result.toString();
        }

        private void drawPlayingHud(Canvas c) {
            if ("world".equals(viewMode())) drawWorldHud(c); else drawRoomHud(c);
            JSONObject sign=state.optJSONObject("sign"); if(sign!=null)drawSign(c,sign);
            if(toolsMode) drawToolsBar(c);
        }

        private void drawWorldHud(Canvas c) {
            if(settingsOpen){drawSettingsPanel(c);return;}
            if(pauseOpen){drawPausePanel(c);return;}
            JSONObject dialogue=state.optJSONObject("dialogue");
            if(dialogue!=null){drawDialogue(c,dialogue);drawPortrait(c,state.optJSONObject("portrait"));return;}
            drawHudComponents(c,"world",true,"SaveIcon");
            button(c,"Ⅱ",1780,25,1870,110,0xCC242B32,10,()->{pauseOpen=true;updateEngine();invalidate();});
            if(nearbyInteraction!=null&&!nativeBusy) {
                String label=nearbyLabel(nearbyInteraction);
                button(c,label,1450,845,1845,945,0xEE874C34,16,MainActivity.this::dispatchNearbyInteraction);
            }
            drawJoystick(c);drawRightLookHint(c);
        }

        private String nearbyLabel(JSONObject target) {
            String action=target.optString("action","");
            if("open_door".equals(action))return "Atender à porta";
            if("actor_talk".equals(action))return "Falar com o vizinho";
            if("enter_room".equals(action)) {
                int room=target.optInt("room",-1);
                if(room==5)return "Olhar pelo olho mágico";
                if(room>=0&&room<roomNames.length)return "Entrar: "+roomNames[room];
            }
            return "Interagir";
        }

        private void drawRoomHud(Canvas c) {
            JSONObject dialogue=state.optJSONObject("dialogue");
            if(dialogue!=null){drawDialogue(c,dialogue);drawPortrait(c,state.optJSONObject("portrait"));return;}
            button(c,"Voltar ao mundo",1630,28,1870,105,0xCC242B32,12,()->act("enter_world",null,null));
            JSONObject campaign=state.optJSONObject("campaign");
            if(campaign!=null&&campaign.optBoolean("neighbour_can_talk",false))
                button(c,"Conversar com o Vizinho",1390,870,1810,970,0xEE874C34,14,this::actorTalkNeighbour);
        }

        private void drawSettingsPanel(Canvas c) {
            fill(c,0,0,W,H,0xA9000000,0);fill(c,620,235,1300,850,0xF0141A20,20);
            center(c,"OPÇÕES",960,330,34,Color.WHITE,true);
            button(c,uiScale>1f?"Interface maior ✓":"Interface maior",700,395,1220,475,0xFF46545C,12,()->{uiScale=1.15f;invalidate();});
            button(c,uiScale==1f?"Interface padrão ✓":"Interface padrão",700,500,1220,580,0xFF46545C,12,()->{uiScale=1f;invalidate();});
            button(c,muteIntro?"Som da introdução: desligado":"Som da introdução: ligado",700,605,1220,685,0xFF46545C,12,()->{muteIntro=!muteIntro;if(introPlayer!=null)introPlayer.setVolume(muteIntro?0f:1f,muteIntro?0f:1f);invalidate();});
            button(c,"Fechar",700,710,1220,790,0xFF794839,12,()->{settingsOpen=false;updateEngine();invalidate();});
        }

        private void drawPausePanel(Canvas c) {
            drawHudComponents(c,"pause",false,null);
            drawPauseLabel(c,"PauseText","PAUSADO");
            drawPauseButton(c,"Continue","Continuar",()->{pauseOpen=false;updateEngine();invalidate();});
            drawPauseButton(c,"Settings","Opções",MainActivity.this::showOptionsDialog);
            drawPauseButton(c,"Menu","Menu principal",()->{pauseOpen=false;act("menu",null,null);});
            drawPauseButton(c,"Exit","Salvar sessão",this::saveWorldState);
        }

        private void drawPauseButton(Canvas c,String control,String label,Runnable action) {
            JSONObject item=findPauseComponent(control,"Text (TMP)");float[] rect=uiBounds(item);
            if(rect==null){float y="Continue".equals(control)?393:"Settings".equals(control)?543:"Menu".equals(control)?693:843;rect=new float[]{70,y,692,y+84};}
            drawSourceLabel(c,label,rect,36,Color.WHITE);hits.add(new Hit(new RectF(rect[0],rect[1],rect[2],rect[3]),action));
        }

        private void drawPauseLabel(Canvas c,String control,String label) {
            JSONObject item=findPauseComponent(control,null);float[] rect=uiBounds(item);if(rect!=null)drawSourceLabel(c,label,rect,42,Color.WHITE);
        }

        private JSONObject findPauseComponent(String buttonName,String componentName) {
            JSONArray items=sceneComponents("pause");if(items==null)return null;
            for(int i=0;i<items.length();i++) {
                JSONObject item=items.optJSONObject(i);if(item==null)continue;
                if(componentName!=null&&!componentName.equals(uiName(item)))continue;
                JSONArray h=item.optJSONArray("hierarchy");if(h==null)continue;boolean underButton=false,matched=false;
                for(int j=0;j<h.length();j++){String part=h.optString(j,"");if(buttonName.equals(part))underButton=true;if("Buttons".equals(part))matched=true;}
                if(underButton&&(matched||"PauseText".equals(buttonName)))return item;
            }
            return null;
        }

        private void drawSourceLabel(Canvas c,String value,float[] rect,float size,int color) {
            p.setColor(color);p.setTypeface(fontFor(findPauseComponentForTextRect(rect)));p.setTextSize(size*uiScale);p.setTextAlign(Paint.Align.CENTER);
            Paint.FontMetrics fm=p.getFontMetrics();float y=(rect[1]+rect[3]-(fm.ascent+fm.descent))/2f;c.drawText(value,(rect[0]+rect[2])/2f,y,p);p.setTextAlign(Paint.Align.LEFT);
        }

        private JSONObject findPauseComponentForTextRect(float[] rect) {
            JSONArray items=sceneComponents("pause");if(items==null)return null;
            for(int i=0;i<items.length();i++){JSONObject item=items.optJSONObject(i);if(item!=null&&"text".equals(item.optString("kind",""))&&uiBounds(item)!=null){float[] b=uiBounds(item);if(Math.abs(b[0]-rect[0])<2&&Math.abs(b[1]-rect[1])<2)return item;}}
            return null;
        }

        private void drawJoystick(Canvas c) {
            float cx=250,cy=835,r=135;p.setColor(0x553A4148);p.setStyle(Paint.Style.FILL);c.drawCircle(cx,cy,r,p);
            p.setColor(0xAAADB3B8);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(4);c.drawCircle(cx,cy,r,p);p.setStyle(Paint.Style.FILL);
            p.setColor(0xB8D4D6D8);c.drawCircle(cx+joystickX*r,cy-joystickY*r,54,p);
        }

        private void drawRightLookHint(Canvas c) {
            if(lookPointer<0){p.setColor(0x77FFFFFF);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(3);c.drawCircle(1770,830,44,p);p.setStyle(Paint.Style.FILL);}
        }

        private void drawHudComponents(Canvas c,String scene,boolean includeText,String onlyName) {
            JSONArray items=sceneComponents(scene);
            if(items==null)return;
            List<JSONObject> sorted=new ArrayList<>();
            for(int i=0;i<items.length();i++) {
                JSONObject item=items.optJSONObject(i);if(item==null)continue;
                if(onlyName!=null&&!onlyName.equals(uiName(item)))continue;
                if("dialogue".equals(scene)&&wrongDialogueCanvas(item))continue;
                if("dialogue".equals(scene)&&"Character".equals(uiName(item)))continue;
                boolean visible=item.optBoolean("visible",false);
                if("pause".equals(scene)&&"pause_open".equals(item.optString("runtime_visibility_condition",""))&&isPauseBase(item))visible=true;
                if(visible)sorted.add(item);
            }
            sorted.sort((a,b)->Integer.compare(a.optInt("z",0),b.optInt("z",0)));
            for(JSONObject item:sorted) {
                float[] r=uiBounds(item);if(r==null||r[2]<=r[0]||r[3]<=r[1])continue;
                JSONObject imageData=item.optJSONObject("image");
                String asset=uiAsset(item);
                if(!asset.isEmpty()) {
                    Bitmap image=bitmap(asset);
                    if(image!=null) {
                        int tint=uiColor(item,imageData),opaqueTint=0xFF000000|(tint&0x00FFFFFF);
                        p.setColorFilter(opaqueTint==Color.WHITE?null:new PorterDuffColorFilter(opaqueTint,PorterDuff.Mode.MULTIPLY));
                        p.setAlpha(Color.alpha(tint));
                        boolean preserve=imageData==null?item.optBoolean("preserve_aspect",false):imageData.optBoolean("preserve_aspect",false);
                        if(preserve)contain(c,image,r[0],r[1],r[2],r[3]);else stretch(c,image,r[0],r[1],r[2],r[3]);
                        p.setAlpha(255);p.setColorFilter(null);
                    }
                } else if("image".equals(item.optString("kind",""))) {
                    int color=uiColor(item,imageData);if(Color.alpha(color)>0){p.setColor(color);c.drawRect(r[0],r[1],r[2],r[3],p);p.setColor(Color.WHITE);}
                }
                String value=includeText?uiText(item):"";
                if(!value.isEmpty()) {
                    p.setTypeface(fontFor(item));p.setTextSize((float)item.optDouble("font_size",20)*uiScale);
                    p.setColor(uiColor(item,null));
                    String align=item.optString("alignment","");p.setTextAlign("center".equalsIgnoreCase(align)?Paint.Align.CENTER:"right".equalsIgnoreCase(align)?Paint.Align.RIGHT:Paint.Align.LEFT);
                    Paint.FontMetrics fm=p.getFontMetrics();float x="center".equalsIgnoreCase(align)?(r[0]+r[2])/2f:"right".equalsIgnoreCase(align)?r[2]-6:r[0]+6;
                    float y=(r[1]+r[3]-(fm.ascent+fm.descent))/2f;c.save();c.clipRect(r[0],r[1],r[2],r[3]);c.drawText(value,x,y,p);c.restore();p.setTextAlign(Paint.Align.LEFT);
                }
            }
        }

        private JSONArray sceneComponents(String scene) { JSONObject scenes=uiManifest.optJSONObject("scenes");return scenes==null?null:scenes.optJSONArray(scene); }

        private String uiName(JSONObject item) { return item.optString("game_object_name",item.optString("name","")); }

        private String uiAsset(JSONObject item) {
            String path=item.isNull("asset")?"":item.optString("asset","");if(!path.isEmpty()&&!("null".equals(path)))return path;
            JSONObject image=item.optJSONObject("image");String key=image==null||image.isNull("sprite_key")?"":image.optString("sprite_key","");
            if(key.isEmpty())return "";
            JSONObject sprites=uiManifest.optJSONObject("sprites"),entry=sprites==null?null:sprites.optJSONObject(key);
            return entry==null?"":entry.optString("android_asset",entry.optString("asset",""));
        }

        private int uiAlpha(JSONObject item,JSONObject image) { return Color.alpha(uiColor(item,image)); }

        private int uiColor(JSONObject item,JSONObject image) {
            JSONArray rgba=item.optJSONArray("color");if(rgba==null&&image!=null)rgba=image.optJSONArray("color_rgba");
            if(rgba!=null&&rgba.length()>=4)return Color.argb(channel(rgba,3),channel(rgba,0),channel(rgba,1),channel(rgba,2));
            String value=item.optString("color","");if(value.startsWith("#")){try{long n=Long.parseLong(value.substring(1),16);if(value.length()==7)n|=0xFF000000L;return (int)n;}catch(Exception ignored){}}
            return Color.WHITE;
        }

        private int channel(JSONArray rgba,int i) { return Math.max(0,Math.min(255,Math.round((float)rgba.optDouble(i,1)*255f))); }

        private boolean wrongDialogueCanvas(JSONObject item) {
            JSONArray h=item.optJSONArray("hierarchy");if(h==null)return false;boolean option=false,line=false;
            for(int i=0;i<h.length();i++){String part=h.optString(i,"");option|="Options List View".equals(part);line|="Line View".equals(part);}
            JSONObject d=state.optJSONObject("dialogue");boolean showingOptions=d!=null&&"options".equals(d.optString("type",""));
            return option&&!showingOptions||line&&showingOptions;
        }

        private boolean isPauseBase(JSONObject item) {
            JSONArray h=item.optJSONArray("hierarchy");if(h==null)return false;boolean pause=false,base=false,settings=false;
            for(int i=0;i<h.length();i++){String part=h.optString(i,"");pause|="Pause".equals(part);base|="BG".equals(part)||"NotBG".equals(part);settings|="Settings".equals(part);}
            return pause&&base&&!settings;
        }

        private float[] uiBounds(JSONObject item) {
            if(item==null)return null;
            JSONObject rt=item.optJSONObject("rect_transform");
            JSONArray rect=rt==null?null:rt.optJSONArray("screen_rect_1920x1080");
            if(rect==null)rect=item.optJSONArray("screen_rect_1920x1080");
            if(rect!=null&&rect.length()>=4) {double x=rect.optDouble(0,0),y=rect.optDouble(1,0),w=rect.optDouble(2,0),h=rect.optDouble(3,0);return new float[]{(float)x,(float)y,(float)(x+w),(float)(y+h)};}
            if(rt!=null&&(rect=rt.optJSONArray("normalized_rect_1920x1080"))!=null){}else rect=item.optJSONArray("normalized_rect_1920x1080");
            if(rect==null)return null;double x=rect.optDouble(0,0),y=rect.optDouble(1,0),w=rect.optDouble(2,0),h=rect.optDouble(3,0);
            return new float[]{(float)(x*W),(float)(y*H),(float)((x+w)*W),(float)((y+h)*H)};
        }

        private String uiText(JSONObject item) {
            JSONObject t=item.optJSONObject("text");if(t!=null)return t.optString("value","");
            return item.optString("label","");
        }

        private Typeface fontFor(JSONObject item) {
            if(item==null)return Typeface.DEFAULT;
            if(item.isNull("font_asset"))return Typeface.DEFAULT;
            String path=item.optString("font_asset","");if(path.isEmpty())return Typeface.DEFAULT;
            Typeface cached=uiFonts.get(path);if(cached!=null)return cached;
            try{Typeface loaded=Typeface.createFromAsset(getAssets(),path);uiFonts.put(path,loaded);return loaded;}catch(Exception ignored){return Typeface.DEFAULT;}
        }

        private int parseUiColor(String value) {
            try{String hex=value.startsWith("#")?value.substring(1):value;long n=Long.parseLong(hex,16);if(hex.length()==6)n|=0xFF000000L;return (int)n;}catch(Exception ignored){return Color.WHITE;}
        }

        private void drawDialogue(Canvas c,JSONObject d) {
            Typeface old=textFontOverride;textFontOverride=dialogueFont(d);
            try { drawDialogueContent(c,d); } finally { textFontOverride=old; }
        }

        private Typeface dialogueFont(JSONObject d) {
            JSONObject scenes=uiManifest.optJSONObject("scenes");JSONArray items=scenes==null?null:scenes.optJSONArray("dialogue");
            if(items==null)return Typeface.DEFAULT;
            boolean options=d!=null&&"options".equals(d.optString("type",""));
            for(int i=0;i<items.length();i++) {
                JSONObject item=items.optJSONObject(i);if(item==null||!"Text".equals(uiName(item)))continue;
                JSONArray h=item.optJSONArray("hierarchy");boolean inExpected=false;
                if(h!=null)for(int j=0;j<h.length();j++){String part=h.optString(j,"");if(options&&"Options List View".equals(part))inExpected=true;if(!options&&"Line View".equals(part))inExpected=true;}
                if(inExpected)return fontFor(item);
            }
            return Typeface.DEFAULT;
        }

        private void drawDialogueContent(Canvas c,JSONObject d) {
            if(d==null)return;
            String kind=d.optString("type","line"),name=d.optString("character",state.optString("character",""));
            boolean options="options".equals(kind);String plateName=options?"DialogContent2":"DialogContent";
            drawHudComponents(c,"dialogue",false,plateName);
            JSONObject textComponent=findDialogueText(options);float[] textRect=uiBounds(textComponent);
            if(textRect==null)textRect=new float[]{1010,249,1678,569};
            float left=textRect[0]+22,right=textRect[2]-22,top=textRect[1]+12,bottom=textRect[3]-12;
            if(!name.isEmpty())text(c,name.toUpperCase(),left,top+24,23,0xFFE0AE79,true);
            if("command".equals(kind)) {
                text(c,"Comando ainda não integrado: "+d.optString("command",""),left,top+86,27,0xFFFFC685,true);
                text(c,"A execução permanece pendente.",left,top+128,23,Color.WHITE,false);return;
            }
            if(options){showOptionsCanvas(c,d.optJSONArray("options"),new float[]{left,top+42,right,bottom});return;}
            if("error".equals(kind)||"stopped".equals(kind)) {
                wrap(c,d.optString("message",d.optString("error","")),left,top+78,right-left,36,5,Color.WHITE,27);return;
            }
            float bodyTop=top+66;
            wrap(c,translatedText(d),left,bodyTop,right-left,36,4,Color.WHITE,30);
            hits.add(new Hit(new RectF(left,bodyTop-22,right,bottom-58),()->showFullDialogue(d)));
            button(c,"Avançar",right-180,bottom-54,right,bottom-6,0xAA915B3E,10,()->act("advance",null,null));
        }

        private JSONObject findDialogueText(boolean options) {
            JSONArray items=sceneComponents("dialogue");if(items==null)return null;
            for(int i=0;i<items.length();i++) {
                JSONObject item=items.optJSONObject(i);if(item==null||!"Text".equals(uiName(item)))continue;
                JSONArray h=item.optJSONArray("hierarchy");if(h==null)continue;
                for(int j=0;j<h.length();j++)if((options&&"Options List View".equals(h.optString(j,"")))||(!options&&"Line View".equals(h.optString(j,""))))return item;
            }
            return null;
        }

        private void showOptionsCanvas(Canvas c,JSONArray options,float[] area) {
            if(options==null)return;
            int rows=Math.min(4,options.length());float rowHeight=Math.min(52f,(area[3]-area[1]-10f)/Math.max(1,rows));
            for(int i=0;i<rows;i++) {
                JSONObject option=options.optJSONObject(i); final int index=i;
                String label=option==null?"Opção "+(i+1):optionText(option,i);
                boolean enabled=option==null||option.optBoolean("enabled",true);
                float y=area[1]+i*rowHeight;
                button(c,label,area[0],y,area[2],y+rowHeight-5,enabled?0x77465760:0x7731373D,8,()->{if(enabled)act("choose","index",index);});
            }
            if(options.length()>4) button(c,"Mais opções",area[2]-190,area[3]-48,area[2],area[3],0xAA46545C,8,()->showOptionsDialog(options));
        }

        private void drawPortrait(Canvas c,JSONObject portrait) {
            if(portrait==null)return; JSONArray frames=portrait.optJSONArray("frames"); if(frames==null||frames.length()==0)return;
            Bitmap image=bitmap(animated("portrait",frames,portrait.optInt("fps",1),portrait.optInt("cycling",2))); if(image==null)return;
            JSONArray position=portrait.optJSONArray("position"),poseScale=portrait.optJSONArray("scale");
            if(position==null||position.length()<2){JSONObject character=findDialogueComponent("Character");float[] b=uiBounds(character);if(b!=null)contain(c,image,b[0],b[1],b[2],b[3]);return;}
            float sx=poseScale==null?1f:Math.abs((float)poseScale.optDouble(0,1)),sy=poseScale==null?1f:Math.abs((float)poseScale.optDouble(1,1));
            float width=645f*sx,height=800f*sy,cx=960f+(float)position.optDouble(0,0),cy=540f-(float)position.optDouble(1,0);
            contain(c,image,cx-width/2f,cy-height/2f,cx+width/2f,cy+height/2f);
        }

        private JSONObject findDialogueComponent(String name) {
            JSONArray items=sceneComponents("dialogue");if(items==null)return null;for(int i=0;i<items.length();i++){JSONObject item=items.optJSONObject(i);if(item!=null&&name.equals(uiName(item)))return item;}return null;
        }

        private void drawSign(Canvas c,JSONObject sign) {
            fill(c,1350,150,1870,790,0xF0080C10,18);
            String[] names={"Olhos","Mãos","Dentes","Foto","Axila","Orelha"}; int kind=Math.max(0,Math.min(5,sign.optInt("kind",0)));
            text(c,sign.optString("character","")+" • "+names[kind],1380,205,22,Color.WHITE,true);
            button(c,"Fechar",1690,165,1840,225,0xFF71483D,12,()->act("stop_sign",null,null));
            JSONArray frames=sign.optJSONArray("frames"); Bitmap img=frames!=null&&frames.length()>0?bitmap(animated("sign",frames,sign.optInt("fps",1),sign.optInt("cycling",2))):bitmap(sign.optString("sprite",""));
            if(img!=null)contain(c,img,1390,245,1830,640);
            Bitmap white=bitmap(sign.optString("white","")),iris=bitmap(sign.optString("iris",""));if(white!=null)contain(c,white,1400,250,1820,640);if(iris!=null)contain(c,iris,1510,330,1710,560);
            String[] raw={"Eye","Hands","Teeth","AuraPhoto","Armpit","Ear"};
            for(int i=0;i<6;i++){final int n=i;button(c,names[i],1370+(i%3)*155,660+(i/3)*54,1510+(i%3)*155,708+(i/3)*54,i==kind?0xFF965F42:0xFF3C484F,8,()->act("inspect","sign",raw[n]));}
        }

        private void drawBoundary(Canvas c) {
            c.drawColor(0xFF11161C); fill(c,160,140,1760,930,0xFF252E36,28);
            text(c,"LIMITE DA RECONSTRUÇÃO",235,250,28,0xFFE2B181,true);
            JSONObject campaign=state.optJSONObject("campaign");String note=campaign==null?"Conteúdo de campanha ainda não integrado.":campaign.optString("boundary","Conteúdo de campanha ainda não integrado.");
            if(note.contains("talk_neighbour_1")) note="Esta prévia termina após a primeira conversa com o vizinho dentro da casa. As próximas visitas e os próximos dias ainda estão em desenvolvimento.";
            wrap(c,note,235,335,1420,42,8,Color.WHITE,30);
            button(c,"Voltar ao menu",235,800,545,880,0xFF46535D,14,()->act("menu",null,null));
        }

        private void drawTools(Canvas c) {
            String phase=state.optString("phase","");
            if(!state.optString("character","").isEmpty()&&"tools".equals(phase)) drawPlayingHud(c);
            else c.drawColor(0xFF151A20);
            if(!state.has("character")) {
                text(c,"FERRAMENTAS DE TESTE DO NÚCLEO",90,110,32,Color.WHITE,true);
                text(c,"Rotas isoladas: não representam uma campanha completa.",90,155,22,0xFFC4C9CD,false);
                button(c,"Fatman • recompensa",90,220,620,305,0xFF456257,16,()->scenario("fatman"));
                button(c,"Firefighter • recusa",650,220,1180,305,0xFF5D4947,16,()->scenario("firefighter"));
                button(c,"Alkonost • energia",1210,220,1740,305,0xFF504D72,16,()->scenario("alkonost"));
            } else drawToolsBar(c);
            button(c,"Voltar ao menu",90,350,360,425,0xFF3C474F,14,()->{toolsMode=false;act("menu",null,null);});
        }

        private void drawToolsBar(Canvas c) {
            fill(c,30,120,1890,210,0xE90A0F15,12);
            text(c,"TESTES",55,178,19,0xFFE0AD79,true);
            button(c,"Fatman",260,135,440,197,0xFF456257,10,()->scenario("fatman"));
            button(c,"Firefighter",455,135,655,197,0xFF5D4947,10,()->scenario("firefighter"));
            button(c,"Alkonost",670,135,870,197,0xFF504D72,10,()->scenario("alkonost"));
            button(c,"Salvar",890,135,1050,197,0xFF46545C,10,this::saveWorldState);
            button(c,state.optBoolean("save_available",false)?"Retomar":"Sem teste salvo",1065,135,1285,197,0xFF46545C,10,()->{if(state.optBoolean("save_available",false))act("load",null,null);});
            if(!state.optString("character","").isEmpty()) button(c,"Inspecionar",1310,135,1550,197,0xFF46545C,10,()->{
                String[] labels={"Olhos","Mãos","Dentes","Foto","Axila","Orelha"};
                String[] signs={"Eye","Hands","Teeth","AuraPhoto","Armpit","Ear"};
                new AlertDialog.Builder(MainActivity.this).setTitle("Inspeção de teste").setItems(labels,(dialog,index)->act("inspect","sign",signs[index])).setNegativeButton("Fechar",null).show();
            });
        }

        private void drawError(Canvas c) {
            String error=state.isNull("error")?"":state.optString("error","");if(error.isEmpty()&&loadError!=null)error=loadError;if(error==null||error.isEmpty()||"null".equals(error))return;
            fill(c,35,12,1885,92,0xDD58231C,10);text(c,error,65,60,20,Color.WHITE,true);
        }

        private void actorTalkNeighbour() {
            JSONObject action=new JSONObject();
            try { action.put("action","actor_talk"); action.put("character","Neighbour"); }
            catch(JSONException ignored) { }
            dispatch(action);
        }

        private void saveWorldState() {
            JSONObject action=new JSONObject();JSONObject pose=roomEngine==null?null:roomEngine.getPose();
            try { action.put("action","save");if(pose!=null)action.put("world_pose",pose); }
            catch(JSONException ignored) { }
            dispatch(action);
        }

        private void addNeighbourHit(int room) {
            JSONArray objects=state.optJSONArray("room_objects"); if(objects==null)return;
            for(int i=0;i<objects.length();i++) {
                JSONObject actor=objects.optJSONObject(i);
                if(actor==null||!actor.optBoolean("active",false)||actor.optInt("room",-1)!=room||!"Neighbour".equals(actor.optString("name","")))continue;
                Map<String,JSONObject> roomMap=roomLayoutsByRoom.get(room);
                JSONObject layout=roomMap==null?null:roomMap.get("Neighbour");
                if(layout==null)layout=roomLayouts.get("Neighbour");
                JSONArray size=layout==null?null:layout.optJSONArray("size"),pivot=layout==null?null:layout.optJSONArray("pivot");
                JSONArray pos=actor.optJSONArray("position"),pose=actor.optJSONArray("scale");
                float px=(float)(pos==null?0:pos.optDouble(0,0)), py=(float)(pos==null?0:pos.optDouble(1,0));
                float sx=(float)(pose==null?1:pose.optDouble(0,1)), sy=(float)(pose==null?1:pose.optDouble(1,1));
                float w=(float)(size==null?80:size.optDouble(0,80))*Math.abs(sx),h=(float)(size==null?130:size.optDouble(1,130))*Math.abs(sy);
                float ax=(float)(pivot==null?.5:pivot.optDouble(0,.5)),ay=(float)(pivot==null?.5:pivot.optDouble(1,.5));
                float left=960+px-w*ax,top=540-py-h*(1-ay); 
                hits.add(new Hit(new RectF(left,top,left+w,top+h),this::actorTalkNeighbour));
                return;
            }
        }

        private void showRoomChooser() {
            new AlertDialog.Builder(MainActivity.this).setTitle("Ir para um cômodo")
                .setItems(roomNames,(dialog,which)->act("room","room",which)).setNegativeButton("Cancelar",null).show();
        }

        private void showFullDialogue(JSONObject d) {
            String type=d.optString("type","line");String message=translatedText(d);
            if("options".equals(type)){StringBuilder all=new StringBuilder();JSONArray options=d.optJSONArray("options");if(options!=null)for(int i=0;i<options.length();i++){JSONObject o=options.optJSONObject(i);all.append(i+1).append(". ").append(o==null?"Opção":optionText(o,i)).append(o!=null&&!o.optBoolean("enabled",true)?" (indisponível)":"").append('\n');}message=all.toString();}
            new AlertDialog.Builder(MainActivity.this).setTitle(d.optString("character","Diálogo")).setMessage(message).setPositiveButton("Fechar",null).show();
        }

        private void showOptionsDialog(JSONArray options) {
            ArrayList<String> labels=new ArrayList<>();ArrayList<Boolean> enabled=new ArrayList<>();
            for(int i=0;i<options.length();i++){JSONObject o=options.optJSONObject(i);labels.add(o==null?"Opção "+(i+1):optionText(o,i));enabled.add(o==null||o.optBoolean("enabled",true));}
            ArrayAdapter<String> adapter=new ArrayAdapter<String>(MainActivity.this,android.R.layout.simple_list_item_1,labels){
                @Override public boolean isEnabled(int position){return enabled.get(position);}
                @Override public View getView(int position,View convertView,android.view.ViewGroup parent){View v=super.getView(position,convertView,parent);v.setAlpha(enabled.get(position)?1f:.45f);return v;}
            };
            new AlertDialog.Builder(MainActivity.this).setTitle("Escolha uma resposta").setAdapter(adapter,(d,w)->{if(w>=0&&enabled.get(w))act("choose","index",w);}).setNegativeButton("Cancelar",null).show();
        }

        private String optionText(JSONObject option,int index){String direct=option.optString("text","");if(!direct.isEmpty())return direct;String t=translatedLines.get(option.optString("line_id",""));return t==null?"Opção "+(index+1):substituteArrayTokens(t,option.optJSONArray("substitutions"));}
        private void scenario(String name){toolsMode=true;JSONObject a=new JSONObject();try{a.put("action","scenario");a.put("name",name);}catch(JSONException ignored){}dispatch(a);}
        private void act(String type,String key,Object value){JSONObject a=new JSONObject();try{a.put("action",type);if(key!=null)a.put(key,value);}catch(JSONException ignored){}dispatch(a);}

        private String animated(String key,JSONArray frames,int fps,int cycling){
            if(frames.length()==0)return "";String sig=frames.toString()+":"+fps+":"+cycling;
            if(!sig.equals(animationSignature.get(key))){animationSignature.put(key,sig);animationStart.put(key,SystemClock.uptimeMillis());}
            long start=animationStart.getOrDefault(key,SystemClock.uptimeMillis());int i=fps<=0?0:(int)((SystemClock.uptimeMillis()-start)*fps/1000L);
            if(cycling==1)i%=frames.length();else i=Math.min(i,frames.length()-1);
            if(frames.length()>1&&(cycling==1||i<frames.length()-1))postInvalidateDelayed(Math.max(50,1000/Math.max(1,fps)));
            return frames.optString(i,"");
        }

        private void button(Canvas c,String label,float l,float t,float r,float b,int color,int radius,Runnable action){fill(c,l,t,r,b,color,radius);center(c,label,(l+r)/2,(t+b)/2+8,24,Color.WHITE,true);hits.add(new Hit(new RectF(l,t,r,b),action));}
        private void fill(Canvas c,float l,float t,float r,float b,int color,float radius){p.setColor(color);p.setStyle(Paint.Style.FILL);c.drawRoundRect(l,t,r,b,radius,radius,p);}
        private void text(Canvas c,String s,float x,float y,float size,int color,boolean bold){p.setColor(color);p.setTextSize(size*uiScale);p.setTypeface(textFontOverride!=null?textFontOverride:(bold?Typeface.DEFAULT_BOLD:Typeface.DEFAULT));c.drawText(s==null?"":s,x,y,p);}
        private void center(Canvas c,String s,float x,float y,float size,int color,boolean bold){p.setTextSize(size*uiScale);p.setTypeface(textFontOverride!=null?textFontOverride:(bold?Typeface.DEFAULT_BOLD:Typeface.DEFAULT));text(c,s,x-p.measureText(s==null?"":s)/2,y,size,color,bold);}
        private void wrap(Canvas c,String value,float x,float y,float maxWidth,float lineHeight,int maxLines,int color,float size){String[] words=(value==null?"":value).replace('\n',' ').split("\\s+");String line="";int row=0;p.setTextSize(size*uiScale);if(textFontOverride!=null)p.setTypeface(textFontOverride);for(String word:words){String candidate=line.isEmpty()?word:line+" "+word;if(p.measureText(candidate)>maxWidth&&!line.isEmpty()){text(c,line,x,y+row*lineHeight,size,color,false);line=word;if(++row>=maxLines-1){line=trim(line,90)+"…";break;}}else line=candidate;}if(row<maxLines)text(c,line,x,y+row*lineHeight,size,color,false);}
        private String trim(String s,int n){return s==null?"":s.length()<=n?s:s.substring(0,Math.max(1,n-1))+"…";}
        private void cover(Canvas c,Bitmap b,float l,float t,float r,float bottom){float s=Math.max((r-l)/b.getWidth(),(bottom-t)/b.getHeight());float w=b.getWidth()*s,h=b.getHeight()*s;c.save();c.clipRect(l,t,r,bottom);c.drawBitmap(b,null,new RectF((l+r-w)/2,(t+bottom-h)/2,(l+r+w)/2,(t+bottom+h)/2),p);c.restore();}
        private void contain(Canvas c,Bitmap b,float l,float t,float r,float bottom){float s=Math.min((r-l)/b.getWidth(),(bottom-t)/b.getHeight());float w=b.getWidth()*s,h=b.getHeight()*s;c.drawBitmap(b,null,new RectF((l+r-w)/2,(t+bottom-h)/2,(l+r+w)/2,(t+bottom+h)/2),p);}
        private void stretch(Canvas c,Bitmap b,float l,float t,float r,float bottom){c.drawBitmap(b,null,new RectF(l,t,r,bottom),p);}
        private void gradient(Canvas c){p.setShader(new android.graphics.LinearGradient(0,0,W,H,0xFF151A20,0xFF39414A,android.graphics.Shader.TileMode.CLAMP));c.drawRect(0,0,W,H,p);p.setShader(null);}

        private float[] logicalPoint(float px,float py) {
            float s=Math.max(.001f,Math.min(getWidth()/W,getHeight()/H));
            return new float[]{(px-(getWidth()-W*s)/2f)/s,(py-(getHeight()-H*s)/2f)/s,s};
        }

        private void pointerDown(MotionEvent e,int index) {
            int id=e.getPointerId(index);float[] q=logicalPoint(e.getX(index),e.getY(index));
            for(int i=hits.size()-1;i>=0;i--)if(hits.get(i).rect.contains(q[0],q[1])){pointerRoles.put(id,ROLE_UI);pointerHits.put(id,hits.get(i));return;}
            if(!initialized||nativeBusy||!"playing".equals(state.optString("phase",""))||!"world".equals(viewMode())||toolsMode||pauseOpen||settingsOpen){pointerRoles.put(id,ROLE_NONE);return;}
            if(q[0]<560&&q[1]>520&&joystickPointer<0){pointerRoles.put(id,ROLE_MOVE);joystickPointer=id;moveJoystick(q[0],q[1]);}
            else if(q[0]>900&&lookPointer<0){pointerRoles.put(id,ROLE_LOOK);lookPointer=id;lookLastX=e.getX(index);lookLastY=e.getY(index);}
            else pointerRoles.put(id,ROLE_NONE);
        }

        private void pointerMove(MotionEvent e) {
            if(roomEngine==null)return;
            for(int i=0;i<e.getPointerCount();i++) {
                int id=e.getPointerId(i),role=pointerRoles.getOrDefault(id,ROLE_NONE);
                if(role==ROLE_MOVE){float[] q=logicalPoint(e.getX(i),e.getY(i));moveJoystick(q[0],q[1]);}
                else if(role==ROLE_LOOK){float s=Math.max(.001f,Math.min(getWidth()/W,getHeight()/H));roomEngine.addLookDelta((e.getX(i)-lookLastX)/s,(e.getY(i)-lookLastY)/s);lookLastX=e.getX(i);lookLastY=e.getY(i);}
            }
            invalidate();
        }

        private void moveJoystick(float x,float y) {
            float dx=(x-250f)/135f,dy=(835f-y)/135f,mag=(float)Math.sqrt(dx*dx+dy*dy);
            if(mag>1f){dx/=mag;dy/=mag;}joystickX=dx;joystickY=dy;
            if(roomEngine!=null)roomEngine.setMoveVector(dx,dy);
        }

        private void pointerUp(MotionEvent e,int index) {
            int id=e.getPointerId(index),role=pointerRoles.getOrDefault(id,ROLE_NONE);
            if(role==ROLE_UI&&!nativeBusy&&initialized){Hit hit=pointerHits.get(id);float[] q=logicalPoint(e.getX(index),e.getY(index));if(hit!=null&&hit.rect.contains(q[0],q[1]))hit.action.run();}
            if(id==joystickPointer){joystickPointer=-1;joystickX=joystickY=0f;if(roomEngine!=null)roomEngine.setMoveVector(0f,0f);}
            if(id==lookPointer)lookPointer=-1;
            pointerRoles.remove(id);pointerHits.remove(id);invalidate();
        }

        private void clearPointers() {
            pointerRoles.clear();pointerHits.clear();joystickPointer=lookPointer=-1;joystickX=joystickY=0f;
            if(roomEngine!=null)roomEngine.setMoveVector(0f,0f);
        }

        @Override public boolean onTouchEvent(MotionEvent e) {
            int action=e.getActionMasked();
            if(action==MotionEvent.ACTION_DOWN||action==MotionEvent.ACTION_POINTER_DOWN){pointerDown(e,e.getActionIndex());return true;}
            if(action==MotionEvent.ACTION_MOVE){pointerMove(e);return true;}
            if(action==MotionEvent.ACTION_UP||action==MotionEvent.ACTION_POINTER_UP){pointerUp(e,e.getActionIndex());return true;}
            if(action==MotionEvent.ACTION_CANCEL){clearPointers();return true;}
            return true;
        }
    }

    private static final class Hit { final RectF rect; final Runnable action; Hit(RectF rect,Runnable action){this.rect=rect;this.action=action;} }
}
