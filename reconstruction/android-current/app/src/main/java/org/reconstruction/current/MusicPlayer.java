package org.reconstruction.current;

import android.content.Context;
import android.content.res.AssetFileDescriptor;
import android.content.res.AssetManager;
import android.media.MediaPlayer;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/** A small, lifecycle-gated OGG player for statically recovered music assets. */
public final class MusicPlayer implements AutoCloseable {
    private final AssetManager assets;
    private final Map<String, JSONObject> tracks = new HashMap<>();
    private MediaPlayer player;
    private long generation;
    private boolean closed;
    private boolean pausedByHost = true;
    private boolean muted;
    private float masterGain = 1f;
    private float sourceGain = 1f;
    private String currentAsset = "";
    private String status = "stopped";
    private String lastError = "";

    public MusicPlayer(Context context) {
        if (context == null) throw new IllegalArgumentException("context is required");
        assets = context.getApplicationContext().getAssets();
    }

    /** Loads one track row by key. Playback remains paused until onHostResume(). */
    public synchronized void playConfigured(String manifestAsset, String key) {
        if (closed) { fail("MusicPlayer is closed"); return; }
        try {
            if (manifestAsset == null || manifestAsset.isEmpty()) throw new IllegalArgumentException("manifest asset is empty");
            if (key == null || key.isEmpty()) throw new IllegalArgumentException("track key is empty");
            loadManifestLocked(manifestAsset);
            JSONObject track = tracks.get(key);
            if (track == null) throw new IllegalArgumentException("No music track for key: " + key);
            String asset = track.getString("asset");
            if (asset.isEmpty() || asset.startsWith("/") || asset.contains("..")) throw new IllegalArgumentException("Unsafe music asset path for " + key);
            releasePlayerLocked();
            final long request = ++generation;
            currentAsset = asset;
            sourceGain = clamp((float) track.optDouble("source_volume", 1.0));
            status = "preparing";
            lastError = "";
            MediaPlayer next = new MediaPlayer();
            player = next;
            next.setLooping(track.optBoolean("loop", false));
            next.setVolume(effectiveGainLocked(), effectiveGainLocked());
            next.setOnPreparedListener(prepared -> onPrepared(request, prepared));
            next.setOnCompletionListener(completed -> onCompletion(request, completed));
            next.setOnErrorListener((failed, what, extra) -> {
                onMediaError(request, failed, what, extra);
                return true;
            });
            try (AssetFileDescriptor descriptor = assets.openFd(asset)) {
                next.setDataSource(descriptor.getFileDescriptor(), descriptor.getStartOffset(), descriptor.getLength());
            }
            next.prepareAsync();
        } catch (Exception e) {
            releasePlayerLocked();
            fail("Could not play " + key + ": " + message(e));
        }
    }

    public synchronized void setMuted(boolean value) {
        muted = value;
        updateVolumeLocked();
    }

    public synchronized void setVolume(float value) {
        if (Float.isNaN(value) || Float.isInfinite(value)) value = 1f;
        masterGain = Math.max(0f, Math.min(1f, value));
        updateVolumeLocked();
    }

    public synchronized void onHostPause() {
        pausedByHost = true;
        if (player != null && isPreparedStatus(status)) {
            try { if (player.isPlaying()) player.pause(); }
            catch (IllegalStateException e) { fail("Could not pause music: " + message(e)); }
        }
        if (player != null && isPreparedStatus(status)) status = "paused";
    }

    public synchronized void onHostResume() {
        if (closed) return;
        pausedByHost = false;
        startIfAllowedLocked();
    }

    public synchronized void stop() {
        generation++;
        releasePlayerLocked();
        currentAsset = "";
        status = "stopped";
        lastError = "";
    }

    public synchronized String getStatus() { return status; }
    public synchronized String getCurrentAsset() { return currentAsset; }
    public synchronized String getLastError() { return lastError; }

    @Override public synchronized void close() {
        if (closed) return;
        closed = true;
        generation++;
        releasePlayerLocked();
        currentAsset = "";
        status = "closed";
    }

    private void loadManifestLocked(String manifestAsset) throws Exception {
        if (!tracks.isEmpty()) return;
        JSONObject manifest;
        try (InputStream input = assets.open(manifestAsset); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            manifest = new JSONObject(new String(output.toByteArray(), StandardCharsets.UTF_8));
        }
        JSONArray rows = manifest.optJSONArray("tracks");
        if (rows == null) throw new IllegalArgumentException("Manifest has no tracks array: " + manifestAsset);
        for (int i = 0; i < rows.length(); i++) {
            JSONObject row = rows.optJSONObject(i);
            if (row == null) continue;
            String key = row.optString("key", "");
            if (key.isEmpty()) continue;
            if (tracks.put(key, row) != null) throw new IllegalArgumentException("Duplicate music key: " + key);
        }
        if (tracks.isEmpty()) throw new IllegalArgumentException("Manifest has no usable tracks: " + manifestAsset);
    }

    private synchronized void onPrepared(long request, MediaPlayer prepared) {
        if (closed || request != generation || player != prepared) { safeRelease(prepared); return; }
        status = "ready";
        startIfAllowedLocked();
    }

    private synchronized void onCompletion(long request, MediaPlayer completed) {
        if (closed || request != generation || player != completed) return;
        status = "completed";
    }

    private synchronized void onMediaError(long request, MediaPlayer failed, int what, int extra) {
        if (closed || request != generation || player != failed) return;
        String failedAsset = currentAsset;
        generation++;
        releasePlayerLocked();
        currentAsset = failedAsset;
        status = "error";
        lastError = "MediaPlayer error for " + failedAsset + " (what=" + what + ", extra=" + extra + ")";
    }

    private void startIfAllowedLocked() {
        if (closed || pausedByHost || player == null || !("ready".equals(status) || "paused".equals(status))) return;
        try {
            player.start();
            status = "playing";
        } catch (IllegalStateException e) {
            fail("Could not start music: " + message(e));
            releasePlayerLocked();
        }
    }

    private void updateVolumeLocked() {
        if (player == null) return;
        try {
            float gain = effectiveGainLocked();
            player.setVolume(gain, gain);
        } catch (IllegalStateException e) { fail("Could not set music volume: " + message(e)); }
    }

    private float effectiveGainLocked() { return muted ? 0f : masterGain * sourceGain; }
    private static float clamp(float value) { return Math.max(0f, Math.min(1f, value)); }
    private static boolean isPreparedStatus(String value) { return "ready".equals(value) || "playing".equals(value) || "paused".equals(value); }

    private void releasePlayerLocked() {
        MediaPlayer old = player;
        player = null;
        if (old != null) safeRelease(old);
    }

    private static void safeRelease(MediaPlayer target) {
        try { target.setOnPreparedListener(null); target.setOnCompletionListener(null); target.setOnErrorListener(null); }
        catch (IllegalStateException ignored) { }
        try { target.release(); } catch (RuntimeException ignored) { }
    }

    private void fail(String value) { lastError = value; status = "error"; }
    private static String message(Exception e) { return e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage(); }
}
