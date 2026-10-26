package org.reconstruction.current;

/** Frame order from AnimatedImage's recovered coroutine; Android supplies elapsed time. */
final class FrameSequence {
    private FrameSequence() { }

    /** -1 means the Image is disabled (empty sequence or completed PlayOnce). */
    static int frameAt(int count, int fps, int cycling, long elapsedMs) {
        if (count <= 0) return -1;
        // Invalid rates have no portable Unity coroutine timing; keep the first frame.
        if (fps <= 0) return 0;
        long elapsed = Math.max(0, elapsedMs);
        long tick = elapsed > Long.MAX_VALUE / fps ? Long.MAX_VALUE : elapsed * fps / 1000L;
        if (cycling == 1) return (int) (tick % count);
        if (tick >= count) return cycling == 0 ? -1 : count - 1;
        return (int) tick;
    }

    /** Next authored frame boundary, or -1 when playback no longer needs redraws. */
    static long nextFrameDelay(int count, int fps, int cycling, long elapsedMs) {
        if (count <= 0 || fps <= 0) return -1;
        long elapsed = Math.max(0, elapsedMs);
        long tick = elapsed > Long.MAX_VALUE / fps ? Long.MAX_VALUE : elapsed * fps / 1000L;
        if (cycling != 1 && (tick >= count || (cycling != 0 && tick >= count - 1))) return -1;
        // The remainder avoids a long-running loop accumulating rounding drift.
        long remainder = (elapsed % 1000L) * fps % 1000L;
        return Math.max(1L, (1000L - remainder + fps - 1L) / fps);
    }

    /** Monotonic game clock frozen by the Android lifecycle and pause/options panels. */
    static final class Clock {
        private long pausedAt, pausedMillis;
        private boolean paused;
        void setPaused(boolean value, long wallMs) {
            if (value == paused) return;
            if (value) pausedAt = wallMs;
            else pausedMillis += Math.max(0L, wallMs - pausedAt);
            paused = value;
        }
        long now(long wallMs) { return (paused ? pausedAt : wallMs) - pausedMillis; }
        boolean isPaused() { return paused; }
    }
}
